from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.log import log_interaction
from src.modules.practice.pract import handle_practice_completion


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

    msg = await context.bot.send_message(
        chat_id=update.callback_query.message.chat.id,
        text="💬 *Комментарий к практике*\n\n"
        "Хотите ли вы оставить комментарий или отзыв о практике?\n"
        "Это поможет нам стать лучше!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="skip_comment")]
        ])
    )
    context.user_data["comment_prompt_message_id"] = msg.message_id
    context.user_data["waiting_for_comment"] = True


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

    prompt_id = context.user_data.pop("comment_prompt_message_id", None)
    if prompt_id:
        try:
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=prompt_id)
        except BadRequest:
            pass
        except Exception:
            pass

    # Завершаем практику
    await handle_practice_completion(update, context)
