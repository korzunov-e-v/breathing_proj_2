import asyncio
import logging
import sys

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


# Настройка расширенного логирования
def setup_logging():
    """Настраивает логирование в файл и stdout"""
    # Создаем логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Обработчик для файла
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Обработчик для stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    # Очищаем существующие обработчики и добавляем новые
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Устанавливаем уровень для httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)


async def log_interaction(update: Update, interaction_type: str, additional_info: str = ""):
    """Логирует все взаимодействия с ботом"""
    user = update.effective_user
    chat = update.effective_chat

    user_info = f"UserID: {user.id}, Username: @{user.username}" if user else "Unknown user"
    chat_info = f"ChatID: {chat.id}, Type: {chat.type}" if chat else "Unknown chat"

    if update.message:
        message_info = f"MessageID: {update.message.message_id}, Text: '{update.message.text}'"
    elif update.callback_query:
        message_info = f"CallbackData: '{update.callback_query.data}'"
    else:
        message_info = "No message data"

    log_message = (
        f"🔹 {interaction_type} | {user_info} | {chat_info} | "
        f"{message_info} | {additional_info}"
    )

    logging.info(log_message)


async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик медиа-файлов с логированием и возвратом file_id"""
    await log_interaction(update, "MEDIA_RECEIVED")

    msg = update.message
    if msg.photo:
        file_id = msg.photo[-1].file_id
        await msg.reply_text(f'Photo file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML', parse_mode='HTML')
    elif msg.video:
        file_id = msg.video.file_id
        await msg.reply_text(f"Video file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML", parse_mode="HTML")
    elif msg.audio:
        file_id = msg.audio.file_id
        await msg.reply_text(f"Audio file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML", parse_mode="HTML")
    elif msg.document:
        file_id = msg.document.file_id
        await msg.reply_text(f"Document file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML", parse_mode="HTML")
    else:
        await msg.reply_text("Пришлите фото, видео, аудио или документ, чтобы получить их file_id для использования в меню.")


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


async def get_rating_keyboard():
    """Создает клавиатуру для оценки 1-10"""
    keyboard = []
    # Первый ряд: 1-5
    row1 = [InlineKeyboardButton(str(i), callback_data=f"rating_{i}") for i in range(1, 6)]
    # Второй ряд: 6-10
    row2 = [InlineKeyboardButton(str(i), callback_data=f"rating_{i}") for i in range(6, 11)]
    keyboard.append(row1)
    keyboard.append(row2)
    return InlineKeyboardMarkup(keyboard)


async def handle_mood_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора настроения"""
    query = update.callback_query
    await query.answer()

    mood_id = query.data.replace("mood_", "")
    await log_interaction(update, "MOOD_SELECTED", f"MoodID: {mood_id}")

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
            # Переходим к запросу рейтинга
            await ask_feedback_rating(update, context)

    except Exception as e:
        logging.error(f"Ошибка в handle_mood_selection: {e}")
        await query.edit_message_text("Произошла ошибка при сохранении настроения")
    finally:
        db.close()


async def show_practice_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает содержание практики после выбора настроения"""
    await log_interaction(update, "PRACTICE_SHOWN")

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if not user:
            await context.bot.send_message(chat_id, "Пользователь не найден")
            return

        # Определяем, какую практику показывать
        if context.user_data.get('selected_practice_id'):
            # Если есть выбранная практика (из повторных или библиотеки), используем ее
            practice = db.query(Practice).filter(Practice.id == context.user_data['selected_practice_id']).first()
            practice_day = practice.day_number if practice else None
            practice_source = "повторения"
        else:
            # Иначе показываем практику текущего дня
            practice = db.query(Practice).filter(Practice.day_number == user.current_day).first()
            practice_day = user.current_day
            practice_source = "дня"

        if not practice:
            await context.bot.send_message(chat_id, "Практика не найдена")
            return

        # Показываем практику
        text = f"""
