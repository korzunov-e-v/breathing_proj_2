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
        practice_access: dict[int, bool] = {}
        for practice in practices:
            practice_access[practice.id] = bool(user) and await access_service.has_mini_practice_access(
                user.id,
                practice.id,
            )

        # Формируем кнопки для практик
        buttons = []
        for practice in practices:
            has_access = practice_access.get(practice.id, False)
            prefix = "$ " if practice.premium and not has_access else "🌀 "
            callback_data = f"minipractice_{practice.id}"

            practice_title = "Премиум контент" if practice.premium and not has_access else practice.title
            description = f"{prefix}{practice_title}"

            if len(description) > 40:
                description = description[:37] + "..."

            buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        has_locked_premium = any(
            p.premium and not practice_access.get(p.id, False)
            for p in practices
        )

        text = "🌬 Мини-практики\n\nВыберите практику:"
        if has_locked_premium:
            text += "\n\n$ - практики доступны по подписке"

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
        has_access = bool(user) and await access_service.has_mini_practice_access(
            user.id,
            practice.id,
        )

        if practice.premium and not has_access:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"*🌬 Практика {practice.id} - {practice.title}*\n\n🔒 Эта практика доступна только после покупки.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Купить практику", callback_data=f"buy_minipractice_{practice.id}")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="library_practices")]
                    ]
                ),
                media_files=None,
            )
        else:
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
