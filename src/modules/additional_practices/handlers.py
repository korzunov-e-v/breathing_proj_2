from __future__ import annotations

from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import Video, Music, TextItem, User
from src.modules.acquiring.access import AccessService
from src.modules.library.tools import is_user_subscribed
from src.modules.menu_renderer import replace_menu_message

SECTION = "additional_practices"

# ключи в context.chat_data
UD_AP_CAT1 = "ap_cat1_map"
UD_AP_CAT2 = "ap_cat2_map"


def _tok(i: int) -> str:
    # токен короткий и гарантированно влезает
    return str(i)


async def show_additional_practices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """category_1"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video.category_1)
            .where(Video.section == SECTION)
            .distinct()
            .order_by(Video.category_1)
        )
        categories = result.scalars().all()

    cat1_values = [r for r in categories]

    if not cat1_values:
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text="🧘 Доп. практики\n\nПока нет доступных категорий.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]),
            media_files=None,
        )
        return

    # маппинг token -> category_1
    cat1_map = {_tok(i): name for i, name in enumerate(cat1_values)}
    context.chat_data[UD_AP_CAT1] = cat1_map

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"ap_cat1_{token}")]
        for token, name in cat1_map.items()
    ]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="menu")])

    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text="🧘 Доп. практики\n\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(buttons),
        media_files=None,
    )


async def show_additional_practices_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """category_2 внутри выбранной category_1"""
    data = update.callback_query.data  # "ap_cat1_<token>"
    token = data.replace("ap_cat1_", "", 1)

    cat1_map: dict[str, str] = context.chat_data.get(UD_AP_CAT1, {})
    cat1 = cat1_map.get(token)
    if not cat1:
        # если маппинг потерялся (перезапуск/другая сессия) — вернемся на начало
        return await show_additional_practices(update, context)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Video.category_2)
            .where(
                Video.section == SECTION,
                Video.category_1 == cat1
            )
            .distinct()
            .order_by(Video.category_2)
        )
        cat2_rows = result.scalars().all()

    cat2_values = [r for r in cat2_rows]

    if not cat2_values:
        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=f"🧘 {cat1}\n\nПока нет подкатегорий.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]),
            media_files=None,
        )
        return

    # маппинг token2 -> category_2 (на уровне выбранной cat1)
    cat2_map = {_tok(i): name for i, name in enumerate(cat2_values)}
    context.chat_data[UD_AP_CAT2] = {"cat1": cat1, "map": cat2_map}

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"ap_cat2_{t2}")]
        for t2, name in cat2_map.items()
    ]
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")])

    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=f"🧘 {cat1}\n\nВыберите практику:",
        reply_markup=InlineKeyboardMarkup(buttons),
        media_files=None,
    )


async def show_additional_practice_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    token2 = data.replace("ap_cat2_", "", 1)

    ap_cat2_state: dict = context.chat_data.get(UD_AP_CAT2, {})
    cat1 = ap_cat2_state.get("cat1")
    cat2_map: dict[str, str] = ap_cat2_state.get("map", {})
    cat2 = cat2_map.get(token2)

    if not cat1 or not cat2:
        return await show_additional_practices(update, context)

    chat_id = update.effective_chat.id
    user_tg_id = update.effective_user.id

    async with AsyncSessionLocal() as db:
        user_result = await db.execute(
            select(User).where(User.tg_id == user_tg_id)
        )
        user = user_result.scalar_one_or_none()
        access_service = AccessService(db)

        has_full_access = await access_service.has_additional_practice_access(
            user_id=user.id,
            section=SECTION,
            category_1=cat1,
            category_2=cat2,
        )

        videos_result = await db.execute(
            select(Video)
            .where(
                Video.section == SECTION,
                Video.category_1 == cat1,
                Video.category_2 == cat2,
            )
            .order_by(Video.id)
        )
        videos = videos_result.scalars().all()

        audios_result = await db.execute(
            select(Music)
            .where(
                Music.section == SECTION,
                Music.category_1 == cat1,
                Music.category_2 == cat2,
            )
            .order_by(Music.id)
        )
        audios = audios_result.scalars().all()

        texts_result = await db.execute(
            select(TextItem)
            .where(
                TextItem.section == SECTION,
                TextItem.category_1 == cat1,
                TextItem.category_2 == cat2,
            )
            .order_by(TextItem.id)
        )
        texts = texts_result.scalars().all()

    def _is_premium(obj) -> bool:
        return bool(getattr(obj, "premium", False))

    has_any_premium = any(_is_premium(x) for x in (videos + audios + texts))
    has_any_free = any(not _is_premium(x) for x in (videos + audios + texts))

    # Всё премиум и доступа нет — блокируем
    if (videos or audios or texts) and (not has_full_access) and (not has_any_free):
        await replace_menu_message(
            chat_id=chat_id,
            context=context,
            text="*🧘 Премиум контент*\n\n🔒 Эта практика доступна только после покупки.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✨ Купить практику", callback_data=f"buy_ap_{token2}")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")],
                ]
            ),
            media_files=None,
        )
        return

    # Нет полного доступа — показываем только бесплатное
    if not has_full_access:
        videos_to_send = [v for v in videos if not _is_premium(v)]
        audios_to_send = [a for a in audios if not _is_premium(a)]
        texts_to_show = [t for t in texts if not _is_premium(t)]
    else:
        videos_to_send = videos
        audios_to_send = audios
        texts_to_show = texts

    for v in videos_to_send:
        fid = getattr(v, "video_id", None)
        if not fid:
            continue
        caption = getattr(v, "title", None) or ""
        await context.bot.send_video(
            chat_id=chat_id,
            video=fid,
            caption=caption[:1024] if caption else None,
        )

    for a in audios_to_send:
        fid = getattr(a, "audio_id", None) or getattr(a, "file_id", None)
        if not fid:
            continue

        title = getattr(a, "title", None) or None
        performer = getattr(a, "artist", None) or None
        caption = getattr(a, "description", None) or None

        await context.bot.send_audio(
            chat_id=chat_id,
            audio=fid,
            title=title,
            performer=performer,
            caption=(caption[:1024] if caption else None),
        )

    text_parts: list[str] = []
    for t in texts_to_show:
        body = (t.text or "").strip()
        if body:
            text_parts.append(body)

    header = f"🧘 {cat1}\n\n*{cat2}*"
    full_text = header + (("\n\n" + "\n\n— — —\n\n".join(text_parts)) if text_parts else "")

    if not videos_to_send and not audios_to_send and not text_parts:
        full_text += "\n\nПока нет доступного контента в этой подкатегории."
        if has_any_premium and not has_full_access:
            full_text += "\n\n🔒 Часть материалов доступна после покупки."

    if has_any_premium and not has_full_access:
        full_text += "\n\n🔒 Часть материалов доступна после покупки."

    buttons = [
        [InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")],
    ]
    if has_any_premium and not has_full_access:
        buttons.insert(0, [InlineKeyboardButton("✨ Купить практику", callback_data=f"buy_ap_{token2}")])

    await replace_menu_message(
        chat_id=chat_id,
        context=context,
        text=full_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        media_files=None,
    )
