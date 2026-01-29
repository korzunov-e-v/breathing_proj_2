import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import User
from src.log import log_interaction
from src.modules.menu_renderer import replace_menu_message


async def handle_change_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для меню смены времени"""

    if not context.user_data.get('waiting_for_change_time'):
        return

    await log_interaction(update, "CHANGE_TIME_REQUESTED")
    try:
        umt = update.message.text
        if len(umt) == 4:
            umt = "0" + umt
        time = datetime.time.fromisoformat(umt)
        user_id = update.effective_user.id
        db = SessionLocal()
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user.practice_time = time.strftime("%H:%M")
            db.commit()
            context.user_data.pop('waiting_for_change_time')
            await replace_menu_message(
                chat_id=update.message.chat.id,
                context=context,
                text=(
                    f"Отлично! 🎉\n"
                    f"\n"
                    f"Ваше время практик установлено на {user.practice_time}.\n"
                    f"\n"
                    f"Теперь я буду напоминать вам о практике в это время каждый день.\n"
                    f"\n"
                    f"Когда будете готовы начать - нажмите кнопку ниже:"
                ),
                buttons=[{"text": "⬅️ Главное меню", "goto": "menu"}],
                media_files=[],
            )
        else:
            await replace_menu_message(
                chat_id=update.message.chat.id,
                context=context,
                text="Пользователь не найден. Начните с /start",
                buttons=[],
                media_files=[],
            )
    except ValueError:
        await replace_menu_message(
            chat_id=update.message.chat.id,
            context=context,
            text="Не понятно время, отправьте в формате 07:00, 09:31, 21:59",
            buttons=[],
            media_files=[],
        )


async def handle_time_selection(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()

    time_str = query.data.replace("set_time_", "")
    await log_interaction(update, "TIME_SELECTED", f"Time: {time_str}")

    user_id = query.from_user.id

    keyboard = [
        [InlineKeyboardButton("📋 В главное меню", callback_data="menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Сохраняем время в БД
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user.practice_time = time_str
            db.commit()

            # Показываем главное меню из YAML после настройки
            await query.edit_message_text(
                f"*Отлично!* 🎉\n\nВаше время практик установлено на *{time_str}*.\n\n"
                f"Теперь я буду напоминать вам о практике в это время каждый день.\n\n"
                f"Когда будете готовы начать - нажмите кнопку ниже:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("Пользователь не найден. Начните с /start")
    finally:
        db.close()
