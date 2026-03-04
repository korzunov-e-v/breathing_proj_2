from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.modules.menu_renderer import replace_menu_message
from src.settings import settings


async def show_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка в меню: включаем режим ожидания текста"""
    user_data: UserContextData = context.user_data
    user_data.state = UserState.FEEDBACK

    text = (
        "📝 *Обратная связь*\n\n"
        "Напишите одним сообщением, что вы хотите нам передать.\n"
        "Мы получим его прямо в боте.\n\n"
        "Чтобы выйти — нажмите «⬅️ В меню»."
    )

    keyboard = [[InlineKeyboardButton("⬅️ В меню", callback_data="menu")]]
    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        media_files=None,
    )


async def handle_feedback_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловим текст от пользователя в режиме FEEDBACK и шлём админам"""
    user_data: UserContextData = context.user_data
    if user_data.state != UserState.FEEDBACK:
        return

    if not update.message or not update.message.text:
        return

    msg_text = update.message.text.strip()
    if not msg_text:
        return

    u = update.effective_user
    chat_id = update.effective_chat.id
    username = f"@{u.username}" if u and u.username else "(нет username)"
    full_name = " ".join([p for p in [getattr(u, "first_name", None), getattr(u, "last_name", None)] if p]) or "(без имени)"
    user_id = u.id if u else None

    admin_text = (
        "📩 ОБРАТНАЯ СВЯЗЬ\n\n"
        f"От: {full_name} {username}\n"
        f"User ID: {user_id}\n"
        f"Chat ID: {chat_id}\n\n"
        f"{msg_text}"
    )

    # лучше без Markdown, чтобы пользователь не мог сломать формат
    for admin_id in settings.admin_tg_ids:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_text)
        except Exception:
            pass

    user_data.state = UserState.IDLE

    await update.message.reply_text(
        "✅ Спасибо! Сообщение отправлено.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В моё пространство", callback_data="menu")]]),
    )
