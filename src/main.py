import asyncio
import logging

import yaml
from sqlalchemy import func
from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputMediaVideo, Update
)
from telegram.ext import (
    Application, ApplicationBuilder,
    CallbackQueryHandler, CommandHandler, ContextTypes,
    MessageHandler, filters
)

from src.database import SessionLocal, create_tables
from src.models import PracticeLog, User, Practice, Mood
from src.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.getLogger("httpx").setLevel(logging.WARNING)


async def receive_media(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:
        file_id = msg.photo[-1].file_id  # Берем самый большой размер
        await msg.reply_text(f'Photo file_id: <code>{file_id}</code>', parse_mode='HTML')
    elif msg.video:
        file_id = msg.video.file_id
        await msg.reply_text(f"Video file_id: <code>{file_id}</code>", parse_mode="HTML")
    elif msg.audio:
        file_id = msg.audio.file_id
        await msg.reply_text(f"Audio file_id: <code>{file_id}</code>", parse_mode="HTML")
    elif msg.document:
        file_id = msg.document.file_id
        await msg.reply_text(f"Document file_id: <code>{file_id}</code>", parse_mode="HTML")
    else:
        await msg.reply_text("Пришлите фото, видео, аудио или документ.")


async def get_moods_keyboard():
    """Получает список настроений из БД и создает клавиатуру"""
    db = SessionLocal()
    try:
        moods = db.query(Mood).all()
        keyboard = []
        for mood in moods:
            keyboard.append([InlineKeyboardButton(mood.name, callback_data=f"mood_{mood.id}")])
        return InlineKeyboardMarkup(keyboard)
    finally:
        db.close()


async def handle_mood_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора настроения"""
    query = update.callback_query
    await query.answer()

    mood_id = query.data.replace("mood_", "")
    user_id = query.from_user.id

    db = SessionLocal()
    try:
        mood = db.query(Mood).filter(Mood.id == mood_id).first()
        if not mood:
            await query.edit_message_text("Ошибка: настроение не найдено")
            return

        # Сохраняем выбранное настроение в context.user_data
        if 'mood_before' not in context.user_data:
            # Это настроение перед практикой
            context.user_data['mood_before'] = mood.name

            # УДАЛЯЕМ старое сообщение с выбором настроения
            await query.delete_message()

            # ПОКАЗЫВАЕМ практику сразу после выбора настроения
            await show_practice_content(update, context)

        else:
            # Это настроение после практики
            context.user_data['mood_after'] = mood.name
            await handle_practice_completion(update, context)

    except Exception as e:
        logging.error(f"Ошибка в handle_mood_selection: {e}")
        await query.edit_message_text("Произошла ошибка при сохранении настроения")
    finally:
        db.close()


async def show_practice_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает содержание практики после выбора настроения"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if not user:
            await context.bot.send_message(chat_id, "Пользователь не найден")
            return

        practice = db.query(Practice).filter(Practice.day_number == user.current_day).first()
        if not practice:
            await context.bot.send_message(chat_id, "Практика не найдена")
            return

        # Показываем практику дня
        text = f"""
🧘 *Практика дня {user.current_day}*

{practice.intro_text}

Длительность: ~5 минут

Готовы начать?
"""

        # Если есть аудио - отправляем его
        if practice.audio_file_id:
            try:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=practice.audio_file_id,
                    caption="🎧 Аудио для практики"
                )
            except Exception as e:
                logging.error(f"Ошибка отправки аудио: {e}")

        # Отправляем текст практики
        await context.bot.send_message(chat_id, text, parse_mode='Markdown')

        # Сразу показываем меню завершения
        buttons = [
            {"text": "✅ Я сделал практику", "goto": "ask_mood_after"},
            {"text": "⬅️ Главное меню", "goto": "menu"}
        ]

        await send_menu(update, context, [], "Отметьте завершение практики:", buttons, delete=False)

    except Exception as e:
        logging.error(f"Ошибка в show_practice_content: {e}")
        await context.bot.send_message(chat_id, "Произошла ошибка при загрузке практики")
    finally:
        db.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    _chat_id = update.effective_chat.id

    # Сохраняем/обновляем пользователя в БД
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.tg_id == user.id).first()
        if not db_user:
            db_user = User(
                tg_id=user.id,
                username=user.username,
                current_day=1,
                streak=0
            )
            db.add(db_user)
            db.commit()
            print(f"Создан новый пользователь: {user.username} (ID: {user.id})")

            # Онбординг для нового пользователя
            await send_onboarding(update, context, db_user)
        else:
            print(f"Пользователь уже существует: {user.username}")
            # Показываем главное меню из YAML для существующего пользователя
            await show_menu_by_name(update, context, "menu")
    finally:
        db.close()


async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()

    time_str = query.data.replace("set_time_", "")
    user_id = query.from_user.id

    keyboard = [
        [InlineKeyboardButton("📋 В главное меню", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Сохраняем время в БД
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user.practice_time = time_str
            db.commit()

            # Показываем главное меню из YAML после настройки
            await query.edit_message_text(
                f"*Отлично!* 🎉\n\nВаше время практик установлено на *{time_str}*.\n\n"
                f"Теперь я буду напоминать вам о практике в это время каждый день.\n\n"
                f"Когда будете готовы начать - нажмите кнопку ниже:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("Пользователь не найден. Начните с /start")
    finally:
        db.close()


async def handle_practice_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик завершения практики"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            # Получаем практику для текущего дня (до увеличения дня)
            current_practice = db.query(Practice).filter(Practice.day_number == user.current_day).first()

            # Создаем запись в логе практик
            practice_log = PracticeLog(
                user_id=user.id,
                practice_id=user.current_day,
                completed_at=func.now(),
                mood_before=context.user_data.get('mood_before'),
                mood_after=context.user_data.get('mood_after')
            )
            db.add(practice_log)

            # Обновляем прогресс пользователя
            user.streak += 1
            user.current_day += 1
            user.total_practice_minutes += 5

            # Сбрасываем счетчик напоминаний
            user.reminder_count_today = 0
            user.freeze_reminders = False

            db.commit()

            # Очищаем временные данные настроений
            context.user_data.pop('mood_before', None)
            context.user_data.pop('mood_after', None)

            # Показываем outro_text если он есть, затем меню рефлексии
            if current_practice and current_practice.outro_text:
                outro_text = f"""
🎯 *Завершение практики*

{current_practice.outro_text}

Как вы себя чувствуете теперь?
"""
                await query.edit_message_text(outro_text, parse_mode='Markdown')
                await asyncio.sleep(2)  # Даем время прочитать outro

            # Показываем меню рефлексии из YAML
            await show_menu_by_name(update, context, "practice_complete", delete=False)
        else:
            await query.edit_message_text("Пользователь не найден")
    except Exception as e:
        logging.error(f"Ошибка в handle_practice_completion: {e}")
        await query.edit_message_text("Произошла ошибка при завершении практики")
    finally:
        db.close()


async def ask_mood_after_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Спрашивает настроение после практики"""
    query = update.callback_query
    await query.answer()

    mood_keyboard = await get_moods_keyboard()
    await query.edit_message_text(
        "🎯 Практика завершена!\n\nКакое у вас настроение теперь?",
        reply_markup=mood_keyboard,
        parse_mode='Markdown'
    )


async def handle_reflection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик рефлексии после практики"""
    query = update.callback_query
    await query.answer()

    reflection_type = query.data.replace("reflection_", "")
    logging.info(f"Обработчик рефлексии: {reflection_type}")

    # Получаем соответствующее меню из YAML
    menu_name = f"reflection_{reflection_type}"
    logging.info(f"Пытаемся загрузить меню: {menu_name}")

    try:
        await show_menu_by_name(update, context, menu_name)
    except Exception as e:
        logging.error(f"Ошибка при загрузке меню {menu_name}: {e}")
        await query.edit_message_text(f"Ошибка: меню '{menu_name}' не найдено")


async def handle_change_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для меню смены времени"""
    query = update.callback_query
    await query.answer()

    # Показываем меню выбора времени (программно, не из YAML)
    time_keyboard = [
        [InlineKeyboardButton("07:00", callback_data="set_time_07:00"),
         InlineKeyboardButton("08:00", callback_data="set_time_08:00")],
        [InlineKeyboardButton("09:00", callback_data="set_time_09:00"),
         InlineKeyboardButton("10:00", callback_data="set_time_10:00")],
        [InlineKeyboardButton("11:00", callback_data="set_time_11:00"),
         InlineKeyboardButton("12:00", callback_data="set_time_12:00")],
    ]
    reply_markup = InlineKeyboardMarkup(time_keyboard)

    await query.edit_message_text(
        "Выберите удобное время для ежедневных практик:",
        reply_markup=reply_markup
    )


async def show_daily_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает практику дня с динамическими данными из БД"""
    query = update.callback_query
    if query and query.message:
        await query.answer()
        chat_id = query.message.chat_id
    else:
        chat_id = update.effective_chat.id

    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if not user:
            await context.bot.send_message(chat_id, "Пользователь не найден. Начните с /start")
            return

        # Находим практику для текущего дня пользователя
        practice = db.query(Practice).filter(Practice.day_number == user.current_day).first()

        if not practice:
            # Если практики нет - показываем сообщение и предлагаем начать заново
            text = """
🎉 *Поздравляем!*

Вы завершили все доступные практики.

Что дальше?
"""
            buttons = [
                {"text": "🔄 Начать заново", "goto": "restart_practices"},
                {"text": "📚 Открыть библиотеку", "goto": "library"},
                {"text": "⬅️ Главное меню", "goto": "menu"}
            ]

            if query:
                await query.edit_message_text(text, parse_mode='Markdown')
                await send_menu(update, context, [], "Выберите действие:", buttons)
            else:
                await context.bot.send_message(chat_id, text, parse_mode='Markdown')
                await send_menu(update, context, [], "Выберите действие:", buttons)
            return

        # Проверяем доступ к премиум контенту
        if practice.premium and not user.subscribed:
            # Показываем оффер на подписку (особенно после дня 3)
            if user.current_day == 3:
                text = f"""
✨ *Вы завершили 3 дня практик!*

Прекрасный результат! Чтобы продолжить путешествие и получить доступ к продвинутым практикам, выберите подписку:

*Базовый пакет* - полный доступ к 7-дневной программе
*Премиум пакет* - углубленные практики + поддержка
"""
            else:
                text = f"""
🔒 *Премиум контент*

Эта практика доступна только для подписчиков.

День {user.current_day}: {practice.intro_text}
"""

            buttons = [
                {"text": "💳 Выбрать подписку", "goto": "subscription_offer"},
                {"text": "⬅️ Главное меню", "goto": "menu"}
            ]

            if query:
                await query.edit_message_text(text, parse_mode='Markdown')
                await send_menu(update, context, [], "Выберите действие:", buttons)
            else:
                await context.bot.send_message(chat_id, text, parse_mode='Markdown')
                await send_menu(update, context, [], "Выберите действие:", buttons)
            return

        # Сначала спрашиваем настроение перед практикой
        mood_keyboard = await get_moods_keyboard()

        if query:
            # Если это callback query, редактируем существующее сообщение
            await query.edit_message_text(
                "🧘 *Перед началом практики*\n\nКакое у вас сейчас настроение?",
                reply_markup=mood_keyboard,
                parse_mode='Markdown'
            )
        else:
            # Если это команда, отправляем новое сообщение
            mood_message = await context.bot.send_message(
                chat_id=chat_id,
                text="🧘 *Перед началом практики*\n\nКакое у вас сейчас настроение?",
                reply_markup=mood_keyboard,
                parse_mode='Markdown'
            )
            # Сохраняем ID сообщения с настроением для возможного удаления
            context.user_data['mood_message_id'] = mood_message.message_id

    except Exception as e:
        logging.error(f"Ошибка в show_daily_practice: {e}")
        error_text = "Произошла ошибка при загрузке практики. Попробуйте позже."
        if query:
            await query.edit_message_text(error_text)
        else:
            await context.bot.send_message(chat_id, error_text)
    finally:
        db.close()


async def show_practice_after_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает практику после выбора настроения"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if not user:
            await query.edit_message_text("Пользователь не найден")
            return

        practice = db.query(Practice).filter(Practice.day_number == user.current_day).first()
        if not practice:
            await query.edit_message_text("Практика не найдена")
            return

        # Показываем практику дня
        text = f"""
🧘 *Практика дня {user.current_day}*

{practice.intro_text}

Длительность: ~5 минут

Готовы начать?
"""

        # Если есть аудио - отправляем его
        if practice.audio_file_id:
            try:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=practice.audio_file_id,
                    caption="🎧 Аудио для практики"
                )
            except Exception as e:
                logging.error(f"Ошибка отправки аудио: {e}")

        # Удаляем сообщение с выбором настроения
        mood_message_id = context.user_data.get('mood_message_id')
        if mood_message_id:
            try:
                await context.bot.delete_message(query.message.chat_id, mood_message_id)
            except:
                pass

        # Показываем практику и кнопку завершения
        await query.edit_message_text(text, parse_mode='Markdown')

        buttons = [
            {"text": "✅ Я сделал практику", "goto": "ask_mood_after"},
            {"text": "⬅️ Главное меню", "goto": "menu"}
        ]

        await send_menu(update, context, [], "Отметьте завершение практики:", buttons, delete=False)

    except Exception as e:
        logging.error(f"Ошибка в show_practice_after_mood: {e}")
        await query.edit_message_text("Произошла ошибка при загрузке практики")
    finally:
        db.close()


async def handle_restart_practices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс прогресса и начало заново"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user.current_day = 1
            user.streak = 0
            db.commit()

            await query.edit_message_text(
                "🔄 *Прогресс сброшен!*\n\nНачинаем новое 7-дневное путешествие.",
                parse_mode='Markdown'
            )
            await show_daily_practice(update, context)
        else:
            await query.edit_message_text("Пользователь не найден")
    finally:
        db.close()


async def send_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, user: User):
    """Процесс онбординга для нового пользователя"""

    # 1. Приветствие
    welcome_text = """
*Это ваше тихое место.* 🌿

Давайте создадим ритм, который будет поддерживать вас ежедневно.

Здесь вы найдете практики дыхания, которые помогут:
• Снизить стресс и тревогу
• Улучшить концентрацию  
• Обрести внутреннее спокойствие
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

    await asyncio.sleep(2)

    # 2. Микро-практика (20 секунд)
    practice_text = """
*Давайте начнем с небольшой практики.*

Сядьте удобно, закройте глаза.
Сосредоточьтесь на дыхании...

*20 секунд осознанного дыхания*
⏰ Я подожду...
"""
    await update.message.reply_text(practice_text, parse_mode='Markdown')

    # Имитация ожидания практики
    await asyncio.sleep(5)  # В реальном боте 20 секунд

    # 3. Объяснение пространства
    explanation_text = """
*Отлично!* ✨

Теперь давайте настроим время для ваших ежедневных практик.

Выберите удобное время, и я буду напоминать вам о практике.
"""
    await update.message.reply_text(explanation_text, parse_mode='Markdown')

    # 4. Настройка времени
    time_keyboard = [
        [InlineKeyboardButton("07:00", callback_data="set_time_07:00"),
         InlineKeyboardButton("08:00", callback_data="set_time_08:00")],
        [InlineKeyboardButton("09:00", callback_data="set_time_09:00"),
         InlineKeyboardButton("10:00", callback_data="set_time_10:00")],
        [InlineKeyboardButton("11:00", callback_data="set_time_11:00"),
         InlineKeyboardButton("12:00", callback_data="set_time_12:00")],
    ]
    reply_markup = InlineKeyboardMarkup(time_keyboard)

    await update.message.reply_text(
        "Выберите удобное время для ежедневных практик:",
        reply_markup=reply_markup
    )


async def send_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    media, text, buttons, delete=True,
):

    chat_id = update.effective_chat.id

    # Удаляем старые сообщения
    old = context.user_data.get("menu_messages", [])
    if delete:
        for msg_id in old:
            try:
                await context.bot.delete_message(chat_id, msg_id)
            except:
                pass
    context.user_data["menu_messages"] = []

    # ---------- 1. MEDIA GROUP ----------
    media_group = []

    if media:
        for m in media:
            m_str = str(m).lower()

            # Видео
            if m_str.endswith(".mp4") or m_str.startswith("baac"):
                media_group.append(InputMediaVideo(m))
            # Фото
            else:
                media_group.append(InputMediaPhoto(m))

        sent = await context.bot.send_media_group(chat_id, media=media_group)
        msg_ids = [msg.message_id for msg in sent]
        context.user_data["menu_messages"].extend(msg_ids)

    # ---------- 2. TEXT ----------
    # Используем Markdown для форматирования
    msg_text = await context.bot.send_message(
        chat_id,
        text,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )
    context.user_data["menu_messages"].append(msg_text.message_id)

    # ---------- 3. BUTTONS ----------
    if buttons:
        kb = [
            [InlineKeyboardButton(btn["text"], callback_data=btn["goto"])]
            for btn in buttons
        ]
        markup = InlineKeyboardMarkup(kb)
        msg_btn = await context.bot.send_message(
            chat_id,
            "Выберите пункт:",
            reply_markup=markup
        )
        context.user_data["menu_messages"].append(msg_btn.message_id)


