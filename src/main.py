import asyncio
import logging

from sqlalchemy import select
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    filters,
    MessageHandler,
)
from telegram.ext import ContextTypes

from src.context import UserContextData, context_types
from src.db.database import create_tables, AsyncSessionLocal
from src.db.models import User
from src.log import log_interaction, setup_logging
from src.modules.acquiring.polling import poll_pending_payments
from src.modules.feedback.handlers import handle_feedback_message
from src.modules.llm.chat import handle_chat_message
from src.modules.menu_renderer import show_main_menu
from src.modules.onboarding.onboarding import send_onboarding
from src.modules.practice.rate import handle_comment_text
from src.modules.reminders.tasks import start_scheduler
from src.modules.settings.contacts import handle_contact, handle_email
from src.modules.settings.time import handle_change_time
from src.router import router
from src.settings import settings
from src.telegram_utils import receive_media


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await log_interaction(update, "START_COMMAND")

    user = update.effective_user
    _chat_id = update.effective_chat.id

    user_data: UserContextData = context.user_data
    user_data.clear_practice_data()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == user.id)
        )
        db_user: User | None = result.scalars().first()

        if not db_user:
            db_user = User(
                tg_id=user.id,
                username=user.username,
                current_day=1,
                streak=0
            )
            db.add(db_user)
            await db.commit()

            logging.info(f"Создан новый пользователь: {user.username} (ID: {user.id})")

            await send_onboarding(update, context)
        else:
            logging.info(f"Пользователь уже существует: {user.username}")
            await show_main_menu(update, context)


def main():
    create_tables()
    app = ApplicationBuilder().token(settings.bot_token).context_types(context_types).build()
    setup_logging()

    logging.info("🤖 Бот запущен и готов к работе!")

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact), group=100)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email), group=101)
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.Document.ALL, receive_media))
    app.add_handler(CallbackQueryHandler(router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_message), group=103)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_comment_text), group=104, )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_time), group=105, )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message), group=106, )
    # После запуска бота запускаем планировщик
    async def on_startup(application):
        asyncio.create_task(start_scheduler(application))
        asyncio.create_task(poll_pending_payments(AsyncSessionLocal, application))
    app.post_init = on_startup
    app.run_polling()


if __name__ == '__main__':
    main()
