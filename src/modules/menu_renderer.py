import logging

import yaml
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.telegram_utils import _detect_type

MENU_KEY_ID = "menu_message_id"


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
    old_id = context.user_data.get(MENU_KEY_ID)
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
    context.user_data[MENU_KEY_ID] = msg.message_id
    return msg.message_id


def get_menu_data(menu_name: str) -> dict:
    """Получает данные меню из YAML по имени"""
    try:
        with open("data/menu.yaml", "r", encoding='utf-8') as f:
            data = yaml.safe_load(f)

        logging.info(f"Ищем меню: {menu_name}")
        logging.info(f"Доступные меню: {list(data['main-menu'].keys())}")

        if menu_name not in data["main-menu"]:
            logging.error(f"Меню '{menu_name}' не найдено в YAML")
            return {"text": f"Меню '{menu_name}' не найдено", "buttons": []}

        menu_data = data["main-menu"][menu_name]
        logging.info(f"Меню '{menu_name}' найдено: {menu_data}")
        return menu_data

    except Exception as e:
        logging.error(f"Error loading menu {menu_name}: {e}")
        return {"text": f"Ошибка загрузки меню: {e}", "buttons": []}


async def show_menu_by_name(update: Update, context: ContextTypes.DEFAULT_TYPE, menu_name: str, query=None):
    """Показывает меню по имени из YAML с поддержкой медиа"""
    if query:
        await query.answer()
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id

    menu_cfg = get_menu_data(menu_name)
    text = menu_cfg["text"]
    buttons = menu_cfg.get("buttons", [])
    media_files = menu_cfg.get("media") or menu_cfg.get("images") or []

    await replace_menu_message(
        chat_id=chat_id,
        context=context,
        text=text,
        buttons=buttons,
        media_files=media_files,
    )
