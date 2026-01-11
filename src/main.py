import asyncio
import logging

import yaml
from telegram import (
    Update,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)

from src.app_tasks import start_scheduler
from src.db.database import create_tables, SessionLocal
from src.db.models import User
from src.log import log_interaction, setup_logging
from src.modules.menu_renderer import show_menu_by_name
from src.modules.onboarding.onboarding import send_onboarding
from src.modules.practice.mood import ask_mood_after_practice, handle_mood_selection
from src.modules.practice.pract import (
    handle_practice_completion,
    handle_repeat_practice_selection,
    handle_restart_practices,
    show_daily_practice,
    show_practice_again,
)
from src.modules.practice.rate import (
    ask_feedback_rating,
    handle_comment_skip,
    handle_comment_text,
    handle_rating_selection,
)
from src.modules.settings.notifications import pause_notifications_handler
from src.modules.reminders.reminders import skip_today_handler, remind_later_handler
from src.modules.settings.time import handle_change_time, handle_time_selection
from src.settings import settings
from src.telegram_utils import receive_media


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с логированием"""
    await log_interaction(update, "START_COMMAND")

    user = update.effective_user
    _chat_id = update.effective_chat.id

    # Сохраняем/обновляем пользователя в БД
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.tg_id == user.id).first()
        if not db_user:
            db_user = User(
                tg_id=user.id,
                username=user.username,
                current_day=1,
                streak=0
            )
            db.add(db_user)
            db.commit()
            logging.info(f"Создан новый пользователь: {user.username} (ID: {user.id})")

            # Онбординг для нового пользователя
            await send_onboarding(update, context, db_user)
        else:
            logging.info(f"Пользователь уже существует: {user.username}")
            # Показываем главное меню из YAML для существующего пользователя
            await show_menu_by_name(update, context, "menu")
    finally:
        db.close()


def register_handlers(app: Application):
    """Регистрирует только статичные меню из YAML, исключая динамические"""
    with open("data/menu.yaml", "r", encoding='utf-8') as f:
        data = yaml.safe_load(f)

    if "main-menu" not in data:
        raise Exception("No 'main-menu' section in data/menu.yaml")

    # Меню, которые обрабатываются отдельно (не регистрируем их здесь)
    excluded_menus = {
        "daily_practice", "change_time", "practice_again", "all_practices"
    }

    data = data["main-menu"]

    logging.info(f"Найдены меню для регистрации: {list(data.keys())}")

    for menu_name, menu_data in data.items():
        if menu_name in excluded_menus:
            logging.info(f"Пропускаем регистрацию меню: {menu_name}")
            continue

        def make_handler(name=menu_name):
            async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await log_interaction(update, f"MENU_NAVIGATION", f"Menu: {name}")
                return await show_menu_by_name(update, context, name, query=update.callback_query)
            return handler

        # Регистрируем команду и callback
        app.add_handler(CommandHandler(menu_name, make_handler()))
        app.add_handler(CallbackQueryHandler(make_handler(), pattern=f"^{menu_name}$"))

    return app


def main():
    create_tables()
    app = ApplicationBuilder().token(settings.bot_token).build()
    setup_logging()

    logging.info("🤖 Бот запущен и готов к работе!")

    # Существующие обработчики...
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, receive_media))

    # Обработчики для динамических меню
    app.add_handler(CallbackQueryHandler(handle_change_time, pattern="^change_time$"))
    app.add_handler(CallbackQueryHandler(handle_time_selection, pattern="^set_time_"))
    app.add_handler(CallbackQueryHandler(handle_practice_completion, pattern="^practice_complete$"))
    app.add_handler(CallbackQueryHandler(ask_mood_after_practice, pattern="^ask_mood_after$"))
    app.add_handler(CallbackQueryHandler(handle_restart_practices, pattern="^restart_practices$"))

    # Обработчики для настроений
    app.add_handler(CallbackQueryHandler(handle_mood_selection, pattern="^mood_"))

    # Обработчики для фидбека
    app.add_handler(CallbackQueryHandler(handle_rating_selection, pattern="^rating_"))
    app.add_handler(CallbackQueryHandler(ask_feedback_rating, pattern="^ask_feedback_rating$"))
    app.add_handler(CallbackQueryHandler(handle_comment_skip, pattern="^skip_comment$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment_text), group=103, )

    # Практики
    app.add_handler(CallbackQueryHandler(show_daily_practice, pattern="^daily_practice$"))
    app.add_handler(CommandHandler("practice", show_daily_practice))
    app.add_handler(CallbackQueryHandler(show_practice_again, pattern="^practice_again$"))
    app.add_handler(CallbackQueryHandler(handle_repeat_practice_selection, pattern="^repeat_practice_"))

    app.add_handler(CallbackQueryHandler(remind_later_handler, pattern="^remind_later$"))
    app.add_handler(CallbackQueryHandler(skip_today_handler, pattern="^skip_today$"))
    app.add_handler(CallbackQueryHandler(pause_notifications_handler, pattern="^pause_notifications$"))

    # Регистрируем статичные меню из YAML (библиотека, статьи, музыка и т.д.)
    register_handlers(app)

    # После запуска бота запускаем планировщик
    async def on_startup(application):
        asyncio.create_task(start_scheduler(application))

    app.post_init = on_startup

    app.run_polling()


if __name__ == '__main__':
    main()
