from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.modules.llm.openrouter_client import generate_comment_reply, chat_with_context
from src.modules.menu_renderer import replace_menu_message
from src.log import log_interaction
from src.settings import settings


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for chat button that sets flag and sends message"""
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data
    user_data.state = UserState.CHAT
    user_data.last_chat_message_id = None

    await replace_menu_message(
        chat_id=query.message.chat.id,
        context=context,
        text="Это чат с ИИ версией Кабира",
        buttons=[],
        media_files=[],
    )


async def stop_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for stop chat button that clears context and returns to main menu"""
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data
    user_data.ai_chat_context = []
    user_data.state = UserState.IDLE

    try:
        if user_data.last_chat_message_id:
            await context.bot.edit_message_reply_markup(
                chat_id=update.callback_query.message.chat.id,
                message_id=user_data.last_chat_message_id,
                reply_markup=None
            )
    except Exception:
        pass
    user_data.last_chat_message_id = None

    from src.modules.menu_renderer import show_main_menu
    await show_main_menu(update, context)


async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for text messages in AI chat"""
    user_data: UserContextData = context.user_data

    # Check if user is in CHAT state
    if user_data.state != UserState.CHAT:
        return

    user_message = update.message.text
    chat_history = user_data.ai_chat_context

    # Add user message to history
    chat_history.append({"role": "user", "content": user_message})

    await log_interaction(update, "CHAT_MESSAGE")

    user_message = update.message.text

    # Remove button from previous message
    if user_data.last_chat_message_id:
        try:
            await context.bot.edit_message_reply_markup(
                chat_id=update.message.chat.id,
                message_id=user_data.last_chat_message_id,
                reply_markup=None
            )
        except Exception:
            pass

    await update.message.chat.send_action(action="typing")
    response_text = await chat_with_context(messages=[{"role": "user", "content": user_message}], temperature=0.7, max_tokens=250)
    chat_history.append({"role": "assistant", "content": response_text})

    # Create stop chat button
    keyboard = [[InlineKeyboardButton("Покинуть чат", callback_data="stop_chat")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent_message = await update.message.reply_text(response_text, reply_markup=reply_markup)
    user_data.last_chat_message_id = sent_message.message_id
