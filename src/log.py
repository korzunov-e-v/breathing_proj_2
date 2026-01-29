import logging
import sys

from telegram import Update


class DefaultExtraFilter(logging.Filter):
    def filter(self, record):
        for k in ("user_id", "chat_id", "callback_data"):
            if not hasattr(record, k):
                setattr(record, k, "-")
        return True


async def log_interaction(update: Update, interaction_type: str, additional_info: str = ""):
    """Логирует все взаимодействия с ботом"""
    user = update.effective_user
    chat = update.effective_chat

    user_info = f"UserID: {user.id}, Username: @{user.username}" if user else "Unknown user"
    chat_info = f"ChatID: {chat.id}" if chat else "Unknown chat"

    if update.message:
        message_info = f"MessageID: {update.message.message_id}, Text: '{update.message.text}'"
    elif update.callback_query:
        message_info = f"CallbackData: '{update.callback_query.data}'"
    else:
        message_info = "No message data"

    log_message = (
        f"🔹 {interaction_type} | {user_info} | {chat_info} | "
        f"{message_info} | {additional_info}"
    )

    app_log = logging.getLogger("app")
    app_log.info(log_message)


def setup_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    # 1) Формат для APP (без extra)
    app_fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 2) Формат для ROUTER (с extra)
    router_fmt = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s "
        "| user_id=%(user_id)s chat_id=%(chat_id)s callback_data=%(callback_data)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- handlers ---
    stream = logging.StreamHandler(sys.stdout)
    stream.setLevel(logging.INFO)
    stream.setFormatter(app_fmt)  # по умолчанию app-формат

    root.addHandler(stream)

    # --- router logger: отдельный handler с другим форматтером ---
    router_logger = logging.getLogger("router")
    router_logger.propagate = False  # чтобы не дублировалось в root
    router_stream = logging.StreamHandler(sys.stdout)
    router_stream.setLevel(logging.INFO)
    router_stream.setFormatter(router_fmt)
    router_stream.addFilter(DefaultExtraFilter())
    router_logger.addHandler(router_stream)

    # (опционально) app logger явно
    app_logger = logging.getLogger("app")
    app_logger.propagate = True  # пусть идёт в root stream/app_fmt

    logging.getLogger("httpx").setLevel(logging.WARNING)
