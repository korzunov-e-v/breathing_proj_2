from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import Music, User
from src.modules.acquiring.access import AccessService
from src.modules.menu_renderer import replace_screen


async def show_music_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории музыки из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Music.category_1)
            .where(Music.section == "library")
            .distinct()
        )
        categories = result.scalars().all()

        buttons = [
            [InlineKeyboardButton(cat, callback_data=f"music_category_{cat}")]
            for cat in categories if cat
        ]
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        await replace_screen(
            chat_id=update.effective_chat.id,
            context=context,
            text="🎶 Звуки и вибрации\n\nВыбери категорию:",
            reply_markup=InlineKeyboardMarkup(buttons),
            media=None,
        )


async def show_music_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает музыку в выбранной категории"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("music_category_", "")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Music).where(
                Music.category_1 == category,
                Music.section == "library"
            )
        )
        music_tracks = result.scalars().all()
        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)

        buttons = []
        has_locked_premium = False
        for music in music_tracks:
            has_access = bool(user) and await access_service.has_music_access(
                user.id,
                music.id,
            )
            prefix = "$ " if music.premium and not has_access else ""
            callback_data = f"music_{music.id}"

            # Создаем описание для трека
            music_title = "Премиум контент" if music.premium and not has_access else music.title
            description = f"{prefix}{music_title}"
            buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])
            if music.premium and not has_access:
                has_locked_premium = True

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_sounds")])

        text = f"🎶 {category}\n\nВыбери трек:"
        if has_locked_premium:
            text += "\n\n$ - треки доступны по подписке"

        await replace_screen(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media=None,
        )


async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню с музыкой с возможностью воспроизведения"""
    query = update.callback_query
    await query.answer()

    music_id = int(query.data.replace("music_", ""))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Music).where(
                Music.id == music_id,
                Music.section == "library"
            )
        )
        music = result.scalars().first()

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)
        has_access = bool(user) and await access_service.has_music_access(
            user.id,
            music.id,
        )
        category_callback = f"music_category_{music.category}" if music.category else "library_sounds"

        # Определяем доступность трека
        if music.premium and not has_access:
            text = f"🎶 {music.category or 'Музыка'}\n\n🔒 Этот трек доступен только после покупки."
            buttons = [
                [InlineKeyboardButton("✨ Купить трек", callback_data=f"buy_music_{music.id}")],
                [InlineKeyboardButton("🔙 Назад к трекам", callback_data=category_callback)]
            ]

            await replace_screen(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                media=None,
            )
        else:
            # Доступный трек - отправляем аудио напрямую
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=music.audio_id
            )
