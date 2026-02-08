import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import ContextTypes

from src.modules.llm.chat import handle_chat, stop_chat
from src.modules.menu_renderer import show_main_menu
from src.modules.onboarding.onboarding import (
    send_onboarding,
    continue_onboarding,
    retry_onboarding,
    finish_onboarding,
    setting_timezone
)
from src.modules.practice.mood import ask_mood_after_practice, handle_mood_selection
from src.modules.practice.pract import show_daily_practice, show_practice_again, handle_practice_completion, \
    handle_restart_practices, handle_repeat_practice_selection
from src.modules.practice.rate import handle_comment_skip
from src.modules.reminders.reminders import remind_later_handler, skip_today_handler
from src.modules.settings.notifications import pause_notifications_handler
from src.modules.settings.time import handle_change_time, handle_time_selection, handle_timezone_selection

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
EXACT_ROUTES: dict[str, Handler] = {
    # меню
    "menu": show_main_menu,
    "daily_practice": show_daily_practice,
    "practice_again": show_practice_again,
    "ai_chat": handle_chat,
    "stop_chat": stop_chat,

    # онбординг
    "send_onboarding": send_onboarding,
    "continue_onboarding": continue_onboarding,
    "retry_onboarding": retry_onboarding,
    "setting_timezone": setting_timezone,
    "finish_onboarding": finish_onboarding,

    # время/настройки
    "change_time": handle_change_time,

    # практика
    "practice_complete": handle_practice_completion,
    "restart_practices": handle_restart_practices,
    "ask_mood_after": ask_mood_after_practice,

    # фидбек
    "skip_comment": handle_comment_skip,

    # напоминания/уведомления
    "remind_later": remind_later_handler,
    "skip_today": skip_today_handler,
    "pause_notifications": pause_notifications_handler,
}

# ВАЖНО: порядок имеет значение!
# Более специфичные префиксы — выше
PREFIX_ROUTES: list[tuple[str, Handler]] = [
    ("set_time_", handle_time_selection),
    ("repeat_practice_", handle_repeat_practice_selection),
    ("mood_", handle_mood_selection),
    ("timezone_", handle_timezone_selection),
]


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    data = query.data

    # ответить ровно один раз (убери query.answer() из остальных хендлеров по мере рефакторинга)
    await query.answer()

    try:
        # 1) exact match
        handler = EXACT_ROUTES.get(data)
        if handler is not None:
            return await handler(update, context)

        # 2) prefix match
        for prefix, pref_handler in PREFIX_ROUTES:
            if data.startswith(prefix):
                return await pref_handler(update, context)

        router_log = logging.getLogger("router")
        router_log.warning(
            f"Unknown callback_data {data}",
            extra={
                "callback_data": data,
                "user_id": query.from_user.id,
                "chat_id": query.message.chat.id,
            }
        )

    except Exception:
        logging.exception(f"Router failed for callback_data={data}")
