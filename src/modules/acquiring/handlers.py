from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.db.database import AsyncSessionLocal
from src.db.models import Product, ProductType, User
from src.modules.acquiring.service import (
    AcquiringService,
    ProductNotFoundError,
    ProductNotAvailableError,
)
from src.modules.menu_renderer import replace_menu_message
from src.modules.settings.profile_utils import ensure_user_profile

SECTION = "additional_practices"
UD_AP_CAT2 = "ap_cat2_map"


async def buy_additional_practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ctx: UserContextData = context.user_data
    query = update.callback_query
    data = query.data  # buy_ap_<token2>
    token2 = data.replace("buy_ap_", "", 1)

    ap_cat2_state: dict = context.chat_data.get(UD_AP_CAT2, {})
    cat1 = ap_cat2_state.get("cat1")
    cat2_map: dict[str, str] = ap_cat2_state.get("map", {})
    cat2 = cat2_map.get(token2)

    if not cat1 or not cat2:
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text="Не удалось определить практику. Откройте раздел заново.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]
            ),
            media_files=None,
        )
        return

    async with AsyncSessionLocal() as db:
        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()

        user_phone = user.phone
        user_email = user.email

        if not user:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Пользователь не найден в базе.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]
                ),
                media_files=None,
            )
            return
        if not await ensure_user_profile(update, context, user):
            return
        product_result = await db.execute(
            select(Product).where(
                Product.product_type == ProductType.additional_practice,
                Product.section == SECTION,
                Product.category_1 == cat1,
                Product.category_2 == cat2,
                Product.is_active.is_(True),
            )
        )
        product = product_result.scalar_one_or_none()

        if not product:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Для этой практики пока не создан товар.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]
                ),
                media_files=None,
            )
            return
        service = AcquiringService(db)

        try:
            checkout = await service.create_checkout(
                user=user,
                product_code=product.code,
                user_phone=user_phone,
                user_email=user_email,
            )
        except ProductNotFoundError:
            text = "Товар не найден."
        except ProductNotAvailableError:
            text = "Эта практика уже куплена или недоступна."
        else:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=(
                    f"🧘 *{cat1}*\n\n"
                    f"*{cat2}*\n\n"
                    f"Стоимость: {product.price_value / 100:.2f} ₽\n\n"
                    f"[Перейти к оплате]({checkout.confirmation_url})"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]
                ),
                media_files=None,
            )
            return

    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]
        ),
        media_files=None,
    )


async def _get_active_premium_product(db):
    result = await db.execute(
        select(Product).where(
            Product.product_type == ProductType.premium_lifetime,
            Product.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def show_subscription_offer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id if query and query.message else update.effective_chat.id
    async with AsyncSessionLocal() as db:
        product = await _get_active_premium_product(db)

    if not product:
        await replace_menu_message(
            chat_id=chat_id,
            context=context,
            text="Подписка пока недоступна. Попробуйте позже.",
            buttons=[{"text": "🔙 Назад", "goto": "menu"}],
            media_files=None,
        )
        return

    description = product.description or (
        "Открой доступ к ежедневным премиум практикам, аудио и поддержке."
    )
    price_text = f"{product.price_value / 100:.2f} ₽"
    text = (
        f"✨ <b>{product.title or 'Полный доступ'}</b>\n\n"
        f"{description}\n\n"
        f"Стоимость: {price_text}"
    )
    buttons = [
        {"text": "✨ Купить доступ", "goto": "buy_subscription"},
        {"text": "🔙 Назад", "goto": "menu"},
    ]
    await replace_menu_message(
        chat_id=chat_id,
        context=context,
        text=text,
        buttons=buttons,
        media_files=None,
    )


async def buy_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id if query and query.message else update.effective_chat.id

    async with AsyncSessionLocal() as db:
        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await replace_menu_message(
                chat_id=chat_id,
                context=context,
                text="Пользователь не найден в базе.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
                ),
                media_files=None,
            )
            return

        if not await ensure_user_profile(update, context, user):
            return

        product = await _get_active_premium_product(db)
        if not product:
            await replace_menu_message(
                chat_id=chat_id,
                context=context,
                text="Подписка пока недоступна. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
                ),
                media_files=None,
            )
            return

        service = AcquiringService(db)
        try:
            checkout = await service.create_checkout(
                user=user,
                product_code=product.code,
                user_phone=user.phone,
                user_email=user.email,
            )
        except ProductNotFoundError:
            text = "Товар не найден."
        except ProductNotAvailableError:
            text = "Подписка уже оформлена или недоступна."
        else:
            price_text = f"{product.price_value / 100:.2f} ₽"
            link = checkout.confirmation_url
            link_text = (
                f'<a href="{link}">Перейти к оплате</a>' if link else "Ссылка на оплату появится в чате."
            )
            await replace_menu_message(
                chat_id=chat_id,
                context=context,
                text=(
                    f"✨ <b>{product.title or 'Полный доступ'}</b>\n\n"
                    f"Стоимость: {price_text}\n\n"
                    f"{link_text}"
                ),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
                ),
                media_files=None,
            )
            return

    await replace_menu_message(
        chat_id=chat_id,
        context=context,
        text=text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
        ),
        media_files=None,
    )
