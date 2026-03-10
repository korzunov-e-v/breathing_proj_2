from html import escape
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.context import UserContextData
from src.db.database import AsyncSessionLocal
from src.db.models import (
    Article,
    EntitlementType,
    MiniPractice,
    Music,
    Product,
    ProductType,
    User,
    UserEntitlement,
    Video,
)
from src.modules.acquiring import queries
from src.modules.acquiring.service import (
    AcquiringService,
    ProductNotFoundError,
    ProductNotAvailableError,
)
from src.modules.acquiring.access import AccessService
from src.modules.menu_renderer import replace_menu_message
from src.modules.settings.profile_utils import ensure_user_profile

SECTION = "additional_practices"
UD_AP_CAT2 = "ap_cat2_map"
ENTITLEMENT_LABELS = {
    EntitlementType.premium_lifetime: "Лайфтайм",
    EntitlementType.article_access: "Доступ к статье",
    EntitlementType.music_access: "Доступ к музыке",
    EntitlementType.video_access: "Доступ к видео",
    EntitlementType.mini_practice_access: "Доступ к мини-практике",
    EntitlementType.image_access: "Доступ к изображениям",
    EntitlementType.text_access: "Доступ к текстам",
    EntitlementType.additional_practice_access: "Дополнительные практики",
}


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


async def buy_article(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    article_id = int(query.data.replace("buy_article_", "", 1))
    async with AsyncSessionLocal() as db:
        article_result = await db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = article_result.scalars().first()
        back_callback = (
            f"article_category_{article.category}"
            if article and article.category
            else "library_notes"
        )

        if not article:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Статья не найдена.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        product = await _get_active_content_product(
            db,
            product_type=ProductType.article,
            filters={"article_id": article.id},
        )
        if not product:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Для этой статьи пока не создан товар.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Пользователь не найден в базе.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        if not await ensure_user_profile(update, context, user):
            return

        item_title = article.title or f"Статья {article.id}"
        await _process_content_checkout(
            update=update,
            context=context,
            db=db,
            user=user,
            product=product,
            item_title=item_title,
            back_callback=back_callback,
        )


async def buy_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    music_id = int(query.data.replace("buy_music_", "", 1))
    async with AsyncSessionLocal() as db:
        music_result = await db.execute(
            select(Music).where(Music.id == music_id)
        )
        music = music_result.scalars().first()
        back_callback = (
            f"music_category_{music.category}"
            if music and music.category
            else "library_sounds"
        )

        if not music:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Трек не найден.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        product = await _get_active_content_product(
            db,
            product_type=ProductType.music,
            filters={"music_id": music.id},
        )
        if not product:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Этот трек пока не доступен к покупке.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Пользователь не найден в базе.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        if not await ensure_user_profile(update, context, user):
            return

        item_title = music.title or f"Трек {music.id}"
        await _process_content_checkout(
            update=update,
            context=context,
            db=db,
            user=user,
            product=product,
            item_title=item_title,
            back_callback=back_callback,
        )


async def buy_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    video_id = int(query.data.replace("buy_video_", "", 1))
    async with AsyncSessionLocal() as db:
        video_result = await db.execute(
            select(Video).where(Video.id == video_id)
        )
        video = video_result.scalars().first()

        if not video:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Видео не найдено.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
                ),
                media_files=None,
            )
            return

        category_key = getattr(video, "category", None)
        back_callback = (
            f"video_category_{category_key}"
            if category_key
            else "library_videos"
        )

        product = await _get_active_content_product(
            db,
            product_type=ProductType.video,
            filters={"video_id": video.id},
        )
        if not product:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Это видео пока не доступно к покупке.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Пользователь не найден в базе.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        if not await ensure_user_profile(update, context, user):
            return

        item_title = getattr(video, "title", None) or f"Видео {video.id}"
        await _process_content_checkout(
            update=update,
            context=context,
            db=db,
            user=user,
            product=product,
            item_title=item_title,
            back_callback=back_callback,
        )


async def buy_minipractice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    practice_id = int(query.data.replace("buy_minipractice_", "", 1))
    async with AsyncSessionLocal() as db:
        practice_result = await db.execute(
            select(MiniPractice).where(MiniPractice.id == practice_id)
        )
        practice = practice_result.scalars().first()
        back_callback = "library_practices"

        if not practice:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Практика не найдена.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        product = await _get_active_content_product(
            db,
            product_type=ProductType.mini_practice,
            filters={"mini_practice_id": practice.id},
        )
        if not product:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Эта мини-практика пока не доступна к покупке.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Пользователь не найден в базе.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
                ),
                media_files=None,
            )
            return

        access_service = AccessService(db)
        if not await access_service.has_premium(user.id):
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=(
                    "*🌬 Мини-практики*\n\nМини-практики доступны после покупки lifetime-подписки.\n"
                    "Открой полный доступ, чтобы продолжить."
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("✨ Купить lifetime", callback_data="subscription_offer")],
                        [InlineKeyboardButton("🔙 Назад", callback_data="library_practices")],
                    ]
                ),
                media_files=None,
            )
            return

        if not await ensure_user_profile(update, context, user):
            return

        item_title = practice.title or f"Практика {practice.id}"
        await _process_content_checkout(
            update=update,
            context=context,
            db=db,
            user=user,
            product=product,
            item_title=item_title,
            back_callback=back_callback,
        )


