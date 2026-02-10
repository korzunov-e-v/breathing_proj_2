from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.db.database import SessionLocal
from src.db.models import Video, User
from src.modules.menu_renderer import replace_menu_message


async def _is_user_subscribed(user_id):
    """Проверяет подписку пользователя"""
    db = SessionLocal()
    try:
        user: User = db.query(User).filter(User.tg_id == user_id).first()
        return user and user.subscribed
    finally:
        db.close()


async def show_video_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все видео из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    db = SessionLocal()
    try:
        videos = db.query(Video).order_by(Video.id).all()

        if not videos:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="🎞 Киноплёнки\n\nПока нет доступных видео.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔙 Назад", callback_data="library")]
                    ]
                ),
                media_files=None,
            )
            return

        # Проверяем подписку пользователя
        user_id = update.effective_user.id
        is_subscribed = await _is_user_subscribed(user_id)

        # Формируем кнопки для видео
        buttons = []
        for video in videos:
            # Если видео премиум и пользователь не подписан, показываем заблокированным
            prefix = "$ " if video.premium else "▶️ "
            callback_data = f"video_{video.id}"

            # Создаем описание для видео
            video_title = f"Видео {video.id}"
            if hasattr(video, 'title') and video.title:
                video_title = video.title

            description = f"{prefix}{video_title}"
            if len(description) > 40:
                description = description[:37] + "..."

            buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        text = "🎞 Киноплёнки\n\nВыберите видео:"
        if any(v.premium for v in videos) and not is_subscribed:
            text += "\n\n$ - видео доступны по подписке"

        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )
    finally:
        db.close()


async def show_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает видео"""
    query = update.callback_query
    await query.answer()

    video_id = int(query.data.replace("video_", ""))

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()

        # Проверяем подписку
        user_id = update.effective_user.id
        is_subscribed = await _is_user_subscribed(user_id)

        if video.premium and not is_subscribed:
            video_title = f"Видео {video.id}"
            if hasattr(video, 'title') and video.title:
                video_title = video.title

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"*🎞 {video_title}*\n\n🔒 Это видео доступно только по подписке.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Подписка", callback_data="subscription")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]
                    ]
                ),
                media_files=None,
            )
        else:
            video_title = f"Видео {video.id}"
            if hasattr(video, 'title') and video.title:
                video_title = video.title

            description = ""
            if hasattr(video, 'description') and video.description:
                description = f"\n\n{video.description}"

            text = f"*🎞 {video_title}*{description}"

            buttons = [
                [InlineKeyboardButton("🔙 Назад к видео", callback_data="library_videos")]
            ]

            # Отправляем видео
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=[video.video_id],
            )

    finally:
        db.close()
