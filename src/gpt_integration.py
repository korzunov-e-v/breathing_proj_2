# src/gpt_integration.py
import logging
from typing import List, Dict, Any
import openai
from datetime import datetime, timedelta

from src.database import SessionLocal
from src.models import Emotion, PracticeLog, User
from src.settings import settings


class GPTAnalyzer:
    """Класс для анализа данных через GPT"""

    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.openai_api_key)
        self.logger = logging.getLogger(__name__)

    async def analyze_emotion_patterns(self, user_id: int) -> str:
        """Анализ паттернов эмоций пользователя"""
        db = SessionLocal()
        try:
            # Получаем эмоции за последние 30 дней
            thirty_days_ago = datetime.now() - timedelta(days=30)
            emotions = db.query(Emotion).filter(
                Emotion.user_id == user_id,
                Emotion.created_at >= thirty_days_ago
            ).order_by(Emotion.created_at).all()

            if not emotions:
                return "У вас пока недостаточно данных для анализа. Продолжайте записывать эмоции!"

            # Формируем данные для GPT
            emotion_data = []
            for emotion in emotions:
                emotion_data.append(
                    {
                        "date": emotion.created_at.strftime("%Y-%m-%d %H:%M"),
                        "emotion": emotion.emotion_name,
                        "note": emotion.note or ""
                    }
                )

            # Промпт для GPT
            prompt = f"""
            Проанализируй эмоциональные паттерны пользователя на основе следующих данных:

            {emotion_data}

            Сделай краткий анализ (3-4 предложения):
            1. Какие эмоции преобладают?
            2. Есть ли заметные закономерности?
            3. Какие рекомендации можно дать?

            Будь добрым и поддерживающим. Пиши на русском.
            """

            # Вызов GPT
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты психолог-консультант, который помогает анализировать эмоциональные паттерны."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"Ошибка в analyze_emotion_patterns: {e}")
            return "Временно не могу провести анализ. Продолжайте отслеживать эмоции!"
        finally:
            db.close()

    async def generate_personalized_advice(self, user_id: int) -> str:
        """Генерирует персонализированные советы на основе практик и эмоций"""
        db = SessionLocal()
        try:
            # Получаем последние практики
            practices = db.query(PracticeLog).filter(
                PracticeLog.user_id == user_id
            ).order_by(PracticeLog.completed_at.desc()).limit(10).all()

            # Получаем последние эмоции
            emotions = db.query(Emotion).filter(
                Emotion.user_id == user_id
            ).order_by(Emotion.created_at.desc()).limit(10).all()

            if not practices and not emotions:
                return "Продолжайте практиковать и отслеживать эмоции для получения персонализированных советов!"

            # Формируем данные
            practice_data = []
            for p in practices:
                practice_data.append(
                    {
                        "date": p.completed_at.strftime("%Y-%m-%d") if p.completed_at else "",
                        "mood_before": p.mood_before,
                        "mood_after": p.mood_after,
                        "rating": p.feedback_rating
                    }
                )

            emotion_data = []
            for e in emotions:
                emotion_data.append(
                    {
                        "date": e.created_at.strftime("%Y-%m-%d") if e.created_at else "",
                        "emotion": e.emotion_name
                    }
                )

            # Промпт для GPT
            prompt = f"""
            На основе данных пользователя дай персональный совет по практике дыхания:

            Последние практики:
            {practice_data}

            Последние эмоции:
            {emotion_data}

            Дай 1-2 конкретных рекомендации:
            1. Какие практики стоит повторить или попробовать?
            2. Как интегрировать дыхание в ежедневную рутину?

            Будь конкретным и доброжелательным. Пиши на русском.
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты эксперт по дыхательным практикам и mindfulness."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"Ошибка в generate_personalized_advice: {e}")
            return "Совет дня: Регулярная практика дыхания помогает снизить стресс и улучшить концентрацию."
        finally:
            db.close()


# Создаем глобальный экземпляр
# gpt_analyzer = GPTAnalyzer()


# Функции для импорта
async def analyze_emotion_patterns(user_id: int) -> str:
    return "No gpt yet"
    # return await gpt_analyzer.analyze_emotion_patterns(user_id)


async def generate_personalized_advice(user_id: int) -> str:
    return "No gpt yet"
    # return await gpt_analyzer.generate_personalized_advice(user_id)