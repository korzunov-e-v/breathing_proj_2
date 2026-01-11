from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.db.database import SessionLocal
from src.db.models import User
from src.log import log_interaction

time_keyboard = [
    [InlineKeyboardButton("07:00", callback_data="set_time_07:00"),
     InlineKeyboardButton("08:00", callback_data="set_time_08:00")],
    [InlineKeyboardButton("09:00", callback_data="set_time_09:00"),
     InlineKeyboardButton("10:00", callback_data="set_time_10:00")],
    [InlineKeyboardButton("11:00", callback_data="set_time_11:00"),
     InlineKeyboardButton("12:00", callback_data="set_time_12:00")],
]


async def handle_change_time(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для меню смены времени"""
    query = update.callback_query
    await query.answer()

    await log_interaction(update, "CHANGE_TIME_REQUESTED")

    # Показываем меню выбора времени (программно, не из YAML)
    reply_markup = InlineKeyboardMarkup(time_keyboard)

    await query.edit_message_text(
        "Выберите удобное время для ежедневных практик:",
        reply_markup=reply_markup
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