async def _get_active_premium_product(db):
    result = await db.execute(
        select(Product).where(
            Product.product_type == ProductType.premium_lifetime,
            Product.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _get_active_content_product(
    db,
    *,
    product_type: ProductType,
    filters: dict[str, int],
) -> Product | None:
    stmt = select(Product).where(
        Product.product_type == product_type,
        Product.is_active.is_(True),
    )
    for column_name, value in filters.items():
        stmt = stmt.where(getattr(Product, column_name) == value)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _build_checkout_text(
    *,
    item_title: str,
    product: Product,
    checkout,
    extra_description: str | None = None,
) -> str:
    description_parts: list[str] = []
    description = extra_description or product.description
    if description:
        description_parts.append(description)
    price_text = f"{product.price_value / 100:.2f} ₽"
    description_parts.append(f"Стоимость: {price_text}")
    link_text = (
        f"[Перейти к оплате]({checkout.confirmation_url})"
        if checkout.confirmation_url
        else "Ссылка для оплаты пока недоступна."
    )
    description_parts.append(link_text)
    body = "\n\n".join(description_parts)
    return f"✨ *{item_title}*\n\n{body}"


async def _process_content_checkout(
    *,
    update,
    context,
    db,
    user: User,
    product: Product,
    item_title: str,
    back_callback: str,
    extra_description: str | None = None,
) -> bool:
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
        text = f"{item_title} уже куплен или недоступен."
    else:
        text = _build_checkout_text(
            item_title=item_title,
            product=product,
            checkout=checkout,
            extra_description=extra_description,
        )
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
            ),
            media_files=None,
        )
        return True

    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Назад", callback_data=back_callback)]]
        ),
        media_files=None,
    )
    return False


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


def _entitlement_display_name(entitlement: UserEntitlement) -> str:
    return ENTITLEMENT_LABELS.get(
        entitlement.entitlement_type,
        entitlement.entitlement_type.value.replace("_", " ").capitalize(),
    )


def _format_entitlement_line(entitlement: UserEntitlement) -> str:
    parts = [escape(_entitlement_display_name(entitlement))]
    product_title = (entitlement.product.title or "").strip() if entitlement.product else ""
    if product_title:
        parts.append(escape(product_title))

    status = "активен" if entitlement.is_active else "неактивен"
    granted = entitlement.granted_at.strftime("%d.%m.%Y") if entitlement.granted_at else "дата неизвестна"
    line = f"• {' — '.join(parts)} (<i>{status}</i>, куплено {granted}"
    if entitlement.expires_at:
        expires = entitlement.expires_at.strftime("%d.%m.%Y")
        line += f", действует до {expires}"
    line += ")"
    return line


def _build_entitlements_text(
    entitlements: list[UserEntitlement],
    lifetime_active: bool,
) -> str:
    lines = [
        "✨ <b>Глубже в путешествие</b>",
        "Здесь видно состояние lifetime-подписок и других приобретённых доступов.",
        "",
    ]

    if entitlements:
        lines.append("<b>Ваши покупки:</b>")
        lines.extend(_format_entitlement_line(ent) for ent in entitlements)
    else:
        lines.append("Пока нет оформленных покупок.")

    lines.append("")
    lines.append(
        "<b>Лайфтайм:</b> "
        + ("куплен и активен." if lifetime_active else "ещё не оформлен.")
    )
    return "\n".join(lines)


async def show_subscription_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                buttons=[{"text": "🔙 Назад", "goto": "menu"}],
                media_files=None,
            )
            return

        entitlements = await queries.get_user_entitlements(db, user.id)

    lifetime_active = any(
        ent.entitlement_type == EntitlementType.premium_lifetime and ent.is_active
        for ent in entitlements
    )

    text = _build_entitlements_text(entitlements, lifetime_active)
    buttons = []
    if not lifetime_active:
        buttons.append({"text": "✨ Купить lifetime", "goto": "subscription_offer"})
    buttons.append({"text": "🔙 В моё пространство", "goto": "menu"})

    await replace_menu_message(
        chat_id=chat_id,
        context=context,
        text=text,
        buttons=buttons,
        media_files=None,
    )
