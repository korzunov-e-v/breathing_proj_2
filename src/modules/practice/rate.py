import datetime
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.log import log_interaction
from src.modules.llm.openrouter_client import generate_comment_reply, OpenRouterError
from src.modules.practice.pract import handle_practice_completion
from src.settings import settings


async def ask_feedback_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запрашивает комментарий к практике"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "FEEDBACK_COMMENT_REQUESTED")

    user_data: UserContextData = context.user_data

    # Сохраняем состояние ожидания комментария
    user_data.state = UserState.WAITING_COMMENT

    keyboard = [
        [InlineKeyboardButton("🌌 Тишина", callback_data="skip_comment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = await context.bot.send_message(
        chat_id=update.callback_query.message.chat.id,
        text="""
💬 Разделить момент

Место для слов о себе. Просто напиши их...
    """,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    user_data.screen_message_id = msg.message_id


async def handle_comment_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик пропуска комментария"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "COMMENT_SKIPPED")

    user_data: UserContextData = context.user_data
    user_data.practice_data.feedback_comment = None
    user_data.state = UserState.IDLE

    # Завершаем практику
    await handle_practice_completion(update, context)


async def handle_comment_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстового комментария"""
    user_data: UserContextData = context.user_data

    if user_data.state != UserState.WAITING_COMMENT:
        return

    user_data.state = UserState.IDLE

    user_data.practice_data.feedback_comment = update.message.text

    mood_before = user_data.practice_data.mood_before
    mood_after = user_data.practice_data.mood_after
    feedback_comment = user_data.practice_data.feedback_comment

    ai_context = {
        "mood_before": mood_before,
        "mood_after": mood_after,
        "feedback_comment": feedback_comment,
        "current_time": datetime.datetime.now(),
    }

    await log_interaction(update, "COMMENT_RECEIVED", f"Comment: '{feedback_comment[:50]}...'")

    # +++ промпт: либо то, что ты задашь в рантайме, либо дефолт из env
    system_prompt = settings.openrouter_comment_prompt + f"\n{ai_context}"

    # +++ вызываем Sonnet
    ai_reply = None
    try:
        ai_reply = await generate_comment_reply(system_prompt=system_prompt, user_comment=feedback_comment)
    except OpenRouterError as e:
        logging.warning(f"OpenRouterError: {e}")
    except Exception as e:
        logging.exception(f"Unexpected error calling OpenRouter: {e}")

    # сохраним, чтобы показать в завершении практики
    user_data.practice_data.feedback_ai_reply = ai_reply

    # Удаляем сообщение с запросом комментария если возможно
    try:
        await context.bot.delete_message(update.effective_chat.id, update.message.message_id - 1)
    except:
        pass

    # Завершаем практику
    await handle_practice_completion(update, context)
