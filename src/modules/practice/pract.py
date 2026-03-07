import logging

from sqlalchemy import func, select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.context import UserContextData
from src.db.database import AsyncSessionLocal
from src.db.models import Practice, PracticeLog, User
from src.log import log_interaction
from src.modules.library.tools import is_user_subscribed
from src.modules.menu_renderer import replace_menu_message
from src.modules.practice.tools import get_moods_keyboard


async def show_practice_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает содержание практики после выбора настроения"""
    await log_interaction(update, "PRACTICE_SHOWN")

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_data: UserContextData = context.user_data

    async with AsyncSessionLocal() as db:
        try:
            user_result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = user_result.scalars().first()

            if not user:
                await context.bot.send_message(chat_id, "Пользователь не найден")
                return

            if user_data.practice_data.selected_practice_id:
                practice_result = await db.execute(
                    select(Practice).where(
                        Practice.id == user_data.practice_data.selected_practice_id
                    )
                )
                practice: Practice | None = practice_result.scalars().first()
            else:
                practice_result = await db.execute(
                    select(Practice).where(
                        Practice.day_number == user.current_day
                    )
                )
                practice: Practice | None = practice_result.scalars().first()

            # Если есть аудио - отправляем его
            if practice.audio_file_id:
                try:
                    audio_msg = await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=practice.audio_file_id,
                        caption="🎧 Аудио для практики"
                    )
                    user_data.practice_data.practice_message_ids.append(audio_msg.message_id)
                except Exception as e:
                    logging.error(f"Ошибка отправки аудио: {e}")
            if practice.video_file_id:
                try:
                    video_msg = await context.bot.send_video(
                        chat_id=chat_id,
                        video=practice.video_file_id,
                        caption="🎧 Видео для практики"
                    )
                    user_data.practice_data.practice_message_ids.append(video_msg.message_id)
                except Exception as e:
                    logging.error(f"Ошибка отправки видео: {e}")

            # Сразу показываем меню завершения
            buttons = [
                {"text": "🍃 Выдох", "goto": "ask_mood_after"},
                {"text": "🌌 В моё пространство", "goto": "menu"}
            ]

            await replace_menu_message(
                chat_id=chat_id,
                context=context,
                text="""
Этот момент был твоим.  
Спасибо, что позволил ему случиться...

Пусть дальше говорит выдох.
                """,
                buttons=buttons,
                media_files=[],
            )

        except Exception as e:
            logging.error(f"Ошибка в show_practice_content: {e}")
            await context.bot.send_message(chat_id, "Произошла ошибка при загрузке практики")


async def handle_practice_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик завершения практики с учетом типа (новая/повторная)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_data: UserContextData = context.user_data

    # Логируем завершение практики
    mood_before = user_data.practice_data.mood_before
    mood_after = user_data.practice_data.mood_after
    comment = user_data.practice_data.feedback_comment
    ai_reply = user_data.practice_data.feedback_ai_reply
    has_comment = bool(user_data.practice_data.feedback_comment)

    await log_interaction(
        update,
        "PRACTICE_COMPLETED",
        f"MoodBefore: {mood_before}, MoodAfter: {mood_after}, HasComment: {has_comment}"
    )

    # Определяем, откуда брать сообщение для редактирования
    if update.callback_query:
        query = update.callback_query
        message_func = query.edit_message_text
    else:
        query = None
        message_func = lambda text, **kwargs: context.bot.send_message(chat_id, text, **kwargs)

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = result.scalars().first()
            if user:
                if user_data.practice_data.is_repeat:
                    practice_id = user_data.practice_data.selected_practice_id

                    result = await db.execute(
                        select(Practice).where(Practice.id == practice_id)
                    )
                    practice = result.scalars().first()
                    practice_type = "repeat"

                else:
                    result = await db.execute(
                        select(Practice).where(Practice.day_number == user.current_day)
                    )
                    practice = result.scalars().first()
                    practice_id = practice.id if practice else None
                    practice_type = "daily"

                practice_log = PracticeLog(
                    user_id=user.id,
                    practice_id=practice_id,
                    completed_at=func.now(),
                    mood_before=str(user_data.practice_data.mood_before),
                    mood_after=str(user_data.practice_data.mood_after),
                    feedback_rating=0,
                    feedback_comment=user_data.practice_data.feedback_comment,
                    practice_type=practice_type
                )

                db.add(practice_log)

                # Обновляем прогресс пользователя, только если это НЕ повтор
                if not user_data.practice_data.is_repeat:
                    user.streak += 1
                    user.current_day += 1

                user.total_practice_minutes += 5
                user.last_practice_at = func.now()

                if not user_data.practice_data.is_repeat:
                    user.reminder_count_today = 0
                    user.freeze_reminders = False

                await db.commit()

                # Формируем текст завершения
                completion_text = "Спасибо."
                if practice and practice.outro_text:
                    completion_text = f"""