🧘 *Практика {practice_source} {practice_day}*

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

        await send_text_with_buttons(update, context, "Отметьте завершение практики:", buttons)

    except Exception as e:
        logging.error(f"Ошибка в show_practice_content: {e}")
        await context.bot.send_message(chat_id, "Произошла ошибка при загрузке практики")
    finally:
        db.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с логированием"""
    await log_interaction(update, "START_COMMAND")

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
            logging.info(f"Создан новый пользователь: {user.username} (ID: {user.id})")

            # Онбординг для нового пользователя
            await send_onboarding(update, context, db_user)
        else:
            logging.info(f"Пользователь уже существует: {user.username}")
            # Показываем главное меню из YAML для существующего пользователя
            await show_menu_by_name(update, context, "menu")
    finally:
        db.close()


async def handle_time_selection(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()

    time_str = query.data.replace("set_time_", "")
    await log_interaction(update, "TIME_SELECTED", f"Time: {time_str}")

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


async def ask_feedback_rating(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает оценку практики"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "FEEDBACK_RATING_REQUESTED")

    rating_keyboard = await get_rating_keyboard()
    await query.edit_message_text(
        "📊 *Оцените практику*\n\n"
        "Насколько полезна была для вас эта практика?\n"
        "Оцените от 1 до 10, где 1 - совсем не понравилось, 10 - очень понравилось:",
        reply_markup=rating_keyboard,
        parse_mode='Markdown'
    )


async def handle_rating_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора рейтинга"""
    query = update.callback_query
    await query.answer()

    rating = int(query.data.replace("rating_", ""))
    await log_interaction(update, "RATING_SELECTED", f"Rating: {rating}")

    context.user_data['feedback_rating'] = rating

    # Переходим к запросу комментария
    await ask_feedback_comment(update, context)