# ------------------------------------------------------------
#  Р Е Г И С Т Р А Ц И Я   М Е Н Ю
# ------------------------------------------------------------
def get_menu_data(menu_name: str) -> dict:
    """Получает данные меню из YAML по имени"""
    try:
        with open("data/menu.yaml", "r") as f:
            data = yaml.safe_load(f)

        logging.info(f"Ищем меню: {menu_name}")
        logging.info(f"Доступные меню: {list(data['main-menu'].keys())}")

        if menu_name not in data["main-menu"]:
            logging.error(f"Меню '{menu_name}' не найдено в YAML")
            return {"text": f"Меню '{menu_name}' не найдено", "buttons": []}

        menu_data = data["main-menu"][menu_name]
        logging.info(f"Меню '{menu_name}' найдено: {menu_data}")
        return menu_data

    except Exception as e:
        logging.error(f"Error loading menu {menu_name}: {e}")
        return {"text": f"Ошибка загрузки меню: {e}", "buttons": []}


async def show_menu_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE, menu_name: str, delete=False):
    """Показывает меню по имени из YAML"""
    menu_data = get_menu_data(menu_name)
    await send_menu(
        update, context,
        media=menu_data.get("media", []),
        text=menu_data.get("text", ""),
        buttons=menu_data.get("buttons", []),
        delete=delete,
    )


