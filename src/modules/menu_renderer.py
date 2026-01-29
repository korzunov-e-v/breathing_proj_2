import logging

import yaml
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.telegram_utils import _detect_type

SCREEN_KEY_ID = "screen_message_id"

async def cleanup_practice_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    ids = context.user_data.pop("practice_message_ids", [])
    for mid in ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except BadRequest:
            pass
        except Exception:
            pass

async def replace_menu_message(
        *,
        chat_id: int,
        context,
        text: str,
        buttons=None,
        reply_markup=None,
        media_files: list | None = None,
        parse_mode: str = "Markdown",
):
    """Удаляет предыдущее меню (если было) и отправляет новое. Сохраняет message_id."""

    media_files = media_files or []
    media_file = media_files[0] if media_files else None

    # 1) удалить предыдущее меню
    old_id = context.user_data.get(SCREEN_KEY_ID)
    if old_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_id)
        except BadRequest as e:
            # чаще всего: уже удалено / слишком старое / нет прав
            logging.warning(f"delete old menu failed: {e}")
        except Exception as e:
            logging.warning(f"delete old menu failed: {e}")

    if reply_markup is None:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(btn["text"], callback_data=btn["goto"])] for btn in (buttons or [])]
        )

    # 2) отправить новое меню (ОДНИМ сообщением)
    if media_file:
        t = _detect_type(media_file)
        if t == "video":
            msg = await context.bot.send_video(
                chat_id=chat_id,
                video=media_file,
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        elif t == "audio":
            msg = await context.bot.send_audio(
                chat_id=chat_id,
                audio=media_file,
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        else:
            msg = await context.bot.send_photo(
                chat_id=chat_id,
                photo=media_file,
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=True,
        )

    # 3) сохранить id нового меню
    context.user_data[SCREEN_KEY_ID] = msg.message_id
    return msg.message_id


async def replace_screen(
    *,
    chat_id: int,
    context,
    text: str,
    reply_markup,
    media=None,
    parse_mode="Markdown",
):
    old_id = context.user_data.get(SCREEN_KEY_ID)
    if old_id:
        try:
            await context.bot.delete_message(chat_id, old_id)
        except:
            pass

    if media:
        msg = await context.bot.send_photo(
            chat_id=chat_id,
            photo=media,
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    context.user_data[SCREEN_KEY_ID] = msg.message_id


async def show_main_menu(update, context):
    chat_id = update.effective_chat.id
    await cleanup_practice_messages(chat_id, context)

    context.user_data.pop('mood_before', None)
    context.user_data.pop('mood_after', None)
    context.user_data.pop('feedback_rating', None)
    context.user_data.pop('feedback_comment', None)
    context.user_data.pop('waiting_for_comment', None)
    context.user_data.pop('selected_practice_id', None)
    context.user_data.pop('is_repeat', None)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧘 Практика дня", callback_data="daily_practice")],
        [InlineKeyboardButton("🔄 Пройти снова", callback_data="practice_again")],
        [InlineKeyboardButton("📚 Библиотека", callback_data="library")],
        [InlineKeyboardButton("📊 Аналитика", callback_data="analytics")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="settings")],
    ])

    await replace_screen(
        chat_id=chat_id,
        context=context,
        text=(
            "🧘 *Ваше пространство для дыхания*\n\n"
            "Здесь вы найдете практики, которые помогут обрести гармонию и спокойствие."
        ),
        reply_markup=keyboard,
        media="AgACAgIAAxkBAAIFPGksUH2iD8YETWJR6ohqgFWItyikAAI0DWsbwj5oSeqRrcBf8bH-AQADAgADeAADNgQ",
    )
