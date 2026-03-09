from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import Article, User
from src.modules.acquiring.access import AccessService
from src.modules.menu_renderer import replace_screen


async def show_library_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Article.category).distinct()
        )
        categories = result.scalars().all()

        buttons = [
            [InlineKeyboardButton(cat, callback_data=f"article_category_{cat}")]
            for cat in categories if cat
        ]
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        await replace_screen(
            chat_id=update.effective_chat.id,
            context=context,
            text="📚 Выберите категорию:",
            reply_markup=InlineKeyboardMarkup(buttons),
            media=None,
        )


async def show_articles_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статьи категории"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("article_category_", "")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Article).where(Article.category == category)
        )
        articles = result.scalars().all()

        buttons = []
        for article in articles:
            prefix = "$ " if article.premium else ""
            display_title = "Премиум контент" if article.premium else article.title[:40]
            buttons.append(
                [
                    InlineKeyboardButton(
                        f"{prefix}{display_title}",
                        callback_data=f"article_{article.id}"
                    )
                ]
            )

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_notes")])

        await replace_screen(
            chat_id=update.effective_chat.id,
            context=context,
            text=f"Категория: {category}",
            reply_markup=InlineKeyboardMarkup(buttons),
            media=None,
        )


async def show_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статью"""
    query = update.callback_query
    await query.answer()

    article_id = int(query.data.replace("article_", ""))
    async with AsyncSessionLocal() as db:
        article_result = await db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = article_result.scalars().first()

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)

        if article:
            # Проверяем подписку для премиум статей
            has_access = bool(user) and await access_service.has_article_access(
                user.id,
                article.id,
            )

            if article.premium and not has_access:
                text = f"*{article.title}*\n\n🔒 Эта статья доступна только по подписке."
                markup = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Подписка", callback_data="subscription")],
                        [InlineKeyboardButton("🔙 Назад", callback_data=f"article_category_{article.category}")]
                    ]
                )
            else:
                text = f"*{article.title}*\n\n{article.text}"
                markup = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔙 Назад", callback_data=f"article_category_{article.category}")]
                    ]
                )

            await replace_screen(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=markup,
                media=None,
            )