def register_handlers(app: Application):
    """Регистрирует только статичные меню из YAML, исключая динамические"""
    with open("data/menu.yaml", "r") as f:
        data = yaml.safe_load(f)

    if "main-menu" not in data:
        raise Exception("No 'main-menu' section in data/menu.yaml")

    # Меню, которые обрабатываются отдельно (не регистрируем их здесь)
    excluded_menus = {
        "daily_practice", "practice_complete", "practice_reflection_good",
        "practice_reflection_calm", "practice_reflection_anxious",
        "practice_reflection_excited", "change_time"
    }

    data = data["main-menu"]

    for menu_name, menu_data in data.items():
        if menu_name in excluded_menus:
            logging.info(f"Пропускаем регистрацию меню: {menu_name}")
            continue

        text = menu_data.get("text", "")
        media = menu_data.get("media", [])
        buttons = menu_data.get("buttons", [])

        def make_handler(name=menu_name, text_=text, media_=media, buttons_=buttons):
            async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                return await send_menu(
                    update, context,
                    media=media_,
                    text=text_,
                    buttons=buttons_
                )

            return handler

        # Регистрируем команду и callback
        app.add_handler(CommandHandler(menu_name, make_handler()))
        app.add_handler(CallbackQueryHandler(make_handler(), pattern=f"^{menu_name}$"))

    return app


def main():
    TOKEN = settings.bot_token
    create_tables()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, receive_media))

    # Обработчики для динамических меню
    app.add_handler(CallbackQueryHandler(handle_change_time, pattern="^change_time$"))
    app.add_handler(CallbackQueryHandler(handle_time_selection, pattern="^set_time_"))
    app.add_handler(CallbackQueryHandler(handle_practice_completion, pattern="^practice_complete$"))
    app.add_handler(CallbackQueryHandler(ask_mood_after_practice, pattern="^ask_mood_after$"))
    app.add_handler(CallbackQueryHandler(handle_reflection, pattern="^reflection_"))
    app.add_handler(CallbackQueryHandler(handle_restart_practices, pattern="^restart_practices$"))

    # Обработчики для настроений
    app.add_handler(CallbackQueryHandler(handle_mood_selection, pattern="^mood_"))

    # ДИНАМИЧЕСКАЯ практика дня - регистрируем отдельно
    app.add_handler(CallbackQueryHandler(show_daily_practice, pattern="^daily_practice$"))
    app.add_handler(CommandHandler("practice", show_daily_practice))

    # Регистрируем статичные меню из YAML
    register_handlers(app)

    app.run_polling()

if __name__ == "__main__":
    main()