⟡ Между 

Спасибо, что поделился частью себя.  
Это остаётся здесь — без оценки, без спешки.

Можно просто позволить этому быть.

{practice.outro_text if practice.outro_text else ""}
                    """

                # Добавляем благодарность за фидбек
                if comment:
                    if ai_reply:
                        completion_text += "\n\n🧘 Ответ на ваш комментарий:\n"
                        completion_text += ai_reply
                    else:
                        # фоллбек, если OpenRouter не отработал/не успел/упал
                        completion_text += "\n\n💬 Спасибо за комментарий!"

                # Очищаем временные данные
                user_data.clear_practice_data()

                # Создаем inline-клавиатуру с кнопкой "меню"
                keyboard = [[InlineKeyboardButton("🌌 В моё пространство", callback_data="menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                if query:
                    await query.edit_message_text(completion_text, parse_mode='HTML', reply_markup=reply_markup)
                else:
                    await context.bot.send_message(chat_id, completion_text, parse_mode='HTML', reply_markup=reply_markup)

                # Показываем главное меню
                # await show_main_menu(update, context)
            else:
                await message_func("Пользователь не найден")
        except Exception as e:
            logging.error(f"Ошибка в handle_practice_completion: {e}")
            await message_func("Произошла ошибка при завершении практики")


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
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = result.scalars().first()
            if not user:
                await context.bot.send_message(chat_id, "Пользователь не найден. Начните с /start")
                return

            # Проверяем, выполнял ли пользователь практику СЕГОДНЯ
            today = func.date(func.now())
            result = await db.execute(
                select(PracticeLog).where(
                    PracticeLog.user_id == user.id,
                    func.date(PracticeLog.completed_at) == today
                )
            )
            today_practice = result.scalars().first()

            if today_practice:
                # Пользователь уже выполнил практику сегодня
                result = await db.execute(
                    select(Practice).where(Practice.id == today_practice.practice_id)
                )
                practice = result.scalars().first()
                text = f"""
🌿 Сегодня ты уже был с дыханием

Этот шаг сделан.  
Тело помнит его.

🧘 Ты прошёл сегодня:  
Вдох {practice.day_number}

Если чувствуешь отклик —  
можно пройти этот путь ещё раз,  
уже из другого состояния, просто 🔄 Вернись к дыханию.

Или просто побыть с тем, что есть сейчас.
                """
                buttons = [
                    {"text": "🔄 Вернуться к дыханию", "goto": "practice_again"},
                    {"text": "📊 Мой ритм", "goto": "analytics"},
                    {"text": "🌌 В моё пространство", "goto": "menu"}
                ]

                await replace_menu_message(
                    chat_id=chat_id,
                    context=context,
                    text=text,
                    buttons=buttons,
                    media_files=[],
                )
                return

            # Находим практику для ТЕКУЩЕГО дня пользователя
            result = await db.execute(
                select(Practice).where(Practice.day_number == user.current_day)
            )
            practice = result.scalars().first()

            if not practice:
                # Если практики нет - пользователь прошел все
                text = ("🎉 *Поздравляем!*\n"
                        "\n"
                        "Вы завершили все доступные практики.\n"
                        "\n"
                        "Что дальше?")
                buttons = [
                    {"text": "🔄 Пройти снова", "goto": "practice_again"},
                    {"text": "📚 Библиотека", "goto": "library"},
                    {"text": "⬅️ В моё пространство", "goto": "menu"}
                ]

            # Проверяем доступ к премиум контенту
            elif practice.premium and not await is_user_subscribed(user_id):
                text = f"""
*✨ Открыть полное пространство Кабира*

Базовые дыхания — это старт.  
Полная версия — это:  
• ежедневный ритм дыханий  
• еще шесть голосовых практик от Кабира  
• мягкая поддержка в паузах

Здесь дыхание становится частью дня, а не редким событием.
                """
                buttons = [
                    {"text": "💳 Открыть полное пространство", "goto": "subscription_offer"},
                    {"text": "🌌 В моё пространство", "goto": "menu"}
                ]
            else:
                # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - показываем практику
                text = f"""
