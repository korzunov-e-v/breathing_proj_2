import asyncio
import logging
from datetime import datetime, timedelta

import pytz
from sqlalchemy import func

from src.db.database import SessionLocal
from src.db.models import User, NotificationLog, NotificationType, Phrase
from src.modules.menu_renderer import replace_menu_message


# Функция для запуска из main.py
async def start_scheduler(app):
    """Запуск планировщика задач"""
    scheduler = TaskScheduler(app)
    await scheduler.start()


class TaskScheduler:
    """Планировщик периодических задач для бота"""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Запуск планировщика"""
        self.logger.info("🚀 Запуск планировщика задач...")
        logging.warning("Запуск планировщика задач")
        # Создаем задачи
        asyncio.create_task(self._daily_scheduler())

    async def _daily_scheduler(self):
        while True:
            try:
                now = datetime.now(pytz.UTC)
                current_time = now.strftime("%H:%M")
                today = now.date()

                self.logger.debug(f"Проверка ежедневных уведомлений: {current_time}")

                with SessionLocal() as db:
                    try:
                        # Шаг 1: Находим пользователей, у которых время практики сейчас
                        potential_users = db.query(User).filter(User.practice_time.isnot(None)).all()

                        self.logger.info(f"Всего пользователей с настроенным временем: {len(potential_users)}")

                        users_to_notify = []
                        skip_reasons = {
                            'wrong_time': 0,
                            'already_notified_today': 0,
                            'no_practice_time': 0,
                            'paused': 0
                        }

                        for user in potential_users:
                            # Проверяем причину пропуска
                            if user.freeze_reminders:
                                skip_reasons['paused'] += 1
                                continue

                            if not user.practice_time:
                                skip_reasons['no_practice_time'] += 1
                                continue

                            # Проверяем, подходит ли время (±1 минута)
                            user_local_time = user.practice_time  # в базе данных как "11:00"
                            user_gmt_offset = user.timezone  # в базе данных как "5", то есть +5 GMT Yekaterinburg
                            local_time = datetime.strptime(user_local_time, "%H:%M")
                            user_utc_time = (local_time - timedelta(hours=int(user_gmt_offset))).time().strftime("%H:%M")

                            if not (user_utc_time == current_time or
                                    user_utc_time == (now - timedelta(minutes=1)).strftime("%H:%M") or
                                    user_utc_time == (now + timedelta(minutes=1)).strftime("%H:%M")):
                                skip_reasons['wrong_time'] += 1
                                continue

                            # Проверяем, не отправили ли уже уведомление сегодня
                            last_notification = db.query(NotificationLog).filter(
                                NotificationLog.user_id == user.id,
                                NotificationLog.type == NotificationType.daily,
                                func.date(NotificationLog.sent_at) == today
                            ).first()

                            if last_notification:
                                skip_reasons['already_notified_today'] += 1
                                continue

                            users_to_notify.append(user)

                        # Логируем статистику
                        self.logger.info(
                            f"Статистика уведомлений ({current_time}): "
                            f"Всего пользователей: {len(potential_users)}, "
                            f"К уведомлению: {len(users_to_notify)}, "
                            f"Пропущено: {sum(skip_reasons.values())} "
                            f"(приостановлены: {skip_reasons['paused']}, "
                            f"нет времени: {skip_reasons['no_practice_time']}, "
                            f"не время: {skip_reasons['wrong_time']}, "
                            f"уже уведомлены: {skip_reasons['already_notified_today']})"
                        )

                        # Отправляем уведомления
                        for user in users_to_notify:
                            self.logger.info(
                                f"Отправка ежедневного уведомления пользователю {user.tg_id} (время: {user.practice_time})"
                            )
                            await self._send_daily_notification(user)

                        if users_to_notify:
                            self.logger.info(f"Отправлено {len(users_to_notify)} ежедневных уведомлений")

                    finally:
                        db.close()
                await asyncio.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                self.logger.error(f"Ошибка в daily_scheduler: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке

    async def _send_daily_notification(self, user: User):
        """Отправка ежедневного уведомления"""
        try:
            # Текст уведомления
            if user.current_day <= 7:
                day_text = f"День {user.current_day}"
            else:
                day_text = f"Продолжаем практику #{user.current_day}"

            # Случайная фраза дня
            with SessionLocal() as db:
                try:
                    phrases = db.query(Phrase).order_by(func.random())
                    premium_phrases = None
                    if user.subscribed:
                        premium_phrases = phrases.filter(
                            Phrase.for_premium == (user.subscribed if hasattr(user, 'subscribed') else False)
                        ).all()
                    if premium_phrases:
                        phrase = premium_phrases.first()
                    else:
                        phrase = phrases.first()

                    phrase_text = f"\n\n💭 *Фраза дня:*\n{phrase.text}" if phrase else ""
                finally:
                    db.close()

            text = f"""
🧘Твой момент наступил!

🌿 Просто вернись к дыханию.

Сегодня {day_text} вашего дыхательного путешествия.
Время дыхания: *{user.practice_time}*

{phrase_text}

Готовы начать?
"""

            keyboard = [
                {"text": "🧘 Вдох", "goto": "daily_practice"}
            ]

            # Отправляем сообщение
            await replace_menu_message(
                context=self.app,
                text=text,
                buttons=keyboard,
                chat_id=user.tg_id
            )

            # Логируем отправку
            with SessionLocal() as db:
                try:
                    log = NotificationLog(
                        user_id=user.id,
                        type=NotificationType.daily,
                        sent_at=datetime.now()
                    )
                    db.add(log)
                    db.commit()

                    # Обновляем время последнего уведомления
                    user.last_daily_notification_at = datetime.now()
                    db.commit()

                finally:
                    db.close()

        except Exception as e:
            self.logger.error(f"Ошибка отправки daily_notification: {e}")
