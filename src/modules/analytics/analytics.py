from datetime import datetime, timedelta
from typing import List, Dict, Any

from pytz import UTC
from sqlalchemy.orm import selectinload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import desc, select
from collections import Counter

from src.db.database import AsyncSessionLocal
from src.db.models import PracticeLog, User
from src.modules.menu_renderer import replace_menu_message
from src.modules.llm.openrouter_client import chat_with_context, OpenRouterError
import logging

logger = logging.getLogger(__name__)


async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает единое меню аналитики без вложенных кнопок"""
    query = update.callback_query
    if query:
        await query.answer()

    user_id = update.effective_user.id

    async with AsyncSessionLocal() as db:
        try:
            user_result = await db.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = user_result.scalars().first()

            practice_logs_result = await db.execute(
                select(PracticeLog)
                .options(selectinload(PracticeLog.practice))
                .where(PracticeLog.user_id == user.id)
                .order_by(desc(PracticeLog.completed_at))
                .limit(50)
            )
            practice_logs = practice_logs_result.scalars().all()

            if not practice_logs:
                text = """
🌀 Дневник состояний

Ты пока не выполнил ни одной практики.

Вернись после практики дыхания, 
чтобы увидеть здесь свои изменения.
                """

                keyboard = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🌬 Начать практику", callback_data="daily_practice")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
                    ]
                )

                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text=text,
                    reply_markup=keyboard,
                    media_files=None,
                )
                return

            # Формируем дневник эмоций
            text = "🌀 Дневник состояний\n\n"

            # Раздел 1: Последние практики с эмоциями
            text += "Последние практики:\n\n"
            for log in practice_logs[:10]:  # Показываем последние 10
                date_str = log.completed_at.strftime("%d.%m %H:%M") if log.completed_at else "Дата неизвестна"

                practice_name = f"Практика #{log.practice_id}"
                if log.practice and hasattr(log.practice, 'day_number'):
                    practice_name = f"День {log.practice.day_number}"

                emotions_line = ""
                if log.mood_before:
                    emotions_line += f"{log.mood_before} → "

                emotions_line += f"{practice_name} ({date_str})"

                if log.mood_after:
                    emotions_line += f" → {log.mood_after}"

                text += f"• {emotions_line}\n"

            text += "\n"
            # Раздел 2: Статистика
            text += "Статистика:\n"

            total_practices = len(practice_logs)
            text += f"• Всего практик: {total_practices}\n"

            # Практики за последние 30 дней
            thirty_days_ago = datetime.now(tz=UTC) - timedelta(days=30)
            recent_practices = [log for log in practice_logs if log.completed_at and log.completed_at >= thirty_days_ago]
            text += f"• За 30 дней: {len(recent_practices)}\n"

            # Самые частые эмоции
            all_moods = [log.mood_before for log in practice_logs if log.mood_before] + \
                        [log.mood_after for log in practice_logs if log.mood_after]

            if all_moods:
                common_moods = Counter(all_moods).most_common(3)
                text += f"• Частые состояния: {', '.join([m[0] for m in common_moods])}\n"

            # Самые частые смены эмоций
            mood_changes = []
            for log in practice_logs:
                if log.mood_before and log.mood_after:
                    mood_changes.append(f"{log.mood_before} → {log.mood_after}")

            if mood_changes:
                common_changes = Counter(mood_changes).most_common(2)
                text += f"• Частые изменения: {', '.join([c[0] for c in common_changes])}\n"

            # Раздел 3: Анализ от LLM (если достаточно данных)
            if len(practice_logs) >= 1:
                try:
                    # Подготавливаем данные для LLM
                    llm_context = await _prepare_llm_context(practice_logs, user)

                    # Генерируем анализ
                    analysis = await _generate_llm_analysis(llm_context)

                    if analysis:
                        text += f"\nАнализ:\n{analysis}\n"
                except Exception as e:
                    logger.exception("Ошибка при генерации анализа LLM: %s", e)
                    text += "\nАнализ:\n(Не удалось сгенерировать анализ. Попробуйте позже.)\n"
            else:
                text += "\nАнализ:\n(Выполни 1+ практик, чтобы получить анализ.)\n"

            # Кнопки
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔄 Обновить анализ", callback_data="analytics")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
                ]
            )

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=keyboard,
                media_files=None,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception("Ошибка в show_analytics: %s", e)
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="🌀 Дневник состояний\n\nПроизошла ошибка при загрузке данных. Попробуйте позже или нажмите /start заново.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
                    ]
                ),
                media_files=None,
            )


async def _prepare_llm_context(practice_logs: List[PracticeLog], user: User) -> Dict[str, Any]:
    """Подготавливает контекст для LLM"""
    # Собираем статистику
    total_practices = len(practice_logs)

    # Средняя оценка
    ratings = [log.feedback_rating for log in practice_logs if log.feedback_rating]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    # Самые частые эмоции
    all_moods = [log.mood_before for log in practice_logs if log.mood_before] + \
                [log.mood_after for log in practice_logs if log.mood_after]
    common_moods = Counter(all_moods).most_common(5) if all_moods else []

    # Смены эмоций
    mood_changes = []
    for log in practice_logs:
        if log.mood_before and log.mood_after:
            mood_changes.append(f"{log.mood_before} → {log.mood_after}")
    common_changes = Counter(mood_changes).most_common(5) if mood_changes else []

    # Активность по времени
    morning_count = 0
    afternoon_count = 0
    evening_count = 0

    for log in practice_logs:
        if log.completed_at:
            hour = log.completed_at.hour
            if 5 <= hour < 12:
                morning_count += 1
            elif 12 <= hour < 17:
                afternoon_count += 1
            else:
                evening_count += 1

    return {
        "total_practices": total_practices,
        "avg_rating": avg_rating,
        "common_moods": [{"mood": m[0], "count": m[1]} for m in common_moods],
        "common_changes": [{"change": c[0], "count": c[1]} for c in common_changes],
        "time_distribution": {
            "morning": morning_count,
            "afternoon": afternoon_count,
            "evening": evening_count
        },
        "user_name": user.username or f"Пользователь #{user.tg_id}",
        "user_streak": user.streak if hasattr(user, 'streak') else 0
    }


async def _generate_llm_analysis(context: Dict[str, Any]) -> str:
    """Генерирует анализ с помощью LLM"""
    try:
        # Формируем промпт
        prompt = f"""
        Проанализируй данные о практиках пользователя {context['user_name']} и дай краткие инсайты (максимум 3-4 предложения).

        Данные:
        - Всего практик: {context['total_practices']}
        - Средняя оценка практик: {context['avg_rating']:.1f}/5
        - Текущая серия (streak): {context['user_streak']} дней

        Самые частые состояния:
        {chr(10).join([f"- {m['mood']} ({m['count']} раз)" for m in context['common_moods'][:3]]) if context['common_moods'] else "Нет данных"}

        Частые изменения состояний:
        {chr(10).join([f"- {c['change']} ({c['count']} раз)" for c in context['common_changes'][:3]]) if context['common_changes'] else "Нет данных"}

        Распределение по времени суток:
        - Утро: {context['time_distribution']['morning']} практик
        - День: {context['time_distribution']['afternoon']} практик
        - Вечер: {context['time_distribution']['evening']} практик

        Дай 2-3 кратких инсайта о паттернах пользователя. Будь поддерживающим, но объективным.
        Формат: только текст анализа, без заголовков и маркеров списка.
        """

        # Системный промпт
        system_prompt = """
        Ты помощник по медитации и осознанности. Твоя задача — анализировать данные о практиках пользователя
        и давать краткие, полезные инсайты о их паттернах.

        Будь:
        - Поддерживающим и эмпатичным
        - Конкретным и основанным на данных
        - Кратким (2-4 предложения)
        - Полезным для самопознания

        Не используй маркеры списка, просто дай текст анализа.
        """

        # Отправляем запрос в LLM
        response = await chat_with_context(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=300
        )

        return response

    except OpenRouterError as e:
        logger.exception("Ошибка OpenRouter: %s", e)
        return None
    except Exception as e:
        logger.exception("Ошибка при генерации LLM анализа: %s", e)
        return None
