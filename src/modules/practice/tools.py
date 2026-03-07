from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.database import AsyncSessionLocal
from src.db.models import Mood


async def get_moods_keyboard(buttons_only=False):
    """Получает список настроений из БД и создает клавиатуру"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Mood)
        )
        moods = result.scalars().all()
        if buttons_only:
            return  [{"text": mood.name, "goto": f"mood_{mood.id}"} for mood in moods]
        keyboard = []
        for mood in moods:
            keyboard.append([InlineKeyboardButton(mood.name, callback_data=f"mood_{mood.id}")])
        return InlineKeyboardMarkup(keyboard)

