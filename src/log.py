import logging
import sys

from telegram import Update


async def log_interaction(update: Update, interaction_type: str, additional_info: str = ""):
    """Логирует все взаимодействия с ботом"""
    user = update.effective_user
    chat = update.effective_chat

    user_info = f"UserID: {user.id}, Username: @{user.username}" if user else "Unknown user"
    chat_info = f"ChatID: {chat.id}, Type: {chat.type}" if chat else "Unknown chat"

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

    logging.info(log_message)


# Настройка расширенного логирования
def setup_logging():
    """Настраивает логирование в файл и stdout"""
    # Создаем логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Обработчик для файла
    file_handler = logging.FileHandler('bot.log', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    # Обработчик для stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    # Очищаем существующие обработчики и добавляем новые
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    # Устанавливаем уровень для httpx
    logging.getLogger("httpx").setLevel(logging.WARNING)
