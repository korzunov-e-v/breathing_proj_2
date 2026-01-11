from telegram import Update
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import User


async def pause_notifications_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user: User
            # Устанавливаем флаг паузы уведомлений
            user.freeze_reminders = True
            db.commit()

            await query.edit_message_text("🔕 Уведомления приостановлены. Вы можете возобновить их в любое время.")
    finally:
        db.close()


