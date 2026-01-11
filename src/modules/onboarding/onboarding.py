import asyncio

from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.models import User
from src.log import log_interaction
from src.modules.settings.time import time_keyboard


async def send_onboarding(update: Update, _context: ContextTypes.DEFAULT_TYPE, _user: User):
    """Процесс онбординга для нового пользователя"""
    await log_interaction(update, "ONBOARDING_STARTED")

    # 1. Приветствие
    welcome_text = """
*Это ваше тихое место.* 🌿

Давайте создадим ритм, который будет поддерживать вас ежедневно.

Здесь вы найдете практики дыхания, которые помогут:
• Снизить стресс и тревогу
• Улучшить концентрацию  
• Обрести внутреннее спокойствие
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

    await asyncio.sleep(2)

    # 2. Микро-практика (20 секунд)
    practice_text = """
*Давайте начнем с небольшой практики.*

Сядьте удобно, закройте глаза.
Сосредоточьтесь на дыхании...

*20 секунд осознанного дыхания*
⏰ Я подожду...
"""
    await update.message.reply_text(practice_text, parse_mode='Markdown')

    # Имитация ожидания практики
    await asyncio.sleep(5)  # В реальном боте 20 секунд

    # 3. Объяснение пространства
    explanation_text = """
*Отлично!* ✨

Теперь давайте настроим время для ваших ежедневных практик.

Выберите удобное время, и я буду напоминать вам о практике.
"""
    await update.message.reply_text(explanation_text, parse_mode='Markdown')

    # 4. Настройка времени
    reply_markup = InlineKeyboardMarkup(time_keyboard)
    await update.message.reply_text(
        "Выберите удобное время для ежедневных практик:",
        reply_markup=reply_markup
    )