async def ask_feedback_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает комментарий к практике"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "FEEDBACK_COMMENT_REQUESTED")

    # Сохраняем состояние ожидания комментария
    context.user_data['waiting_for_comment'] = True

    keyboard = [
        [InlineKeyboardButton("🚫 Пропустить комментарий", callback_data="skip_comment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "💬 *Комментарий к практике*\n\n"
        "Хотите ли вы оставить комментарий или отзыв о практике?\n"
        "Это поможет нам стать лучше!",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пропуска комментария"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "COMMENT_SKIPPED")

    context.user_data['feedback_comment'] = None
    context.user_data.pop('waiting_for_comment', None)

    # Завершаем практику
    await handle_practice_completion(update, context)


async def handle_comment_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстового комментария"""
    if not context.user_data.get('waiting_for_comment'):
        return

    comment = update.message.text
    await log_interaction(update, "COMMENT_RECEIVED", f"Comment: '{comment[:50]}...'")

    context.user_data['feedback_comment'] = comment
    context.user_data.pop('waiting_for_comment', None)

    # Удаляем сообщение с запросом комментария если возможно
    try:
        await context.bot.delete_message(update.effective_chat.id, update.message.message_id - 1)
    except:
        pass

    # Завершаем практику
    await handle_practice_completion(update, context)


async def handle_practice_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик завершения практики с учетом типа (новая/повторная)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Логируем завершение практики
    mood_before = context.user_data.get('mood_before')
    mood_after = context.user_data.get('mood_after')
    rating = context.user_data.get('feedback_rating')
    has_comment = bool(context.user_data.get('feedback_comment'))

    await log_interaction(
        update,
        "PRACTICE_COMPLETED",
        f"MoodBefore: {mood_before}, MoodAfter: {mood_after}, Rating: {rating}, HasComment: {has_comment}"
    )

    # Определяем, откуда брать сообщение для редактирования
    if update.callback_query:
        query = update.callback_query
        message_func = query.edit_message_text
    else:
        query = None
        message_func = lambda text, **kwargs: context.bot.send_message(chat_id, text, **kwargs)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            # Определяем ID практики
            if context.user_data.get('is_repeat'):
                practice_id = context.user_data.get('selected_practice_id')
                practice = db.query(Practice).filter(Practice.id == practice_id).first()
                practice_type = "repeat"
            else:
                practice_id = user.current_day
                practice = db.query(Practice).filter(Practice.day_number == practice_id).first()
                practice_type = "daily"

            # Создаем запись в логе практик
            practice_log = PracticeLog(
                user_id=user.id,
                practice_id=practice_id,
                completed_at=func.now(),
                mood_before=context.user_data.get('mood_before'),
                mood_after=context.user_data.get('mood_after'),
                feedback_rating=context.user_data.get('feedback_rating'),
                feedback_comment=context.user_data.get('feedback_comment'),
                practice_type=practice_type  # Сохраняем тип практики
            )
            db.add(practice_log)

            # Обновляем прогресс пользователя только если это НЕ повтор
            if not context.user_data.get('is_repeat'):
                user.streak += 1
                user.current_day += 1

            user.total_practice_minutes += 5
            user.last_practice_at = func.now()

            # Сбрасываем счетчик напоминаний только для daily практики
            if not context.user_data.get('is_repeat'):
                user.reminder_count_today = 0
                user.freeze_reminders = False

            db.commit()

            # Формируем текст завершения
            completion_text = ""
            if practice and practice.outro_text:
                completion_text = f"🎯 *Завершение практики*\n\n{practice.outro_text}\n\n"

            # Добавляем благодарность за фидбек
            rating = context.user_data.get('feedback_rating')
            if rating:
                completion_text += f"Спасибо за оценку *{rating}/10*! "
            if context.user_data.get('feedback_comment'):
                completion_text += "И за ваш комментарий! "

            if context.user_data.get('is_repeat'):
                completion_text += "🔄\n\nПрактика повторно завершена!"
            else:
                completion_text += "🧘\n\nПрактика завершена!"

            # Очищаем временные данные
            context.user_data.pop('mood_before', None)
            context.user_data.pop('mood_after', None)
            context.user_data.pop('feedback_rating', None)
            context.user_data.pop('feedback_comment', None)
            context.user_data.pop('waiting_for_comment', None)
            context.user_data.pop('selected_practice_id', None)
            context.user_data.pop('is_repeat', None)

            if query:
                await query.edit_message_text(completion_text, parse_mode='Markdown')
            else:
                await context.bot.send_message(chat_id, completion_text, parse_mode='Markdown')

            # Показываем главное меню
            await show_menu_by_name(update, context, "menu")
        else:
            await message_func("Пользователь не найден")
    except Exception as e:
        logging.error(f"Ошибка в handle_practice_completion: {e}")
        await message_func("Произошла ошибка при завершении практики")
    finally:
        db.close()

async def ask_mood_after_practice(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Спрашивает настроение после практики"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "MOOD_AFTER_REQUESTED")

    mood_keyboard = await get_moods_keyboard()
    await query.edit_message_text(
        "🎯 Практика завершена!\n\nКакое у вас настроение теперь?",
        reply_markup=mood_keyboard,
        parse_mode='Markdown'
    )


async def handle_change_time(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для меню смены времени"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "CHANGE_TIME_REQUESTED")

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


async def send_message_with_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    buttons: list,
    query=None,
    chat_id=None,
    menu_text: str = "Выберите действие:",
):
    """Helper function to send a message with menu buttons in ONE message"""
    if query:
        # Создаем клавиатуру для inline-кнопок
        keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Объединяем текст и меню в одном сообщении
        full_text = f"{text}\n\n_{menu_text}_"
        await query.edit_message_text(
            text=full_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        if chat_id is None:
            chat_id = update.effective_chat.id

        # Создаем клавиатуру для inline-кнопок
        keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Объединяем текст и меню в одном сообщении
        full_text = f"{text}\n\n_{menu_text}_"
        await context.bot.send_message(
            chat_id=chat_id,
            text=full_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def send_text_with_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    buttons: list,
    query=None,
    chat_id=None,
    parse_mode: str = 'Markdown'
):
    """Отправляет текст с кнопками в одном сообщении (без отдельного меню)"""
    # Создаем клавиатуру для inline-кнопок
    keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in buttons]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    else:
        if chat_id is None:
            chat_id = update.effective_chat.id
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )


async def show_daily_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает практику дня - доступна только одна в день и только по порядку"""
    await log_interaction(update, "DAILY_PRACTICE_REQUESTED")

    query = update.callback_query
    if query and query.message:
        await query.answer()
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if not user:
            await context.bot.send_message(chat_id, "Пользователь не найден. Начните с /start")
            return

        # Проверяем, выполнял ли пользователь практику СЕГОДНЯ
        today = func.date(func.now())
        today_practice = db.query(PracticeLog).filter(
            PracticeLog.user_id == user.id,
            func.date(PracticeLog.completed_at) == today
        ).first()

        if today_practice:
            # Пользователь уже выполнил практику сегодня
            practice = db.query(Practice).filter(Practice.id == today_practice.practice_id).first()

            text = f"""
✅ *Вы уже выполнили практику сегодня*

🧘 Сегодня вы прошли: День {practice.day_number if practice else '?'} - {practice.intro_text[:100] + '...' if practice and practice.intro_text else 'практику'}

Вы можете повторить пройденные практики через меню "🔄 Пройти снова"
"""
            buttons = [
                {"text": "🔄 Пройти снова", "goto": "practice_again"},
                {"text": "📊 Моя статистика", "goto": "analytics"},
                {"text": "⬅️ Главное меню", "goto": "menu"}
            ]

            await send_text_with_buttons(update, context, text, buttons, query, chat_id)
            return

        # Находим практику для ТЕКУЩЕГО дня пользователя
        practice = db.query(Practice).filter(Practice.day_number == user.current_day).first()

        if not practice:
            # Если практики нет - пользователь прошел все
            text = """
🎉 *Поздравляем!*

Вы завершили все доступные практики.

Что дальше?
"""
            buttons = [
                {"text": "🔄 Пройти снова", "goto": "practice_again"},
                {"text": "📚 Библиотека", "goto": "library"},
                {"text": "⬅️ Главное меню", "goto": "menu"}
            ]

            await send_text_with_buttons(update, context, text, buttons, query, chat_id)
            return

        # Проверяем доступ к премиум контенту
        if practice.premium and not user.subscribed:
            text = f"""
🔒 *Премиум контент*

Практика дня {user.current_day} доступна только для подписчиков.

{practice.intro_text}
"""

            buttons = [
                {"text": "💳 Выбрать подписку", "goto": "subscription_offer"},
                {"text": "🔄 Повторить пройденные", "goto": "practice_again"},
                {"text": "⬅️ Главное меню", "goto": "menu"}
            ]

            await send_text_with_buttons(update, context, text, buttons, query, chat_id)
            return

        # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - показываем практику
        mood_keyboard = await get_moods_keyboard()

        if query:
            await query.edit_message_text(
                f"🧘 *Практика дня {user.current_day}*\n\nКакое у вас сейчас настроение?",
                reply_markup=mood_keyboard,
                parse_mode='Markdown'
            )
        else:
            mood_message = await context.bot.send_message(
                chat_id=chat_id,
                text=f"🧘 *Практика дня {user.current_day}*\n\nКакое у вас сейчас настроение?",
                reply_markup=mood_keyboard,
                parse_mode='Markdown'
            )
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

async def show_practice_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню для повторного прохождения ТОЛЬКО ПРОЙДЕННЫХ практик"""
    await log_interaction(update, "PRACTICE_AGAIN_REQUESTED")

    query = update.callback_query
    if query and query.message:
        await query.answer()
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    user_id = update.effective_user.id
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if not user:
            await context.bot.send_message(chat_id, "Пользователь не найден. Начните с /start")
            return

        # Получаем ID всех пройденных пользователем практик
        completed_practices = db.query(PracticeLog.practice_id).filter(
            PracticeLog.user_id == user.id
        ).distinct().all()
        completed_ids = [p[0] for p in completed_practices]

        if not completed_ids:
            # Если нет пройденных практик
            text = """
🔄 *Повторить практики*

У вас пока нет пройденных практик для повторения.

Сначала пройдите практику дня!
"""
            buttons = [
                {"text": "🧘 Практика дня", "goto": "daily_practice"},
                {"text": "⬅️ Главное меню", "goto": "menu"}
            ]
            await send_text_with_buttons(update, context, text, buttons, query, chat_id)
            return

        # Получаем только пройденные практики
        practices = db.query(Practice).filter(
            Practice.id.in_(completed_ids)
        ).order_by(Practice.day_number).all()

        text = """
🔄 *Повторить практики*

Выберите практику для повторного прохождения:
"""

        # Создаем клавиатуру только с пройденными практиками
        keyboard = []
        for practice in practices:
            button_text = f"✅ День {practice.day_number}"
            if practice.premium and not user.subscribed:
                button_text += " 🔒"

            keyboard.append(
                [InlineKeyboardButton(
                    button_text,
                    callback_data=f"repeat_practice_{practice.id}"
                )]
            )

        # Добавляем кнопки возврата
        keyboard.append(
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="menu"),
                InlineKeyboardButton("🧘 Практика дня", callback_data="daily_practice")
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Ошибка в show_practice_again: {e}")
        error_text = "Произошла ошибка при загрузке практик."
        if query:
            await query.edit_message_text(error_text)
        else:
            await context.bot.send_message(chat_id, error_text)
    finally:
        db.close()
async def handle_repeat_practice_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора практики для повторного прохождения"""
    query = update.callback_query
    await query.answer()

    practice_id = query.data.replace("repeat_practice_", "")
    await log_interaction(update, "REPEAT_PRACTICE_SELECTED", f"PracticeID: {practice_id}")

    db = SessionLocal()
    try:
        practice = db.query(Practice).filter(Practice.id == practice_id).first()
        if not practice:
            await query.edit_message_text("Практика не найдена")
            return

        user_id = update.effective_user.id
        user = db.query(User).filter(User.tg_id == user_id).first()

        # Проверяем доступ к премиум контенту
        if practice.premium and not user.subscribed:
            await query.edit_message_text(
                f"🔒 *Премиум контент*\n\nПрактика дня {practice.day_number} доступна только для подписчиков.",
                parse_mode='Markdown'
            )
            return

        # Сохраняем выбранную практику в context для использования в процессе
        context.user_data['selected_practice_id'] = practice.id
        context.user_data['is_repeat'] = True  # Помечаем как повторное прохождение

        # Спрашиваем настроение перед практикой
        mood_keyboard = await get_moods_keyboard()
        await query.edit_message_text(
            f"🔄 *Повторение практики дня {practice.day_number}*\n\nКакое у вас сейчас настроение?",
            reply_markup=mood_keyboard,
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error(f"Ошибка в handle_repeat_practice_selection: {e}")
        await query.edit_message_text("Произошла ошибка при загрузке практики")
    finally:
        db.close()



async def handle_restart_practices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс прогресса и начало заново"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "PRACTICES_RESTARTED")

    user_id = query.from_user.id
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user.current_day = 1
            user.streak = 0
            # НЕ удаляем логи практик, чтобы пользователь мог их повторять
            db.commit()

            await query.edit_message_text(
                "🔄 *Прогресс сброшен!*\n\nНачинаем новое 7-дневное путешествие.\n\nВаша история пройденных практик сохранена и доступна для повторения.",
                parse_mode='Markdown'
            )
            await show_daily_practice(update, context)
        else:
            await query.edit_message_text("Пользователь не найден")
    finally:
        db.close()

async def send_onboarding(update: Update, _context: ContextTypes.DEFAULT_TYPE, _user: User):
    """Процесс онбординга для нового пользователя"""
    await log_interaction(update, "ONBOARDING_STARTED")

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


async def send_static_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    buttons: list,
    media=None
):
    """Функция для статических меню с поддержкой медиа"""
    await log_interaction(update, "STATIC_MENU_SHOWN")

    query = update.callback_query
    chat_id = update.effective_chat.id

    # Создаем клавиатуру
    keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in buttons]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Если есть медиа - отправляем его
    if media:
        # Определяем тип медиа и отправляем
        for media_item in media:
            media_str = str(media_item).lower()
            if media_str.endswith(('.mp4', '.mov', '.avi')) or media_str.startswith('baac'):
                # Видео
                await context.bot.send_video(chat_id=chat_id, video=media_item)
            elif media_str.endswith(('.jpg', '.jpeg', '.png', '.gif')) or media_str.startswith('agac'):
                # Фото
                await context.bot.send_photo(chat_id=chat_id, photo=media_item)
            elif media_str.endswith(('.mp3', '.m4a', '.ogg')) or media_str.startswith('cAac'):
                # Аудио
                await context.bot.send_audio(chat_id=chat_id, audio=media_item)

    # Отправляем текст с кнопками
    if query:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )


async def send_menu_with_media(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    buttons: list,
    media=None,  # может быть списком file_id
    images=None,  # альтернативное название для медиа
    query=None,
    chat_id=None
):
    """Универсальная функция для отправки меню с медиа (фото/видео)"""
    await log_interaction(update, "MENU_WITH_MEDIA_SHOWN")

    if query:
        await query.answer()
        chat_id = query.message.chat.id
    else:
        if chat_id is None:
            chat_id = update.effective_chat.id

    # Определяем источник медиа (media или images)
    media_files = media or images or []

    # Отправляем медиа, если есть
    for media_file in media_files:
        try:
            media_str = str(media_file).lower()

            # Определяем тип медиа по расширению или префиксу file_id
            if media_str.endswith('.mp4') or media_str.startswith('baac'):
                # Видео
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=media_file,
                    caption=text if media_file == media_files[0] else None,  # Текст только к первому медиа
                    parse_mode='Markdown'
                )
            elif media_str.endswith('.mp3') or media_str.startswith('cAac'):
                # Аудио
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=media_file,
                    caption=text if media_file == media_files[0] else None,
                    parse_mode='Markdown'
                )
            else:
                # Фото (по умолчанию)
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=media_file,
                    caption=text if media_file == media_files[0] else None,
                    parse_mode='Markdown'
                )
        except Exception as e:
            logging.error(f"Ошибка отправки медиа {media_file}: {e}")

    # Если медиа нет или мы хотим гарантированно показать текст с кнопками
    if not media_files:
        # Создаем клавиатуру
        keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if query:
            await query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    else:
        # Если медиа были отправлены, отправляем кнопки отдельным сообщением
        keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=chat_id,
            text="Выберите действие:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )


