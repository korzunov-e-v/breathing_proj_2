from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import MiniPractice, User
from src.modules.acquiring.access import AccessService
from src.modules.menu_renderer import replace_menu_message


async def show_mini_practices_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все мини-практики из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MiniPractice).order_by(MiniPractice.id)
        )
        practices = result.scalars().all()

        if not practices:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="🌬 Мини-практики\n\nПока нет доступных практик.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔙 Назад", callback_data="library")]
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
        has_lifetime = bool(user) and await access_service.has_premium(user.id)
        if not has_lifetime:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=(
                    "🌬 Мини-практики\n\n"
                    "Мини-практики становятся доступны только после покупки lifetime-подписки."
                ),
                buttons=[
                    {"text": "✨ Купить lifetime", "goto": "subscription_offer"},
                    {"text": "🔙 Назад", "goto": "library"},
                ],
                media_files=None,
            )
            return

        # Формируем кнопки для практик
        buttons = []
        for practice in practices:
            callback_data = f"minipractice_{practice.id}"
            title = practice.title or f"Практика {practice.id}"
            buttons.append([InlineKeyboardButton(title, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        text = "🌬 Мини-практики\n\nВыберите практику:"

        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )


async def show_mini_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает мини-практику"""
    query = update.callback_query
    await query.answer()

    practice_id = int(query.data.replace("minipractice_", ""))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(MiniPractice).where(MiniPractice.id == practice_id)
        )
        practice: MiniPractice | None = result.scalars().first()

        # Проверяем доступ к практике
        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)
        has_lifetime = bool(user) and await access_service.has_premium(user.id)

        if not has_lifetime:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=(
                    f"*🌬 Практика {practice.id} - {practice.title}*\n\n"
                    "🔒 Мини-практики открываются после покупки lifetime-подписки."
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Купить lifetime", callback_data="subscription_offer")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="library_practices")]
                    ]
                ),
                media_files=None,
            )
            return
        # Показываем практику с аудио
            # Показываем практику с аудио
        text = f"*🌬 Практика {practice.id} - {practice.title}*"

        buttons = [
            [InlineKeyboardButton("🔙 Назад к практикам", callback_data="library_practices")]
        ]

        # Отправляем аудио практики
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=[practice.audio_id],
        )
