# src/telegram_utils.py
from typing import Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.log import log_interaction


async def send_text_with_buttons(
    update: Optional[Update],
    context: Any,
    text: str,
    buttons: list,
    query: Any = None,
    chat_id: Optional[int] = None,
    parse_mode: str = 'Markdown'
):
    """Send text with inline buttons in a single message.

    This helper is decoupled from the main module to avoid circular imports.
    It requires an object with a `.bot` attribute (e.g., Application or Context)
    when `query` is not provided.
    """
    # Build inline keyboard (supports flat or row-structured lists and two key styles)
    rows = []
    if buttons and isinstance(buttons[0], dict):
        # Flat list -> make one button per row
        for btn in buttons:
            cb = btn.get("goto") or btn.get("callback_data")
            rows.append([InlineKeyboardButton(btn["text"], callback_data=cb)])
    else:
        # Already structured as rows (list of lists)
        for row in buttons or []:
            rows.append([
                InlineKeyboardButton(b["text"], callback_data=(b.get("goto") or b.get("callback_data")))
                for b in row
            ])

    reply_markup = InlineKeyboardMarkup(rows)

    if query:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    else:
        # Determine chat_id
        if chat_id is None and update is not None and update.effective_chat is not None:
            chat_id = update.effective_chat.id

        # Send it via the provided bot (from Application or Context)
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )


def _detect_type(media_file: str) -> str:
    s = str(media_file).lower()
    if s.endswith(".mp4") or s.startswith("baac"):
        return "video"
    if s.endswith(".mp3") or s.endswith(".ogg") or s.startswith("caac") or s.startswith("cqaca"):
        return "audio"
    return "photo"


async def receive_media(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Обработчик медиа-файлов с логированием и возвратом file_id"""
    await log_interaction(update, "MEDIA_RECEIVED")

    msg = update.message
    if msg.photo:
        file_id = msg.photo[-1].file_id
        await msg.reply_text(f'Photo file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML', parse_mode='HTML')
    elif msg.video:
        file_id = msg.video.file_id
        await msg.reply_text(f"Video file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML", parse_mode="HTML")
    elif msg.audio:
        file_id = msg.audio.file_id
        await msg.reply_text(f"Audio file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML", parse_mode="HTML")
    elif msg.document:
        file_id = msg.document.file_id
        await msg.reply_text(f"Document file_id: <code>{file_id}</code>\n\nИспользуйте этот ID в YAML",
                             parse_mode="HTML")
    else:
        await msg.reply_text(
            "Пришлите фото, видео, аудио или документ, чтобы получить их file_id для использования в меню.")