🧘 *Дыхание дня {user.current_day}*

Состояние этого мгновения...
                """
                buttons = await get_moods_keyboard(buttons_only=True)
            await replace_menu_message(
                chat_id=chat_id,
                context=context,
                text=text,
                buttons=buttons,
                media_files=[],  # без медиа на этом экране
            )

        except Exception as e:
            logging.error(f"Ошибка в show_daily_practice: {e}")
            error_text = "Произошла ошибка при загрузке практики. Попробуйте позже."
            if query:
                await query.edit_message_text(error_text)
            else:
                await context.bot.send_message(chat_id, error_text)


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
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = result.scalars().first()
            if not user:
                await context.bot.send_message(chat_id, "Пользователь не найден. Начните с /start")
                return

            # Получаем ID всех пройденных пользователем практик
            result = await db.execute(
                select(PracticeLog.practice_id)
                .where(PracticeLog.user_id == user.id)
                .distinct()
            )
            completed_practices = result.scalars().all()
            completed_ids = [p[0] for p in completed_practices]

            if not completed_ids:
                # Если нет пройденных практик
                text = """
🔄 Возвращение к дыханию

Иногда полезно пройти путь ещё раз.  
Не чтобы повторить —  
а чтобы услышать его глубже.

Выбери то, к чему хочется вернуться сейчас.

У вас пока нет пройденных дней для повторения.
    """
                buttons = [
                    {"text": "🧘 Первый вдох", "goto": "daily_practice"},
                    {"text": "🌌 В моё пространство", "goto": "menu"}
                ]
                await replace_menu_message(
                    chat_id=chat_id,
                    context=context,
                    text=text,
                    buttons=buttons,
                    media_files=[],
                )
                return

            # Получаем только пройденные практики
            result = await db.execute(
                select(Practice)
                .where(Practice.id.in_(completed_ids))
                .order_by(Practice.day_number)
            )
            practices = result.scalars().all()

            text = """
🔄 Возвращение к дыханию

Иногда полезно пройти путь ещё раз.  
Не чтобы повторить —  
а чтобы услышать его глубже.

Выбери то, к чему хочется вернуться сейчас.
    """

            # Создаем клавиатуру только с пройденными практиками
            keyboard = []
            for practice in practices:
                button_text = f"✅ Вдох {practice.day_number}"
                if practice.premium and not await is_user_subscribed(user_id):
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
                    InlineKeyboardButton("🌌 В моё пространство", callback_data="menu"),
                ]
            )

            reply_markup = InlineKeyboardMarkup(keyboard)

            if query:
                await replace_menu_message(
                    chat_id=chat_id,
                    context=context,
                    text=text,
                    buttons=[],  # можно пустой
                    reply_markup=reply_markup,
                    media_files=[],
                )
            else:
                await replace_menu_message(
                    chat_id=chat_id,
                    context=context,
                    text=text,
                    reply_markup=reply_markup,
                    media_files=[],
                )

        except Exception as e:
            logging.error(f"Ошибка в show_practice_again: {e}")
            error_text = "Произошла ошибка при загрузке практик."
            if query:
                await query.edit_message_text(error_text)
            else:
                await context.bot.send_message(chat_id, error_text)


async def handle_repeat_practice_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора практики для повторного прохождения"""
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data

    practice_id = query.data.replace("repeat_practice_", "")
    await log_interaction(update, "REPEAT_PRACTICE_SELECTED", f"PracticeID: {practice_id}")

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Practice).where(Practice.id == practice_id)
            )
            practice = result.scalars().first()
            if not practice:
                await query.edit_message_text("Практика не найдена")
                return

            user_id = update.effective_user.id
            result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = result.scalars().first()

            # Проверяем доступ к премиум контенту
            if practice.premium and not await is_user_subscribed(user_id):
                await query.edit_message_text(
                    f"🔒 *Премиум контент*\n\nПрактика дня {practice.day_number} доступна только для подписчиков.",
                    parse_mode='Markdown'
                )
                return

            # Сохраняем выбранную практику в context для использования в процессе
            user_data.practice_data.selected_practice_id = practice.id
            user_data.practice_data.is_repeat = True  # Помечаем как повторное прохождение

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


async def handle_restart_practices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс прогресса и начало заново"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "PRACTICES_RESTARTED")

    user_id = query.from_user.id
    async with AsyncSessionLocal() as db:

        try:
            result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = result.scalars().first()
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
