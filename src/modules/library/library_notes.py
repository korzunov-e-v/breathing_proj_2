from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import Article, User
from src.modules.menu_renderer import replace_screen


async def _is_user_subscribed(user_id):
    with SessionLocal() as db:
        user: User = db.query(User).filter(User.tg_id == user_id).first()
        if user and user.subscribed:
            return True
        return False


async def show_library_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    with SessionLocal() as db:
        categories = db.query(Article.category).distinct().all()

        buttons = [
            [InlineKeyboardButton(cat[0], callback_data=f"article_category_{cat[0]}")]
            for cat in categories if cat[0]
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
    with SessionLocal() as db:
        articles = db.query(Article).filter(Article.category == category).all()

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
    with SessionLocal() as db:
        article = db.query(Article).filter(Article.id == article_id).first()

        if article:
            # Проверяем подписку для премиум статей
            user_id = update.effective_user.id
            is_subscribed = await _is_user_subscribed(user_id)

            if article.premium and not is_subscribed:
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

        db.close()
