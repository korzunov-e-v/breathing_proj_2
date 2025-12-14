# src/app_tasks.py
import asyncio
from datetime import datetime, timedelta
import logging
from typing import List, Tuple

from sqlalchemy import func, or_
from telegram.ext import ContextTypes

from src.database import SessionLocal
from src.models import Emotion, Mood, NotificationLog, NotificationType, Phrase, User
from src.telegram_utils import send_text_with_buttons


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
        asyncio.create_task(self._reminder_scheduler())
        asyncio.create_task(self._emotion_notification_scheduler())

    async def _daily_scheduler(self):
        """Ежедневные уведомления в установленное время"""
        while True:
            try:
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                today = now.date()

                self.logger.debug(f"Проверка ежедневных уведомлений: {current_time}")

                db = SessionLocal()
                try:
                    # Шаг 1: Находим пользователей, у которых время практики сейчас
                    potential_users = db.query(User).filter(
                        User.practice_time.isnot(None),
                        User.notification_paused == False
                    ).all()

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
                        if user.notification_paused:
                            skip_reasons['paused'] += 1
                            continue

                        if not user.practice_time:
                            skip_reasons['no_practice_time'] += 1
                            continue

                        # Проверяем, подходит ли время (±1 минута)
                        user_time = user.practice_time
                        if not (user_time == current_time or
                                user_time == (now - timedelta(minutes=1)).strftime("%H:%M") or
                                user_time == (now + timedelta(minutes=1)).strftime("%H:%M")):
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
                            f"Отправка ежедневного уведомления пользователю {user.tg_id} (время: {user.practice_time})")
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
            db = SessionLocal()
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
🧘 *Доброе утро!*

Сегодня {day_text} вашего дыхательного путешествия.
Время практики: *{user.practice_time}*

{phrase_text}

