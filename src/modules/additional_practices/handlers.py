from __future__ import annotations

from urllib.parse import quote_plus, unquote_plus

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import Video, Music, Texts
from src.modules.menu_renderer import replace_menu_message


SECTION_ADDITIONAL = "additional_practices"

# --- callback helpers ---

def _enc(s: str) -> str:
    return quote_plus(s)

def _dec(s: str) -> str:
    return unquote_plus(s)

def _cb_cat1(cat1: str) -> str:
    return f"ap_cat1:{_enc(cat1)}"

def _cb_cat2(cat1: str, cat2: str) -> str:
    return f"ap_cat2:{_enc(cat1)}|{_enc(cat2)}"

def _parse_cat1(data: str) -> str:
    # data = "ap_cat1:<cat1>"
    return _dec(data.split(":", 1)[1])

def _parse_cat2(data: str) -> tuple[str, str]:
    # data = "ap_cat2:<cat1>|<cat2>"
    payload = data.split(":", 1)[1]
    a, b = payload.split("|", 1)
    return _dec(a), _dec(b)


# --- 1) уровень: category_1 ---

async def show_additional_practices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает category_1 для additional_practices"""
    query = update.callback_query
    if query:
        await query.answer()

    with SessionLocal() as db:
        try:
            cat1_rows = (
                db.query(Video.category_1)
                .filter(Video.section == SECTION_ADDITIONAL)
                .distinct()
                .order_by(Video.category_1)
                .all()
            )

            # Дополнительно: если у тебя category_1 может быть только в Audio/Texts — можно раскомментить и объединить.
            # audio_cat1 = (
            #     db.query(Audio.category_1)
            #     .filter(Audio.section == SECTION_ADDITIONAL)
            #     .distinct()
            #     .all()
            # )
            # text_cat1 = (
            #     db.query(Texts.category_1)
            #     .filter(Texts.section == SECTION_ADDITIONAL)
            #     .distinct()
            #     .all()
            # )
            # cat1_values = sorted({r[0] for r in (cat1_rows + audio_cat1 + text_cat1) if r and r[0]})
            cat1_values = [r[0] for r in cat1_rows if r and r[0]]

            buttons = [
                [InlineKeyboardButton(cat1, callback_data=_cb_cat1(cat1))]
                for cat1 in cat1_values
            ]

            if not buttons:
                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text="🧘 Доп. практики\n\nПока нет доступных категорий.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Назад", callback_data="menu")]]
                    ),
                    media_files=None,
                )
                return

            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="menu")])

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="🧘 Доп. практики\n\nВыберите категорию:",
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=None,
            )
        finally:
            db.close()


# --- 2) уровень: category_2 (внутри выбранной category_1) ---

async def show_additional_practices_subcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает category_2 внутри выбранной category_1"""
    query = update.callback_query
    await query.answer()

    cat1 = _parse_cat1(query.data)

    with SessionLocal() as db:
        try:
            cat2_rows = (
                db.query(Video.category_2)
                .filter(Video.section == SECTION_ADDITIONAL, Video.category_1 == cat1)
                .distinct()
                .order_by(Video.category_2)
                .all()
            )

            # Если category_2 могут быть только в Audio/Texts — объединяй аналогично (как выше).
            cat2_values = [r[0] for r in cat2_rows if r and r[0]]

            buttons = [
                [InlineKeyboardButton(cat2, callback_data=_cb_cat2(cat1, cat2))]
                for cat2 in cat2_values
            ]

            if not buttons:
                await replace_menu_message(
                    chat_id=update.effective_chat.id,
                    context=context,
                    text=f"🧘 {cat1}\n\nПока нет подкатегорий.",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")]]
                    ),
                    media_files=None,
                )
                return

            buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="additional_practices")])

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=f"🧘 {cat1}\n\nВыберите практику:",
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=None,
            )
        finally:
            db.close()


# --- контент: видео + аудио + текст по (category_1, category_2) ---

async def show_additional_practice_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    По выбранной подкатегории показывает:
    - видео (Video.video_id)
    - аудио (Audio.audio_id)
    - текст (Texts.*)
    В одном сообщении через replace_menu_message(media_files=[...])
    """
    query = update.callback_query
    await query.answer()

    cat1, cat2 = _parse_cat2(query.data)

    with SessionLocal() as db:
        try:
            videos = (
                db.query(Video)
                .filter(
                    Video.section == SECTION_ADDITIONAL,
                    Video.category_1 == cat1,
                    Video.category_2 == cat2,
                )
                .order_by(Video.id)
                .all()
            )

            audios = (
                db.query(Music)
                .filter(
                    Music.section == SECTION_ADDITIONAL,
                    Music.category_1 == cat1,
                    Music.category_2 == cat2,
                )
                .order_by(Music.id)
                .all()
            )

            texts = (
                db.query(Texts)
                .filter(
                    Texts.section == SECTION_ADDITIONAL,
                    Texts.category_1 == cat1,
                    Texts.category_2 == cat2,
                )
                .order_by(Texts.id)
                .all()
            )

            media_files: list[str] = []

            # видео (как у тебя: video.video_id)
            for v in videos:
                fid = getattr(v, "video_id", None)
                if fid:
                    media_files.append(fid)

            # аудио (предполагаю поле audio_id)
            for a in audios:
                fid = getattr(a, "audio_id", None)
                if fid:
                    media_files.append(fid)

            # текст в тело сообщения
            text_parts: list[str] = []
            for t in texts:
                # подстрой под свои поля: content/body/text/description/title
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
            if text_parts:
                full_text = header + "\n\n" + "\n\n— — —\n\n".join(text_parts)
            else:
                full_text = header

            if not media_files and not text_parts:
                full_text += "\n\nПока нет контента в этой подкатегории."

            buttons = [
                [InlineKeyboardButton("🔙 Назад", callback_data=_cb_cat1(cat1))],
                [InlineKeyboardButton("🏠 В доп. практики", callback_data="additional_practices")],
            ]

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=full_text,
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=media_files or None,
            )
        finally:
            db.close()