async def send_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    media, text, buttons, delete=True,
):
    """Отправляет меню с логированием"""
    menu_name = "UNKNOWN"
    if buttons:
        for btn in buttons:
            if btn.get("goto") == "menu":
                menu_name = "MAIN_MENU"
                break
            elif btn.get("goto") == "daily_practice":
                menu_name = "DAILY_PRACTICE_MENU"
                break

    await log_interaction(update, f"MENU_SHOWN_{menu_name}", f"Buttons: {len(buttons)}")

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


async def show_menu_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE, menu_name: str):
    """Показывает меню по имени из YAML с поддержкой медиа"""
    menu_data = get_menu_data(menu_name)

    # Поддерживаем оба варианта: media и images
    media = menu_data.get("media", [])
    images = menu_data.get("images", [])

    await send_menu_with_media(
        update, context,
        text=menu_data.get("text", ""),
        buttons=menu_data.get("buttons", []),
        media=media,
        images=images
    )


def register_handlers(app: Application):
    """Регистрирует только статичные меню из YAML, исключая динамические"""
    with open("data/menu.yaml", "r") as f:
        data = yaml.safe_load(f)

    if "main-menu" not in data:
        raise Exception("No 'main-menu' section in data/menu.yaml")

    # Меню, которые обрабатываются отдельно (не регистрируем их здесь)
    excluded_menus = {
        "daily_practice", "change_time", "practice_again", "all_practices"
    }

    data = data["main-menu"]

    logging.info(f"Найдены меню для регистрации: {list(data.keys())}")

    for menu_name, menu_data in data.items():
        if menu_name in excluded_menus:
            logging.info(f"Пропускаем регистрацию меню: {menu_name}")
            continue

        text = menu_data.get("text", "")
        buttons = menu_data.get("buttons", [])
        media = menu_data.get("media", [])
        images = menu_data.get("images", [])

        logging.info(f"Регистрируем меню: {menu_name} с {len(buttons)} кнопками, медиа: {len(media)}, images: {len(images)}")

        def make_handler(name=menu_name, text_=text, buttons_=buttons, media_=media, images_=images):
            async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await log_interaction(update, f"MENU_NAVIGATION", f"Menu: {name}")
                return await send_menu_with_media(
                    update, context,
                    text=text_,
                    buttons=buttons_,
                    media=media_,
                    images=images_
                )

            return handler

        # Регистрируем команду и callback
        app.add_handler(CommandHandler(menu_name, make_handler()))
        app.add_handler(CallbackQueryHandler(make_handler(), pattern=f"^{menu_name}$"))

    return app
