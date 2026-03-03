from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.db.database import SessionLocal
from src.db.models import Video, User
from src.modules.menu_renderer import replace_menu_message


async def _is_user_subscribed(user_id: int) -> bool:
    """Проверяет подписку пользователя"""
    with SessionLocal() as db:
        try:
            user: User = db.query(User).filter(User.tg_id == user_id).first()
            return bool(user and user.subscribed)
        finally:
            db.close()


async def show_video_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории (топики) видео из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    with SessionLocal() as db:
        try:
            # Важно: предполагается, что у Video есть поле category
            categories = (
                db.query(Video.category)
                .distinct()
                .order_by(Video.category)
                .all()
            )

            buttons = [
                [InlineKeyboardButton(cat[0], callback_data=f"video_category_{cat[0]}")]
                for cat in categories
                if cat and cat[0]
            ]

            if not buttons:
                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text="🎞 Киноплёнки\n\nПока нет доступных категорий.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Назад", callback_data="library")]]
                    ),
                    media_files=None,
                )
                return

            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="🎞 Киноплёнки\n\nВыберите категорию:",
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=None,
            )
        finally:
            db.close()


async def show_video_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список видео в выбранной категории"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("video_category_", "", 1)

    with SessionLocal() as db:
        try:
            videos = (
                db.query(Video)
                .filter(Video.category == category)
                .order_by(Video.id)
                .all()
            )

            if not videos:
                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text=f"🎞 {category}\n\nВ этой категории пока нет видео.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]
                        ]
                    ),
                    media_files=None,
                )
                return

            user_id = update.effective_user.id
            is_subscribed = await _is_user_subscribed(user_id)

            buttons = []
            for video in videos:
                prefix = "$ " if video.premium else "▶️ "
                callback_data = f"video_{video.id}"

                if video.premium and not is_subscribed:
                    video_title = "Премиум контент"
                else:
                    video_title = getattr(video, "title", None) or f"Видео {video.id}"
                description = f"{prefix}{video_title}"
                if len(description) > 40:
                    description = description[:37] + "..."

                buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_videos")])

            text = f"🎞 {category}\n\nВыберите видео:"
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
    """Показывает выбранное видео (или блокирует премиум без подписки)"""
    query = update.callback_query
    await query.answer()

    video_id = int(query.data.replace("video_", "", 1))

    with SessionLocal() as db:
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text="🎞 Видео не найдено.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
                    ),
                    media_files=None,
                )
                return

            user_id = update.effective_user.id
            is_subscribed = await _is_user_subscribed(user_id)

            video_title = getattr(video, "title", None) or f"Видео {video.id}"
            category = getattr(video, "category", None) or "Видео"

            if video.premium and not is_subscribed:
                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text=f"*🎞 Премиум контент*\n\n🔒 Это видео доступно только по подписке.",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [InlineKeyboardButton("✨ Подписка", callback_data="subscription")],
                            [InlineKeyboardButton("🔙 Назад к видео", callback_data=f"video_category_{category}")]
                        ]
                    ),
                    media_files=None,
                )
                return

            description = getattr(video, "description", None) or ""
            text = f"*🎞 {video_title}*"
            if description:
                text += f"\n\n{description}"

            buttons = [
                [InlineKeyboardButton("🔙 Назад к видео", callback_data=f"video_category_{category}")]
            ]

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=[video.video_id],
            )
        finally:
            db.close()
