from telegram import KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState


async def ensure_user_profile(update, context: ContextTypes.DEFAULT_TYPE, user) -> bool:
    """
    Проверяет заполнен ли профиль пользователя.
    Если нет — запрашивает нужные данные.
    Возвращает True если можно продолжать оплату.
    """
    user_ctx: UserContextData = context.user_data
    if not user.phone:
        user_ctx.state = UserState.WAITING_PHONE
        keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Отправить телефон", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Платёжная система просит номер и почту, чтобы спокойно завершить покупку и "
                 "отправить подтверждение.\n\nЕсли с оплатой есть трудности, просто напиши "
                 'нам в разделе "📝 Обратная связь" и мы поможем тебе разобраться.',
            reply_markup=keyboard,
        )
        return False
    if not user.email:
        user_ctx.state = UserState.WAITING_EMAIL
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введите email для чека:",
        )
        return False
    return True
