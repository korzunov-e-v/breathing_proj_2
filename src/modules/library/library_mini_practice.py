from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import MiniPractice
from src.modules.library.tools import is_user_subscribed
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

        # Проверяем подписку пользователя
        user_id = update.effective_user.id
        is_subscribed = await is_user_subscribed(user_id)

        # Формируем кнопки для практик
        buttons = []
        for practice in practices:
            # Если практика премиум и пользователь не подписан, показываем заблокированной
            prefix = "$ " if practice.premium else "🌀 "
            callback_data = f"minipractice_{practice.id}"

            # Создаем описание для практики
            practice_title = "Премиум контент" if practice.premium else practice.title
            description = f"{prefix}{practice_title}"

            # Обрезаем если слишком длинное
            if len(description) > 40:
                description = description[:37] + "..."

            buttons.append([InlineKeyboardButton(description, callback_data=callback_data)])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        text = "🌬 Мини-практики\n\nВыберите практику:"
        if any(p.premium for p in practices) and not is_subscribed:
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

        # Проверяем подписку
        user_id = update.effective_user.id
        is_subscribed = await is_user_subscribed(user_id)

        if practice.premium and not is_subscribed:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"*🌬 Практика {practice.id} - {practice.title}*\n\n🔒 Эта практика доступна только по подписке.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Подписка", callback_data="subscription")],
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
