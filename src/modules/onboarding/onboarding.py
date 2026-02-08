import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.log import log_interaction
from src.modules.menu_renderer import replace_menu_message
from src.modules.settings.time import get_timezones_kb


async def send_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Процесс онбординга для нового пользователя"""
    await log_interaction(update, "ONBOARDING_STARTED")

    # 1. Приветствие
    welcome_text = ("""
Привет, дорогой друг.  
Меня зовут Кабир — и я буду рядом в этом тихом путешествии внутрь себя 🌌

Здесь не нужно спешить, стараться и держать планку.  
Мы просто возвращаемся к твоему личному космосу через дыхание — спокойно, бережно, в своём ритме 🌿

Начнём с первого ознакомительного дыхания.  
Оно займёт 15 минут и поможет телу вспомнить, как отпускать.
    """
                    )
    keyboard = [
        [InlineKeyboardButton("🌬️Вдох", callback_data="continue_onboarding")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await replace_menu_message(
        chat_id=update.effective_chat.id,
        context=context,
        text=welcome_text,
        reply_markup=reply_markup,
        media_files=[],
    )
    return


async def continue_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (f"""
Ты здесь. Этого достаточно.  
Дальше — выбор: шаг или пауза.
    """)
    buttons = [
        {"text": "🌊 Коснулся дыхания", "goto": "setting_timezone"},
        {"text": "⏳ Создал паузу", "goto": "retry_onboarding"},
    ]
    await replace_menu_message(
        chat_id=query.message.chat.id,
        context=context,
        text=text,
        buttons=buttons,
        media_files=["BAACAgIAAxkBAAINTmlw-tPoBF0xnUZICWgcuRqZ2CubAAKaoAACy66JS0ZeGU3DIzvvOAQ"],
    )


async def retry_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = f"Иногда пауза - это уже начало. Возвращайся в правильное для себя время..."
    buttons = [
        {"text": "🌬️ Вернуться к дыханию", "goto": "send_onboarding"},
    ]
    await replace_menu_message(
        chat_id=query.message.chat.id,
        context=context,
        text=text,
        buttons=buttons,
        media_files=[],
    )


async def setting_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data
    user_data.state = UserState.WAITING_TIMEZONE

    text = '''
У каждого свой ритм — и я предлагаю тебе выбрать свой.  
Это может быть ☀️ утро, 🌤 пауза днём или 🌙 тихий вечер.

✦ Просто напиши мне твой часовой пояс от МСК.
    '''
    buttons = get_timezones_kb()
    # Генерируем кнопки для часовых поясов от МСК-11 до МСК+12
    await replace_menu_message(
        chat_id=query.message.chat.id,
        context=context,
        text=text,
        buttons=buttons,
        media_files=[],
    )


async def finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data: UserContextData = context.user_data
    user_data.state = UserState.WAITING_TIME

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
