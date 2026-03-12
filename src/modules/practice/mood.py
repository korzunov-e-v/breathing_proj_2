import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes

from src.context import UserContextData
from src.db.database import AsyncSessionLocal
from src.db.models import Mood
from src.log import log_interaction
from src.modules.practice.pract import show_practice_content
from src.modules.practice.rate import ask_feedback_comment
from src.modules.practice.tools import get_moods_keyboard


async def handle_mood_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора настроения"""
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data

    mood_id = int(query.data.replace("mood_", ""))
    await log_interaction(update, "MOOD_SELECTED", f"MoodID: {mood_id}")

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(Mood).where(Mood.id == mood_id)
            )
            mood = result.scalars().first()
            if not mood:
                await query.edit_message_text("Ошибка: настроение не найдено")
                return

            # Сохраняем выбранное настроение в context.user_data
            if not user_data.practice_data.mood_before:
                # Это настроение перед практикой
                user_data.practice_data.mood_before = mood.name

                # УДАЛЯЕМ старое сообщение с выбором настроения
                await query.delete_message()
                old_menu_id = user_data.screen_message_id
                if old_menu_id == query.message.message_id:
                    user_data.screen_message_id = None
                # ПОКАЗЫВАЕМ практику сразу после выбора настроения
                await show_practice_content(update, context)

            else:
                # Это настроение после практики
                user_data.practice_data.mood_after = mood.name
                # Переходим к запросу рейтинга
                await query.delete_message()
                await ask_feedback_comment(update, context)

        except Exception as e:
            logging.error(f"Ошибка в handle_mood_selection: {e}")
            await query.edit_message_text("Произошла ошибка при сохранении настроения")


async def ask_mood_after_practice(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Спрашивает настроение после практики"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "MOOD_AFTER_REQUESTED")

    mood_keyboard = await get_moods_keyboard()
    await query.edit_message_text(
        text = """
🧘 Точка тишины

Состояние этого мгновения...
        """,
        reply_markup=mood_keyboard,
        parse_mode='Markdown'
    )