Готовы начать день с осознанного дыхания?
"""

            keyboard = [
                [{"text": "🧘 Начать практику", "callback_data": "daily_practice"}],
                [{"text": "⏰ Перенести на позже", "callback_data": "delay_practice"}],
                [{"text": "🔕 Выключить уведомления", "callback_data": "pause_notifications"}]
            ]

            # Отправляем сообщение
            await send_text_with_buttons(
                update=None,
                context=self.app,
                text=text,
                buttons=keyboard,
                chat_id=user.tg_id
            )

            # Логируем отправку
            db = SessionLocal()
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

    async def _reminder_scheduler(self):
        """Умные напоминания о практике"""
        while True:
            try:
                db = SessionLocal()
                try:
                    now = datetime.now()
                    today = now.date()

                    self.logger.debug(f"Проверка напоминаний: {now.strftime('%H:%M:%S')}")

                    # ==================== СБРОС НАПОМИНАНИЙ ====================
                    reset_count = 0
                    if now.hour == 0 and now.minute == 5:
                        # В 00:05 каждый день сбрасываем ВСЕХ пользователей с заморозкой
                        users_with_freeze = db.query(User).filter(
                            User.freeze_reminders == True
                        ).all()

                        reset_count = len(users_with_freeze)
                        for user in users_with_freeze:
                            user.freeze_reminders = False
                            user.reminder_count_today = 0

                        if reset_count > 0:
                            db.commit()
                            self.logger.info(f"Сброшены напоминания для {reset_count} пользователей в 00:05")

                    # ==================== ОТПРАВКА НАПОМИНАНИЙ ====================
                    # Находим ВСЕХ потенциальных пользователей
                    all_users = db.query(User).filter(
                        User.notification_paused == False,
                        User.practice_time.isnot(None)
                    ).all()

                    self.logger.info(f"Всего активных пользователей: {len(all_users)}")

                    skip_stats = {
                        'freeze_reminders': 0,
                        'practiced_today': 0,
                        'no_practice_time': 0,
                        'paused': 0
                    }

                    users_for_reminders = []

                    for user in all_users:
                        # Проверяем причины пропуска
                        if user.freeze_reminders:
                            skip_stats['freeze_reminders'] += 1
                            continue

                        if user.notification_paused:
                            skip_stats['paused'] += 1
                            continue

                        if not user.practice_time:
                            skip_stats['no_practice_time'] += 1
                            continue

                        # Проверяем, практиковался ли сегодня
                        if user.last_practice_at and user.last_practice_at.date() == today:
                            skip_stats['practiced_today'] += 1
                            continue

                        users_for_reminders.append(user)

                    # Логируем статистику
                    self.logger.info(
                        f"Статистика напоминаний: "
                        f"Всего: {len(all_users)}, "
                        f"На проверку: {len(users_for_reminders)}, "
                        f"Пропущено: {sum(skip_stats.values())} "
                        f"(заморожены: {skip_stats['freeze_reminders']}, "
                        f"практиковались: {skip_stats['practiced_today']}, "
                        f"нет времени: {skip_stats['no_practice_time']}, "
                        f"приостановлены: {skip_stats['paused']})"
                    )

                    # Отправляем напоминания
                    sent_count = 0
                    for user in users_for_reminders:
                        if await self._check_and_send_reminder(user.id):
                            sent_count += 1

                    if sent_count > 0:
                        self.logger.info(f"Отправлено {sent_count} напоминаний")
                    else:
                        self.logger.debug("Напоминаний для отправки нет")

                finally:
                    db.close()
                await asyncio.sleep(60)  # Проверяем каждые 1 минуту
            except Exception as e:
                self.logger.error(f"Ошибка в reminder_scheduler: {e}")
                await asyncio.sleep(600)

    async def _check_and_send_reminder(self, user_id: int):
        """Проверяет и отправляет напоминание"""
        # Проверяем, не заморожены ли напоминания
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_id).first()
        if user.freeze_reminders:
            self.logger.debug(f"Пользователь {user.tg_id}: напоминания заморожены")
            return False
        try:
            # Расписание напоминаний (часы_ожидания, текст)
            reminder_schedule: List[Tuple[int, str]] = [
                (1, "Через 1 час после запланированного времени"),
                (3, "Через 3 часа после запланированного времени"),
                (6, "Через 6 часов после запланированного времени"),
                (12, "Через 12 часов после запланированного времени")
            ]

            current_reminder = user.reminder_count_today

            # Если все напоминания отправлены - замораживаем
            if current_reminder >= len(reminder_schedule):
                user.freeze_reminders = True
                db.commit()
                return

            # Получаем запланированное время практики
            if not user.practice_time:
                return

            # Преобразуем время практики в datetime для сегодня
            practice_time_str = user.practice_time
            try:
                practice_hour, practice_minute = map(int, practice_time_str.split(':'))
            except ValueError:
                return

            now = datetime.now()
            today_practice_time = datetime(
                year=now.year,
                month=now.month,
                day=now.day,
                hour=practice_hour,
                minute=practice_minute
            )

            # Вычисляем, когда должно быть отправлено текущее напоминание
            hours_to_wait, message = reminder_schedule[current_reminder]
            reminder_time = today_practice_time + timedelta(hours=hours_to_wait)

            # Проверяем, настало ли время для напоминания
            if now < reminder_time:
                return

            # Проверяем, не отправляли ли уже это напоминание сегодня
            if user.last_reminder_sent_at:
                # Получаем дату последнего напоминания
                last_reminder_date = user.last_reminder_sent_at.date()

                # Если сегодня уже отправляли напоминание
                if last_reminder_date == now.date():
                    # Проверяем, соответствует ли время последнего напоминания
                    # времени ожидаемого напоминания для текущего счетчика
                    last_reminder_time = user.last_reminder_sent_at
                    expected_time = today_practice_time + timedelta(hours=hours_to_wait)

                    # Если последнее напоминание было отправлено в пределах 30 минут от ожидаемого времени
                    # для текущего счетчика, значит это напоминание уже отправлено
                    if abs((last_reminder_time - expected_time).total_seconds()) < 1800:  # 30 минут
                        return

            # Проверяем, не практиковался ли пользователь уже после времени, когда должно было быть это напоминание
            if user.last_practice_at and user.last_practice_at.date() == now.date():
                if user.last_practice_at > reminder_time - timedelta(minutes=5):
                    # Пользователь уже практиковался, пропускаем напоминание и увеличиваем счетчик
                    user.reminder_count_today = current_reminder + 1
                    db.commit()
                    return

            # Отправляем напоминание
            reminder_text = f"""
    🔔 *Напоминание о практике*

    {message}

    Не пропускайте свою практику - она важна для вашего благополучия!
    """

            await send_text_with_buttons(
                update=None,
                context=self.app,
                text=reminder_text,
                buttons=[
                    [{"text": "🧘 Сделать практику сейчас", "callback_data": "daily_practice"}],
                    [{"text": "⏰ Напомнить позже", "callback_data": "remind_later"}],
                    [{"text": "✋ Сегодня не смогу", "callback_data": "skip_today"}]
                ],
                chat_id=user.tg_id
            )

            # Обновляем счетчик
            user.reminder_count_today = current_reminder + 1
            user.last_reminder_sent_at = now
            db.commit()

            self.logger.info(
                f"Отправлено напоминание #{current_reminder + 1} пользователю {user.tg_id} (время практики: {user.practice_time})"
            )
            return True

        except Exception as e:
            self.logger.error(f"Ошибка в check_and_send_reminder для пользователя {user.tg_id}: {e}")
            return False
        finally:
            db.close()

    async def _emotion_notification_scheduler(self):
        """Уведомления для дневника эмоций (в середине дня)"""
        while True:
            try:
                await asyncio.sleep(300)  # Проверяем каждые 5 минут

                now = datetime.now()
                # Время для уведомлений об эмоциях: 14:00-16:00
                if 14 <= now.hour <= 16:
                    db = SessionLocal()
                    try:
                        today = now.date()
                        self.logger.debug(f"Проверка уведомлений об эмоциях: {now.strftime('%H:%M')}")

                        # Все активные пользователи
                        all_users = db.query(User).filter(
                            User.notification_paused == False
                        ).all()

                        self.logger.info(f"Всего активных пользователей для уведомлений об эмоциях: {len(all_users)}")

                        # Пользователи, которые сегодня уже записывали эмоции
                        users_with_emotions = db.query(Emotion.user_id).filter(
                            func.date(Emotion.created_at) == today
                        ).subquery()

                        skip_stats = {
                            'already_logged_today': 0,
                            'already_notified_today': 0,
                            'paused': 0
                        }

                        users_to_notify = []

                        for user in all_users:
                            if user.notification_paused:
                                skip_stats['paused'] += 1
                                continue

                            # Проверяем, записывал ли сегодня эмоции
                            if db.query(Emotion).filter(
                                    Emotion.user_id == user.id,
                                    func.date(Emotion.created_at) == today
                            ).first():
                                skip_stats['already_logged_today'] += 1
                                continue

                            # Проверяем, не отправляли ли уже уведомление сегодня
                            last_emotion_notif = db.query(NotificationLog).filter(
                                NotificationLog.user_id == user.id,
                                NotificationLog.type == NotificationType.emotion,
                                func.date(NotificationLog.sent_at) == today
                            ).first()

                            if last_emotion_notif:
                                skip_stats['already_notified_today'] += 1
                                continue

                            users_to_notify.append(user)

                        # Логируем статистику
                        self.logger.info(
                            f"Статистика уведомлений об эмоциях: "
                            f"Всего: {len(all_users)}, "
                            f"К уведомлению: {len(users_to_notify)}, "
                            f"Пропущено: {sum(skip_stats.values())} "
                            f"(уже записали: {skip_stats['already_logged_today']}, "
                            f"уже уведомлены: {skip_stats['already_notified_today']}, "
                            f"приостановлены: {skip_stats['paused']})"
                        )

                        # Отправляем уведомления
                        sent_count = 0
                        for user in users_to_notify:
                            try:
                                await self._send_emotion_notification(user)
                                sent_count += 1
                            except Exception as e:
                                self.logger.error(
                                    f"Ошибка отправки уведомления об эмоциях пользователю {user.tg_id}: {e}")

                        if sent_count > 0:
                            self.logger.info(f"Отправлено {sent_count} уведомлений об эмоциях")

                    finally:
                        db.close()

            except Exception as e:
                self.logger.error(f"Ошибка в emotion_notification_scheduler: {e}")
                await asyncio.sleep(600)

    async def _send_emotion_notification(self, user: User):
        """Отправка уведомления для записи эмоции"""
        try:
            # Получаем список настроений
            db = SessionLocal()
            moods = db.query(Mood).all()
            db.close()

            # Создаем клавиатуру с эмоциями
            keyboard = []
            row = []
            for i, mood in enumerate(moods):
                row.append(
                    {"text": mood.icon + " " + mood.name,
                     "callback_data": f"log_emotion_{mood.id}"}
                )
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            keyboard.append([{"text": "📝 Записать свою эмоцию", "callback_data": "custom_emotion"}])
            keyboard.append([{"text": "⏰ Напомнить позже", "callback_data": "delay_emotion"}])

            text = """
📖 *Дневник эмоций*

Как вы себя чувствуете в середине дня?
Отметка эмоций поможет лучше понимать свое состояние.
"""

            await send_text_with_buttons(
                update=None,
                context=self.app,
                text=text,
                buttons=keyboard,
                chat_id=user.tg_id
            )

            # Логируем отправку
            db = SessionLocal()
            try:
                log = NotificationLog(
                    user_id=user.id,
                    type=NotificationType.emotion,
                    sent_at=datetime.now()
                )
                db.add(log)
                db.commit()
            finally:
                db.close()

        except Exception as e:
            self.logger.error(f"Ошибка отправки emotion_notification: {e}")


# Функция для запуска из main.py
async def start_scheduler(app):
    """Запуск планировщика задач"""
    scheduler = TaskScheduler(app)
    await scheduler.start()
