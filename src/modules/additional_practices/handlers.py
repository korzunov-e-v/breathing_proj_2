from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import Video, Music, Texts  # проверь имена моделей
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
    with SessionLocal() as db:
        categories = (
            db.query(Video.category_1)
            .filter(Video.section == SECTION)
            .distinct()
            .order_by(Video.category_1)
            .all()
        )

    cat1_values = [r[0] for r in categories if r and r[0]]

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

    with SessionLocal() as db:
        cat2_rows = (
            db.query(Video.category_2)
            .filter(Video.section == SECTION, Video.category_1 == cat1)
            .distinct()
            .order_by(Video.category_2)
            .all()
        )

    cat2_values = [r[0] for r in cat2_rows if r and r[0]]

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
    """контент по (cat1, cat2): видео -> аудио (по одному) -> текст через replace_menu_message"""
    data = update.callback_query.data  # "ap_cat2_<token2>"
    token2 = data.replace("ap_cat2_", "", 1)

    ap_cat2_state: dict = context.chat_data.get(UD_AP_CAT2, {})
    cat1 = ap_cat2_state.get("cat1")
    cat2_map: dict[str, str] = ap_cat2_state.get("map", {})
    cat2 = cat2_map.get(token2)

    if not cat1 or not cat2:
        return await show_additional_practices(update, context)

    chat_id = update.effective_chat.id

    with SessionLocal() as db:
        videos = (
            db.query(Video)
            .filter(Video.section == SECTION, Video.category_1 == cat1, Video.category_2 == cat2)
            .order_by(Video.id)
            .all()
        )
        audios = (
            db.query(Music)  # у тебя Music
            .filter(Music.section == SECTION, Music.category_1 == cat1, Music.category_2 == cat2)
            .order_by(Music.id)
            .all()
        )
        texts = (
            db.query(Texts)
            .filter(Texts.section == SECTION, Texts.category_1 == cat1, Texts.category_2 == cat2)
            .order_by(Texts.id)
            .all()
        )

    # 1) Отправляем видео по одному
    for v in videos:
        fid = getattr(v, "video_id", None)
        if not fid:
            continue
        caption = getattr(v, "title", None) or ""
        # если хочешь — добавь description в caption
        await context.bot.send_video(
            chat_id=chat_id,
            video=fid,
            caption=caption[:1024] if caption else None,
        )

    # 2) Отправляем аудио по одному
    for a in audios:
        fid = getattr(a, "audio_id", None) or getattr(a, "file_id", None)
        if not fid:
            continue
        title = getattr(a, "title", None) or None
        performer = getattr(a, "artist", None) or None  # если есть
        caption = getattr(a, "description", None) or None

        await context.bot.send_audio(
            chat_id=chat_id,
            audio=fid,
            title=title,
            performer=performer,
            caption=(caption[:1024] if caption else None),
        )

    # 3) Тексты собираем и показываем через replace_menu_message
    text_parts: list[str] = []
    for t in texts:
        title = getattr(t, "title", None)
        body = (
            getattr(t, "content", None)
            or getattr(t, "body", None)
            or getattr(t, "text", None)
            or ""
        ).strip()

        if title and body:
            text_parts.append(f"*{title}*\n{body}")
        elif body:
            text_parts.append(body)

    header = f"🧘 {cat1}\n\n*{cat2}*"
    full_text = header + (("\n\n" + "\n\n— — —\n\n".join(text_parts)) if text_parts else "")

    # Если вообще ничего нет — напишем явным текстом
    if not videos and not audios and not text_parts:
        full_text += "\n\nПока нет контента в этой подкатегории."

    buttons = [
        [InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")],
    ]

    await replace_menu_message(
        chat_id=chat_id,
        context=context,
        text=full_text,
        reply_markup=InlineKeyboardMarkup(buttons),
        media_files=None,  # важно: тут уже не шлем медиа пачкой
        # если replace_menu_message поддерживает parse_mode — лучше прокинуть:
        # parse_mode=ParseMode.MARKDOWN
    )
