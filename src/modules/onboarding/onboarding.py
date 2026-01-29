import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from src.log import log_interaction
from src.modules.menu_renderer import replace_menu_message


async def send_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Процесс онбординга для нового пользователя"""
    await log_interaction(update, "ONBOARDING_STARTED")

    # 1. Приветствие
    welcome_text = (
        f"*Это ваше тихое место.* 🌿\n"
        f"\n"
        f"Давайте создадим ритм, который будет поддерживать вас ежедневно.\n"
        f"\n"
        f"Здесь вы найдете практики дыхания, которые помогут:\n"
        f"• Снизить стресс и тревогу\n"
        f"• Улучшить концентрацию\n"
        f"• Обрести внутреннее спокойствие"
    )
    keyboard = [
        [InlineKeyboardButton("Вдох", callback_data="continue_onboarding")]
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

    text = (f"бла бла")
    buttons = [
        {"text": "Я коснулся дыхания", "goto": "finish_onboarding"},
        {"text": "Я возьму паузу", "goto": "retry_onboarding"},
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

    text = (f"Иногда пауза - это уже начало. Возвращайся в правильное для себя время")
    buttons = [
        {"text": "Вернуться к дыханию", "goto": "send_onboarding"},
    ]
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
    context.user_data['waiting_for_change_time'] = True

    text = (
        f"*Отлично!* ✨\n"
        f"\n"
        f"Теперь давайте настроим время для ваших ежедневных практик.\n"
        f"\n"
        f"Напишите удобное время (например `13:00`), и я буду напоминать вам о практике."
    )
    await replace_menu_message(
        chat_id=query.message.chat.id,
        context=context,
        text=text,
        buttons=[],
        media_files=[],
    )
