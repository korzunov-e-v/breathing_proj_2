from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.db.database import AsyncSessionLocal
from src.db.models import Video, User
from src.modules.acquiring.access import AccessService
from src.modules.library.constants import is_charges_topic
from src.modules.menu_renderer import replace_menu_message


async def show_video_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории (топики) видео из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video.category_1)
            .where(Video.section == "library")
            .distinct()
            .order_by(Video.category_1)
        )
        categories = result.scalars().all()

        buttons = [
            [InlineKeyboardButton(cat, callback_data=f"video_category_{cat}")]
            for cat in categories
            if cat and cat
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
            text="🎞 Киноплёнки\n\nВыбери категорию:",
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )


async def show_video_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список видео в выбранной категории"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("video_category_", "", 1)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video)
            .where(
                Video.category_1 == category,
                Video.section == "library"
            )
            .order_by(Video.id)
        )
        videos = result.scalars().all()

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

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)

        buttons = []
        has_locked_premium = False
        for video in videos:
            has_access = bool(user) and await access_service.has_video_access(
                user.id,
                video.id,
            )
            prefix = "$ " if video.premium and not has_access else "▶️ "
            callback_data = f"video_{video.id}"

            video_title = "Премиум контент" if video.premium and not has_access else getattr(video, "title", None) or f"Видео {video.id}"
            description = f"{prefix}{video_title}"
            if len(description) > 40:
                description = description[:37] + "..."
            if video.premium and not has_access:
                has_locked_premium = True

            buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_videos")])

        text = f"🎞 {category}\n\nВыбери видео:"
        if has_locked_premium:
            text += "\n\n$ - видео доступны по подписке"

        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )


async def show_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает выбранное видео (или блокирует премиум без подписки)"""
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data
    if user_data.state == UserState.WAITING_DONATION_AMOUNT:
        user_data.clear_donation_state()

    video_id = int(query.data.replace("video_", "", 1))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = result.scalars().first()
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

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)
        has_access = bool(user) and await access_service.has_video_access(
            user.id,
            video.id,
        )

        video_title = getattr(video, "title", None) or f"Видео {video.id}"
        category = getattr(video, "category", None)
        primary_category = video.category_1 or category
        category_display = primary_category or "Видео"
        category_callback = f"video_category_{primary_category}" if primary_category else "library_videos"

        donation_buttons = []
        if is_charges_topic(video.category_1, video.category_2, primary_category):
            donation_buttons.append(
                [InlineKeyboardButton("💛 Поддержать донатом", callback_data=f"donate_video_{video.id}")]
            )

        if video.premium and not has_access:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"🎞 {category_display}\n\n🔒 Это видео доступно только после покупки.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Купить видео", callback_data=f"buy_video_{video.id}")],
                        [InlineKeyboardButton("🔙 Назад к видео", callback_data=category_callback)]
                    ]
                ),
                media_files=None,
            )
            return

        description = getattr(video, "description", None) or ""
        text = f"🎞 {video_title}"
        if description:
            text += f"\n\n{description}"

        buttons = donation_buttons + [
            [InlineKeyboardButton("🔙 Назад к видео", callback_data=category_callback)]
        ]

        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=[video.video_id],
        )
