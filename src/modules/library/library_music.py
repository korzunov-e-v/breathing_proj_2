from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.db.database import SessionLocal
from src.db.models import Music, User
from src.modules.menu_renderer import replace_screen


async def _is_user_subscribed(user_id):
    """Проверяет подписку пользователя"""
    with SessionLocal() as db:
        try:
            user: User = db.query(User).filter(User.tg_id == user_id).first()
            return user and user.subscribed
        finally:
            db.close()


async def show_music_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории музыки из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    with SessionLocal() as db:
        try:
            categories = db.query(Music.category_1).filter(Music.section == 'library').distinct().all()

            buttons = [
                [InlineKeyboardButton(cat[0], callback_data=f"music_category_{cat[0]}")]
                for cat in categories if cat[0]
            ]
            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

            await replace_screen(
                chat_id=update.effective_chat.id,
                context=context,
                text="🎶 Звуки и вибрации\n\nВыберите категорию:",
                reply_markup=InlineKeyboardMarkup(buttons),
                media=None,
            )
        finally:
            db.close()


async def show_music_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает музыку в выбранной категории"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("music_category_", "")
    with SessionLocal() as db:

        try:
            music_tracks = db.query(Music).filter(Music.category_1 == category, Music.section == 'library').all()
            # Проверяем подписку пользователя
            user_id = update.effective_user.id
            is_subscribed = await _is_user_subscribed(user_id)

            buttons = []
            for music in music_tracks:
                # Если трек премиум и пользователь не подписан, показываем заблокированным
                prefix = "$ " if music.premium else ""
                callback_data = f"music_{music.id}"

                # Создаем описание для трека
                music_title = "Премиум контент" if music.premium else music.title
                description = f"{prefix}{music_title}"
                buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_sounds")])

            text = f"🎶 {category}\n\nВыберите трек:"
            if any(music.premium for music in music_tracks) and not is_subscribed:
                text += "\n\n$ - треки доступны по подписке"

            await replace_screen(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                media=None,
            )
        finally:
            db.close()


async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню с музыкой с возможностью воспроизведения"""
    query = update.callback_query
    await query.answer()

    music_id = int(query.data.replace("music_", ""))

    with SessionLocal() as db:
        try:
            music = db.query(Music).filter(Music.id == music_id, Music.section == 'library').first()

            # Проверяем подписку
            user_id = update.effective_user.id
            is_subscribed = await _is_user_subscribed(user_id)

            # Определяем доступность трека
            if music.premium and not is_subscribed:
                # Премиум трек без подписки
                text = f"*🎶 {music.category}*\n\n🔒 Этот трек доступен только по подписке."
                buttons = [
                    [InlineKeyboardButton("✨ Оформить подписку", callback_data="subscription")],
                    [InlineKeyboardButton("🔙 Назад к трекам", callback_data=f"music_category_{music.category}")]
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

        finally:
            db.close()