def main():
    create_tables()
    app = ApplicationBuilder().token(settings.bot_token).build()
    setup_logging()

    logging.info("🤖 Бот запущен и готов к работе!")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, receive_media))

    # Обработчики для динамических меню
    app.add_handler(CallbackQueryHandler(handle_change_time, pattern="^change_time$"))
    app.add_handler(CallbackQueryHandler(handle_time_selection, pattern="^set_time_"))
    app.add_handler(CallbackQueryHandler(handle_practice_completion, pattern="^practice_complete$"))
    app.add_handler(CallbackQueryHandler(ask_mood_after_practice, pattern="^ask_mood_after$"))
    app.add_handler(CallbackQueryHandler(handle_restart_practices, pattern="^restart_practices$"))

    # Обработчики для настроений
    app.add_handler(CallbackQueryHandler(handle_mood_selection, pattern="^mood_"))

    # Обработчики для фидбека
    app.add_handler(CallbackQueryHandler(handle_rating_selection, pattern="^rating_"))
    app.add_handler(CallbackQueryHandler(ask_feedback_rating, pattern="^ask_feedback_rating$"))
    app.add_handler(CallbackQueryHandler(handle_comment_skip, pattern="^skip_comment$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment_text))

    # Практики
    app.add_handler(CallbackQueryHandler(show_daily_practice, pattern="^daily_practice$"))
    app.add_handler(CommandHandler("practice", show_daily_practice))
    app.add_handler(CallbackQueryHandler(show_practice_again, pattern="^practice_again$"))
    app.add_handler(CallbackQueryHandler(handle_repeat_practice_selection, pattern="^repeat_practice_"))

    # Регистрируем статичные меню из YAML (библиотека, статьи, музыка и т.д.)
    register_handlers(app)

    app.run_polling()


if __name__ == "__main__":
    main()
