# src/telegram_utils.py
from typing import Optional, Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update


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

        # Send via provided bot (from Application or Context)
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
