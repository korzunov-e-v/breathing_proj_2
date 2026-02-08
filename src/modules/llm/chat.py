from telegram import Update
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.modules.menu_renderer import replace_menu_message


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for chat button that sets flag and sends message"""
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data
    user_data.state = UserState.CHAT

    await replace_menu_message(
        chat_id=query.message.chat.id,
        context=context,
        text="Это чат с ИИ версией Кабира",
        buttons=[],
        media_files=[],
    )
