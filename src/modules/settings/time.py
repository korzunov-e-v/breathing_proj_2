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
                text=f"""
Я услышал твой ритм 🌿  
Мы будем возвращаться к дыханию каждый день в {user.practice_time}.

В это время я буду рядом и мягко напоминать тебе о твоём тихом моменте.  
Без спешки. Без давления. В твоём темпе.

Когда будешь готов — просто прикоснись к нашему пространству.
                """,
                buttons=[{"text": "🌌 В моё пространство", "goto": "menu"}],
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
            text="""
Я хочу поймать твой ритм — но сейчас время пришло в другом виде.  
Напиши, пожалуйста, в формате **ЧЧ:ММ** 
            """,
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


async def handle_timezone_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора часового пояса"""
    query = update.callback_query
    await query.answer()

    # Получаем offset относительно МСК
    msk_offset_str = query.data.replace("timezone_", "")
    msk_offset = int(msk_offset_str)

    # Конвертируем в GMT offset (МСК = GMT+3)
    gmt_offset = msk_offset + 3

    await log_interaction(update, "TIMEZONE_SELECTED", f"MSK offset: {msk_offset}, GMT offset: {gmt_offset}")

    user_id = query.from_user.id

    # Сохраняем часовой пояс в БД
    db = SessionLocal()
    try:
        user: User = db.query(User).filter(User.tg_id == user_id).first()
        if user:
            user.timezone = gmt_offset
            db.commit()

            # Переходим к выбору времени практики
            context.user_data['waiting_for_change_timezone'] = False
            context.user_data['waiting_for_change_time'] = True

            text = '''
У каждого свой ритм — и я предлагаю тебе выбрать свой.  
Это может быть ☀️ утро, 🌤 пауза днём или 🌙 тихий вечер.

✦ Просто напиши мне подходящее для себя время.

_Формат: ЧЧ:ММ_ 
            '''

            await replace_menu_message(
                chat_id=query.message.chat.id,
                context=context,
                text=text,
                buttons=[],
                media_files=[],
            )
        else:
            await replace_menu_message(
                chat_id=query.message.chat.id,
                context=context,
                text="Пользователь не найден. Начните с /start",
                buttons=[],
                media_files=[],
            )
    finally:
        db.close()


def get_timezones_kb():
    buttons = []
    for offset in range(-11, 13):
        if offset == 0:
            label = "МСК"
        elif offset > 0:
            label = f"МСК+{offset}"
        else:
            label = f"МСК{offset}"
        buttons.append({"text": label, "goto": f"timezone_{offset}"})
    return buttons
