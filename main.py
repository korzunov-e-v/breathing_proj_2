import asyncio
import logging
from telegram import (
    Update,
    InputMediaPhoto,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(level=logging.INFO)


# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Набери /media")


# --- Команда /media ---
async def send_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Список медиа — можно собирать динамически
    media = [
        InputMediaPhoto("FILE_ID_1"),
        InputMediaPhoto("FILE_ID_2"),
        # InputMediaVideo("FILE_ID_3"),
    ]

    # 1) отправляем группу
    await context.bot.send_media_group(
        chat_id=chat_id,
        media=media,
    )

    # 2) создаём клавиатуру
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
        [InlineKeyboardButton("🔄 Обновить", callback_data="refresh")],
    ])

    # 3) отправляем сообщение с кнопками
    await context.bot.send_message(
        chat_id=chat_id,
        text="Выберите действие:",
        reply_markup=markup
    )


# --- Callback обработчик кнопок ---
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        await query.edit_message_text("Вы нажали Назад")
    elif query.data == "refresh":
        await query.edit_message_text("Обновлено!")


# --- Запуск приложения ---
def main():
    TOKEN = "YOUR_TOKEN_HERE"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("media", send_media))
    app.add_handler(
        # обработчик callback-кнопок
        telegram.ext.CallbackQueryHandler(callbacks)
    )

    app.run_polling()


if __name__ == "__main__":
    main()
