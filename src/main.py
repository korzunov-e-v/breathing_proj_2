import asyncio
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    MessageHandler,
)
from telegram.ext import ContextTypes

from src.app_tasks import start_scheduler
from src.db.database import create_tables, SessionLocal
from src.db.models import User
from src.log import log_interaction, setup_logging
from src.modules.menu_renderer import show_main_menu
from src.modules.onboarding.onboarding import send_onboarding
from src.modules.practice.rate import handle_comment_text
from src.modules.settings.time import handle_change_time
from src.router import router
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
            await send_onboarding(update, context)
        else:
            logging.info(f"Пользователь уже существует: {user.username}")
            # Показываем главное меню из YAML для существующего пользователя
            await show_main_menu(update, context)
    finally:
        db.close()


def main():
    create_tables()
    app = ApplicationBuilder().token(settings.bot_token).build()
    setup_logging()

    logging.info("🤖 Бот запущен и готов к работе!")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, receive_media))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment_text), group=104, )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_time), group=104, )

    # После запуска бота запускаем планировщик
    async def on_startup(application):
        asyncio.create_task(start_scheduler(application))

    app.post_init = on_startup
    app.run_polling()


if __name__ == '__main__':
    main()
