from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.context import UserContextData
from src.db.database import AsyncSessionLocal
from src.db.models import Image, User
from src.modules.acquiring.access import AccessService
from src.modules.menu_renderer import cleanup_practice_messages, replace_screen


async def show_library_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await cleanup_practice_messages(chat_id, context)

    user_data: UserContextData = context.user_data
    user_data.clear_practice_data()

    text = """
📚 Заметки Кабира

Здесь собраны следы пути.  
Слова, звуки и образы —  
то, к чему можно возвращаться в разных состояниях.

Иногда достаточно строки.  
Иногда — дыхания, музыки или тишины между ними.

Выбирай не умом, а ощущением.
    """
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)
        has_lifetime = bool(user) and await access_service.has_premium(user.id)
    # Клавиатура для библиотеки
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✍️ Заметки", callback_data="library_notes")],
            [InlineKeyboardButton("🎶 Звуки и вибрации", callback_data="library_sounds")],
            [InlineKeyboardButton("🎞 Киноплёнки", callback_data="library_videos")],
            [InlineKeyboardButton("🌬 Мини-практики", callback_data="library_practices")]if has_lifetime else [],
            [InlineKeyboardButton("🌌 В тишину", callback_data="menu")],
        ]
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Image).where(Image.title == "Меню")
        )
        image: Image | None = result.scalars().first()
        main_menu_image = image.image_id

    media = ""
    await replace_screen(
        chat_id=chat_id,
        context=context,
        text=text,
        reply_markup=keyboard,
        animation=main_menu_image,
    )
