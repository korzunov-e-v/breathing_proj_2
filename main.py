import asyncio
import logging
import yaml
from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    Application,
)
import telegram


logging.basicConfig(level=logging.INFO)


# --------------------------- SEND MEDIA ---------------------------

async def send_media_group_and_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       media, text, buttons):
    chat_id = update.effective_chat.id

    # 1. отправка media group (если список медиа)
    if media and isinstance(media, list):
        media_group = []
        for m in media:
            # автоматически определяем тип
            if str(m).startswith("BAAC"):  # пример file_id видео
                media_group.append(InputMediaVideo(m))
            else:
                media_group.append(InputMediaPhoto(m))

        await context.bot.send_media_group(chat_id=chat_id, media=media_group)

    # 2. кнопки
    if buttons:
        keyboard = [
            [InlineKeyboardButton(btn["text"], callback_data=btn["goto"])]
            for btn in buttons
        ]
        markup = InlineKeyboardMarkup(keyboard)
    else:
        markup = None

    # 3. текстовое сообщение с кнопками
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)


# --------------------------- YAML HANDLERS ---------------------------

async def register_handlers(app: Application):
    with open("data/menu.yaml", "r") as f:
        data = yaml.safe_load(f)

    for menu_name, menu_data in data.items():
        text = menu_data.get("text", "")
        images = menu_data.get("images", [])
        buttons = menu_data.get("buttons", [])

        def make_handler(name=menu_name, text_=text, images_=images, buttons_=buttons):
            async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await send_media_group_and_buttons(
                    update, context,
                    media=images_,
                    text=text_,
                    buttons=buttons_
                )
            return handler

        # команда /menu_name
        app.add_handler(CommandHandler(menu_name, make_handler()))

        # кнопки callback_data = goto
        app.add_handler(CallbackQueryHandler(make_handler(), pattern=f"^{menu_name}$"))

    return app


# --------------------------- MAIN ---------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню: /menu")


async def main():
    TOKEN = "8206130717:AAEPRFbSAnvQdttbZ1EpYwsZtI6cO4I5njg"

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app = await register_handlers(app)

    app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
