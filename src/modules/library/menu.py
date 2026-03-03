from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.context import UserContextData
from src.db.database import SessionLocal
from src.db.models import Image
from src.modules.menu_renderer import cleanup_practice_messages, replace_screen


async def show_library_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await cleanup_practice_messages(chat_id, context)

    user_data: UserContextData = context.user_data
    user_data.clear_practice_data()

    text = """
*📚 Заметки Кабира*

Здесь собраны следы пути.  
Слова, звуки и образы —  
то, к чему можно возвращаться в разных состояниях.

Иногда достаточно строки.  
Иногда — дыхания, музыки или тишины между ними.

Выбирай не умом, а ощущением.
    """

    # Клавиатура для библиотеки
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✍️ Заметки", callback_data="library_notes")],
            [InlineKeyboardButton("🎶 Звуки и вибрации", callback_data="library_sounds")],
            [InlineKeyboardButton("🎞 Киноплёнки", callback_data="library_videos")],
            [InlineKeyboardButton("🌬 Мини-практики", callback_data="library_practices")],
            [InlineKeyboardButton("🌌 В тишину", callback_data="menu")],
        ]
    )
    with SessionLocal() as db:
        try:
            image: Image = db.query(Image).filter(Image.title == "Меню").first()
            main_menu_image = image.image_id
        finally:
            db.close()

    media = ""
    await replace_screen(
        chat_id=chat_id,
        context=context,
        text=text,
        reply_markup=keyboard,
        animation=main_menu_image,
    )
