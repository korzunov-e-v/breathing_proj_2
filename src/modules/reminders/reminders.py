from telegram import Update
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import User


async def skip_today_handler(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            # Замораживаем напоминания на сегодня
            user.freeze_reminders = True
            db.commit()

            await query.edit_message_text("✋ Хорошо, отменяю напоминания на сегодня. Удачи!")
    finally:
        db.close()


async def remind_later_handler(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            # Увеличиваем счетчик напоминаний, чтобы перейти к следующему
            user.reminder_count_today = min(user.reminder_count_today + 1, 4)
            db.commit()

            await query.edit_message_text("⏰ Хорошо, напомню позже!")
    finally:
        db.close()
