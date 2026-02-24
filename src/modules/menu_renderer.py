import logging

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.db.database import SessionLocal
from src.db.models import User, Image
from src.telegram_utils import _detect_type


async def cleanup_practice_messages(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    user_data: UserContextData = context.user_data
    ids = user_data.practice_data.practice_message_ids
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
    user_data: UserContextData = context.user_data

    media_files = media_files or []
    media_file = media_files[0] if media_files else None

    # 1) удалить предыдущее меню
    try:
        old_id = user_data.screen_message_id
    except:
        old_id = None
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
    try:
        user_data.screen_message_id = msg.message_id
    except:
        pass
    return msg.message_id


async def replace_screen(
    *,
    chat_id: int,
    context,
    text: str,
    reply_markup,
    media=None,
    audio=None,
    video=None,
    parse_mode="Markdown",
):
    """
    Заменяет текущее сообщение экрана на новое.

    Args:
        chat_id: ID чата
        context: Контекст бота
        text: Текст сообщения
        reply_markup: Клавиатура
        media: Фото/изображение (file_id или URL)
        audio: Аудио файл (file_id или URL)
        video: Видео файл (file_id или URL)
        parse_mode: Режим парсинга текста
    """
    from src.context import UserContextData

    user_data: UserContextData = context.user_data
    old_id = user_data.screen_message_id

    # Удаляем старое сообщение
    if old_id:
        try:
            await context.bot.delete_message(chat_id, old_id)
        except:
            pass

    # Отправляем новое сообщение в зависимости от типа медиа
    if media:
        # Отправляем фото с подписью
        msg = await context.bot.send_photo(
            chat_id=chat_id,
            photo=media,
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    elif audio:
        # Отправляем аудио с подписью
        msg = await context.bot.send_audio(
            chat_id=chat_id,
            audio=audio,
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    elif video:
        # Отправляем видео с подписью
        msg = await context.bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    else:
        # Отправляем простое текстовое сообщение
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )

    # Сохраняем ID нового сообщения
    user_data.screen_message_id = msg.message_id

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await cleanup_practice_messages(chat_id, context)

    user_data: UserContextData = context.user_data
    user_data.clear_practice_data()

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌬 Дыхание дня", callback_data="daily_practice")],
            [InlineKeyboardButton("🔄 Вернуться к дыханию", callback_data="practice_again")],
            [InlineKeyboardButton("📚 Заметки Кабира", callback_data="library")],
            [InlineKeyboardButton("🌀 Дневник состояний", callback_data="analytics")],
            [InlineKeyboardButton("💬 Разговор с Кабиром", callback_data="ai_chat")],
            [InlineKeyboardButton("✨ Глубже в путешествие", callback_data="subscription")] if _get_user_current_day(
                update.effective_user.id
            ) >= 3 else [],
            [InlineKeyboardButton("⚙️ Ритм и настройки (время, напоминания, выборы)", callback_data="settings")],
        ]
    )

    db = SessionLocal()
    try:
        image: Image = db.query(Image).filter(Image.title == "Меню").first()
        main_menu_image = image.image_id
    finally:
        db.close()


    await replace_screen(
        chat_id=chat_id,
        context=context,
        text="""
*🌿 Главное пространство*

**Здесь нет спешки и задач.**  
Здесь ты возвращаешься к себе —  
через дыхание, внимание и тишину.

Выбирай то, что откликается тебе сейчас.  
Каждый путь здесь — про заботу и присутствие.
        """,
        reply_markup=keyboard,
        media=main_menu_image,
    )


def _get_user_current_day(user_id: int):
    db = SessionLocal()
    try:
        user: User = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            return user.current_day
        return 1
    finally:
        db.close()
