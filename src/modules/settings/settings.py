from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import User
from src.modules.menu_renderer import replace_menu_message


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает меню настроек с кнопками"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user: User = db.query(User).filter(User.tg_id == user_id).first()

        # Определяем текущее состояние уведомлений
        notifications_status = "🔕 Выключены" if user.freeze_reminders else "🔔 Включены"
        toggle_text = "Включить уведомления" if user.freeze_reminders else "Выключить уведомления"

        keyboard = [
            [InlineKeyboardButton("⏰ Изменить время напоминаний", callback_data="change_time")],
            [InlineKeyboardButton("⏰ Изменить часовой пояс", callback_data="setting_timezone")],
            [InlineKeyboardButton(f"🔔 {toggle_text}", callback_data="toggle_notifications")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        timezone = int(user.timezone)-3
        tzstr = f"MSK+{timezone}" if timezone>=0 else f"MSK{timezone}"
        text = (f"⚙️ Настройки\n\n"
                f"Уведомления: {notifications_status}\n"
                f"Время напоминаний: {user.practice_time}\n"
                f"Часовой пояс: {tzstr}")

        await replace_menu_message(
            context=context,
            text=text,
            reply_markup=reply_markup,
            chat_id=update.effective_chat.id
        )
    finally:
        db.close()


async def toggle_notifications_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переключает состояние уведомлений"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            # Переключаем состояние
            user.freeze_reminders = not user.freeze_reminders
            db.commit()

            # Возвращаемся в меню настроек с обновленным состоянием
            await settings_handler(update, context)
    finally:
        db.close()
