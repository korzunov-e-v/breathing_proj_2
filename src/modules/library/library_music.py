from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.db.database import SessionLocal
from src.db.models import Music, User
from src.modules.menu_renderer import replace_screen


async def _is_user_subscribed(user_id):
    """Проверяет подписку пользователя"""
    db = SessionLocal()
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

    db = SessionLocal()
    try:
        categories = db.query(Music.category).distinct().all()

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
    db = SessionLocal()

    try:
        music_tracks = db.query(Music).filter(Music.category == category).all()

        if not music_tracks:
            await replace_screen(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"В категории '{category}' пока нет музыки.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔙 Назад", callback_data="library_sounds")]
                    ]
                ),
                media=None,
            )
            return

        # Проверяем подписку пользователя
        user_id = update.effective_user.id
        is_subscribed = await _is_user_subscribed(user_id)

        buttons = []
        for music in music_tracks:
            # Если трек премиум и пользователь не подписан, показываем заблокированным
            prefix = "$ " if music.premium else ""
            callback_data = f"music_{music.id}"

            # Создаем описание для трека
            description = f"{prefix}Трек {music.id}"
            buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_sounds")])

        text = f"🎶 {category}\n\nВыберите трек:"
        if any(music.premium for music in music_tracks) and not is_subscribed:
            text += "\n\n🔒 - треки доступны по подписке"

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
    """Воспроизводит музыку"""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data.startswith("premium_music_"):
        # Пользователь пытается открыть премиум музыку без подписки
        music_id = int(callback_data.replace("premium_music_", ""))

        db = SessionLocal()
        try:
            music = db.query(Music).filter(Music.id == music_id).first()
            if music:
                await replace_screen(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text=f"🎶 {music.category}\n\n🔒 Этот трек доступен только по подписке.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("✨ Подписка", callback_data="subscription")],
                            [InlineKeyboardButton("🔙 Назад", callback_data=f"music_category_{music.category}")]
                        ]
                    ),
                    media=None,
                )
        finally:
            db.close()
        return

    # Обычная музыка
    music_id = int(callback_data.replace("music_", ""))

    db = SessionLocal()
    try:
        music = db.query(Music).filter(Music.id == music_id).first()

        if not music:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Трек не найден."
            )
            return

        # Проверяем подписку для премиум треков
        user_id = update.effective_user.id
        is_subscribed = await _is_user_subscribed(user_id)

        if music.premium and not is_subscribed:
            await replace_screen(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"🎶 {music.category}\n\n🔒 Этот трек доступен только по подписке.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Подписка", callback_data="subscription")],
                        [InlineKeyboardButton("🔙 Назад", callback_data=f"music_category_{music.category}")]
                    ]
                ),
                media=None,
            )
        else:
            # Отправляем аудио
            try:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=music.audio_id,
                    caption=f"🎶 {music.category}\n\nНаслаждайтесь звуком...",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("🔙 Назад к трекам", callback_data=f"music_category_{music.category}")]
                        ]
                    )
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Не удалось воспроизвести трек. Ошибка: {e}"
                )
    finally:
        db.close()
