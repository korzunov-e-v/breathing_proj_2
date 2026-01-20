from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.database import SessionLocal
from src.db.models import Mood


async def get_moods_keyboard(buttons_only=False):
    """Получает список настроений из БД и создает клавиатуру"""
    db = SessionLocal()
    try:
        moods = db.query(Mood).all()
        keyboard = []
        for mood in moods:
            keyboard.append([InlineKeyboardButton(mood.name, callback_data=f"mood_{mood.id}")])
        if buttons_only:
            return keyboard
        return InlineKeyboardMarkup(keyboard)
    finally:
        db.close()
