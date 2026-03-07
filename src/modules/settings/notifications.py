from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import User


async def pause_notifications_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

            await query.edit_message_text(
                "🔕 Уведомления приостановлены. Вы можете возобновить их в любое время."
            )


