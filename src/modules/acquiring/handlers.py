from html import escape
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
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
from src.modules.library.constants import is_charges_topic

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


DONATION_AMOUNTS_RUB = (100, 300, 500, 1000)


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


async def donate_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    video_id = int(query.data.replace("donate_video_", "", 1))
    async with AsyncSessionLocal() as db:
        video_result = await db.execute(select(Video).where(Video.id == video_id))
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

        if not is_charges_topic(video.category_1, video.category_2, getattr(video, "category", None)):
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Донаты доступны только для темы «зарядки и пробуждения».",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
                ),
                media_files=None,
            )
            return

        title = video.title or f"Зарядка {video.id}"
        buttons = [
            [
                InlineKeyboardButton(
                    f"{amount} ₽",
                    callback_data=f"donate_video_amount_{video.id}_{amount}",
                )
            ]
            for amount in DONATION_AMOUNTS_RUB
        ]
        buttons.append(
            [
                InlineKeyboardButton(
                    "🎯 Ввести другую сумму",
                    callback_data=f"donate_video_custom_{video.id}",
                )
            ]
        )
        buttons.append([InlineKeyboardButton("🔙 Назад к видео", callback_data=f"video_{video.id}")])

    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=(
            f"💛 *{title}*\n\n"
            "Выберите сумму доната. Контент остаётся доступным даже без доната."
        ),
        reply_markup=InlineKeyboardMarkup(buttons),
        media_files=None,
    )


async def donate_video_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    video_id = int(query.data.replace("donate_video_custom_", "", 1))
    async with AsyncSessionLocal() as db:
        video_result = await db.execute(select(Video).where(Video.id == video_id))
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

    if not is_charges_topic(video.category_1, video.category_2, getattr(video, "category", None)):
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text="Донаты доступны только для темы «зарядки и пробуждения».",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
            ),
            media_files=None,
        )
        return

    video_title = video.title or f"Зарядка {video.id}"
    user_data: UserContextData = context.user_data
    user_data.state = UserState.WAITING_DONATION_AMOUNT
    user_data.pending_donation_video_id = video.id
    user_data.pending_donation_video_title = video_title

    await _send_custom_donation_prompt(
        update=update,
        context=context,
        video_title=video_title,
        video_id=video.id,
    )


async def donate_video_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    payload = query.data.replace("donate_video_amount_", "", 1)
    try:
        video_id_str, amount_str = payload.split("_", 1)
        video_id = int(video_id_str)
        amount_value_rub = int(amount_str)
    except (ValueError, IndexError):
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text="Не удалось определить сумму доната.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
            ),
            media_files=None,
        )
        return

    if amount_value_rub not in DONATION_AMOUNTS_RUB:
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text="Выбранная сумма недоступна.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
            ),
            media_files=None,
        )
        return

    await _process_donation_checkout(
        update=update,
        context=context,
        video_id=video_id,
        amount_value_kopecks=amount_value_rub * 100,
        amount_label=str(amount_value_rub),
    )


async def handle_custom_donation_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    user_data: UserContextData = context.user_data
    if (
        user_data.state != UserState.WAITING_DONATION_AMOUNT
        or not user_data.pending_donation_video_id
    ):
        return

    amount_text = message.text.strip()
    try:
        parsed_amount = Decimal(amount_text.replace(",", "."))
    except InvalidOperation:
        await _send_custom_donation_prompt(
            update=update,
            context=context,
            video_title=user_data.pending_donation_video_title or "зарядка",
            video_id=user_data.pending_donation_video_id,
            error_text="Не удалось распознать сумму. Введите число в рублях.",
        )
        return

    amount_value = parsed_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount_value < Decimal("1"):
        await _send_custom_donation_prompt(
            update=update,
            context=context,
            video_title=user_data.pending_donation_video_title or "зарядка",
            video_id=user_data.pending_donation_video_id,
            error_text="Минимальная сумма доната — 1 ₽.",
        )
        return

    video_id = user_data.pending_donation_video_id
    amount_value_kopecks = int(
        (amount_value * 100).to_integral_value(rounding=ROUND_HALF_UP)
    )
    amount_label = _format_ruble_amount(amount_value)
    user_data.clear_donation_state()

    await _process_donation_checkout(
        update=update,
        context=context,
        video_id=video_id,
        amount_value_kopecks=amount_value_kopecks,
        amount_label=amount_label,
    )


async def _send_custom_donation_prompt(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    video_title: str,
    video_id: int,
    error_text: str | None = None,
) -> None:
    parts = [f"💛 *{video_title}*"]
    if error_text:
        parts.append(error_text)
    parts.append("Введите сумму доната в рублях. Контент остаётся доступным даже без доната.")
    text = "\n\n".join(parts)

    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=text,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Назад к видео", callback_data=f"video_{video_id}")]]
        ),
        media_files=None,
    )


async def _process_donation_checkout(
    *,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    video_id: int,
    amount_value_kopecks: int,
    amount_label: str,
) -> None:
    async with AsyncSessionLocal() as db:
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalars().first()

        if not video or not is_charges_topic(
            video.category_1,
            video.category_2,
            getattr(video, "category", None),
        ):
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="Это видео не поддерживается донатами.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="library_videos")]]
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
                    [[InlineKeyboardButton("🔙 Назад", callback_data=f"video_{video.id}")]]
                ),
                media_files=None,
            )
            return

        if not await ensure_user_profile(update, context, user):
            return

        product = await _get_or_create_donation_product(
            db=db,
            video=video,
            amount_value=amount_value_kopecks,
        )

        item_title = video.title or f"Зарядка {video.id}"
        extra_description = (
            f"Вы выбрали донат {amount_label} ₽ за зарядку «{item_title}». Спасибо за поддержку!"
        )

        await _process_content_checkout(
            update=update,
            context=context,
            db=db,
            user=user,
            product=product,
            item_title=item_title,
            back_callback=f"video_{video.id}",
            extra_description=extra_description,
        )


def _format_ruble_amount(amount: Decimal) -> str:
    normalized = amount.normalize()
    return format(normalized, "f")


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


async def _get_or_create_donation_product(
    *,
    db,
    video: Video,
    amount_value: int,
) -> Product:
    code = f"donation_video_{video.id}_{amount_value}"

    result = await db.execute(select(Product).where(Product.code == code))
    product = result.scalar_one_or_none()
    if product:
        return product

    title = video.title or f"Зарядка {video.id}"
    description = "Донат для поддержки «зарядки и пробуждения». Спасибо за энергичное начало дня."

    product = Product(
        code=code,
        title=f"Донат: {title}",
        description=description,
        product_type=ProductType.donation,
        price_value=amount_value,
        currency="RUB",
        is_active=True,
        is_repeatable=True,
        section=video.section or "library",
        category_1=video.category_1,
        category_2=video.category_2,
        video_id=video.id,
    )
    db.add(product)
    await db.flush()
    return product


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
