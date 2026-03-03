from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.database import SessionLocal
from src.db.models import Mood


async def get_moods_keyboard(buttons_only=False):
    """Получает список настроений из БД и создает клавиатуру"""
    with SessionLocal() as db:
        try:
            moods = db.query(Mood).all()
            if buttons_only:
                return  [{"text": mood.name, "goto": f"mood_{mood.id}"} for mood in moods]
            keyboard = []
            for mood in moods:
                keyboard.append([InlineKeyboardButton(mood.name, callback_data=f"mood_{mood.id}")])
            return InlineKeyboardMarkup(keyboard)
        finally:
            db.close()
