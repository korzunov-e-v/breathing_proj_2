from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import User


async def skip_today_handler(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == user_id)
        )
        user = result.scalars().first()

        if user:
            user.freeze_reminders = True
            await db.commit()

            await query.edit_message_text("✋ Хорошо, отменяю напоминания на сегодня. Удачи!")


async def remind_later_handler(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == user_id)
        )
        user = result.scalars().first()
        if user:
            user.reminder_count_today = min(user.reminder_count_today + 1, 4)
            await db.commit()
            await query.edit_message_text("⏰ Хорошо, напомню позже!")
