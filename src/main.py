import logging
import yaml

from telegram import (
    Update,
    InputMediaPhoto,
    InputMediaVideo,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    Application, MessageHandler, filters
)

from src.settings import settings

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


# ------------------------------------------------------------
#  У Т И Л И Т Ы
# ------------------------------------------------------------

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:
        # Берем самый большой размер
        file_id = msg.photo[-1].file_id
        await msg.reply_text(f'Photo file_id: <code>{file_id}</code>', parse_mode='HTML')
    elif msg.video:
        file_id = msg.video.file_id
        await msg.reply_text(f"Video file_id: <code>{file_id}<code>", parse_mode="HTML")
    else:
        await msg.reply_text("Пришлите фото или видео.")


async def delete_old_messages(context: ContextTypes.DEFAULT_TYPE):
    """Удаляет старые сообщения меню если они сохранены."""
    msg1 = context.user_data.get("menu_msg_media")
    msg2 = context.user_data.get("menu_msg_buttons")

    chat_id = context.user_data.get("chat_id")
    if not chat_id:
        return

    if msg1:
        try:
            await context.bot.delete_message(chat_id, msg1)
        except:
            pass

    if msg2:
        try:
            await context.bot.delete_message(chat_id, msg2)
        except:
            pass


async def send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    media, text, buttons):

    chat_id = update.effective_chat.id

    # Удаляем старые сообщения
    old = context.user_data.get("menu_messages", [])
    for msg_id in old:
        try:
            await context.bot.delete_message(chat_id, msg_id)
        except:
            pass
    context.user_data["menu_messages"] = []

    # ---------- 1. MEDIA GROUP ----------
    media_group = []

    if media:
        for m in media:
            m_str = str(m).lower()

            # Видео
            if m_str.endswith(".mp4") or m_str.startswith("baac"):
                media_group.append(InputMediaVideo(m))
            # Фото
            else:
                media_group.append(InputMediaPhoto(m))

        sent = await context.bot.send_media_group(chat_id, media=media_group)
        msg_ids = [msg.message_id for msg in sent]
        context.user_data["menu_messages"].extend(msg_ids)

    # ---------- 2. TEXT ----------
    msg_text = await context.bot.send_message(chat_id, text)
    context.user_data["menu_messages"].append(msg_text.message_id)

    # ---------- 3. BUTTONS ----------
    if buttons:
        kb = [
            [InlineKeyboardButton(btn["text"], callback_data=btn["goto"])]
            for btn in buttons
        ]
        markup = InlineKeyboardMarkup(kb)
        msg_btn = await context.bot.send_message(chat_id, "Выберите пункт:", reply_markup=markup)
        context.user_data["menu_messages"].append(msg_btn.message_id)

# ------------------------------------------------------------
#  Р Е Г И С Т Р А Ц И Я   М Е Н Ю
# ------------------------------------------------------------

def register_handlers(app: Application):
    with open("../data/menu.yaml", "r") as f:
        data = yaml.safe_load(f)

    if not "main-menu" in data:
        raise Exception("no 'menu' section in data/menu.yaml")

    data = data["main-menu"]

    for menu_name, menu_data in data.items():
        text = menu_data.get("text", "")
        media = menu_data.get("media", [])
        buttons = menu_data.get("buttons", [])

        def make_handler(name=menu_name, text_=text, media_=media, buttons_=buttons):
            async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
                return await send_menu(
                    update, context,
                    media=media_,
                    text=text_,
                    buttons=buttons_
                )
            return handler

        app.add_handler(CommandHandler(menu_name, make_handler()))
        app.add_handler(CallbackQueryHandler(make_handler(), pattern=f"^{menu_name}$"))

    return app



# ------------------------------------------------------------
#  С Т А Р Т
# ------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Главное меню: /menu")


def main():
    TOKEN = settings.bot_token

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, receive_media))
    register_handlers(app)

    app.run_polling()


if __name__ == "__main__":
    main()
