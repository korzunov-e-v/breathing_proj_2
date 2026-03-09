import logging
from typing import Callable, Awaitable

from telegram import Update
from telegram.ext import ContextTypes

from src.modules.acquiring.handlers import (
    buy_additional_practice,
    buy_subscription,
    show_subscription_offer,
)
from src.modules.additional_practices.handlers import (
    show_additional_practices,
    show_additional_practice_content,
    show_additional_practices_subcategories
)
from src.modules.analytics.analytics import show_analytics
from src.modules.feedback.handlers import show_feedback
from src.modules.library.library_mini_practice import show_mini_practice, show_mini_practices_content
from src.modules.library.library_music import show_music_content, show_music_by_category, play_music
from src.modules.library.library_notes import show_library_content, show_articles_by_category, show_article
from src.modules.library.library_video import show_video_content, show_video, show_video_by_category
from src.modules.library.menu import show_library_menu
from src.modules.llm.chat import handle_chat, stop_chat
from src.modules.menu_renderer import show_main_menu
from src.modules.onboarding.onboarding import (
    send_onboarding,
    continue_onboarding,
    retry_onboarding,
    change_time,
    setting_timezone
)
from src.modules.practice.mood import ask_mood_after_practice, handle_mood_selection
from src.modules.practice.pract import show_daily_practice, show_practice_again, handle_practice_completion, \
    handle_restart_practices, handle_repeat_practice_selection
from src.modules.practice.rate import handle_comment_skip
from src.modules.reminders.handlers import remind_later_handler, skip_today_handler
from src.modules.settings.notifications import pause_notifications_handler
from src.modules.settings.settings import toggle_notifications_handler, settings_handler
from src.modules.settings.time import handle_change_time, handle_time_selection, handle_timezone_selection
from src.settings import settings

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]
EXACT_ROUTES: dict[str, Handler] = {
    # меню
    "menu": show_main_menu,
    "daily_practice": show_daily_practice,
    "practice_again": show_practice_again,
    "ai_chat": handle_chat,
    "stop_chat": stop_chat,
    "library": show_library_menu,
    "library_notes": show_library_content,
    "library_sounds": show_music_content,
    "library_videos": show_video_content,
    "library_practices": show_mini_practices_content,
    "analytics": show_analytics,
    "additional_practices": show_additional_practices,
    "subscription": show_subscription_offer,
    "subscription_offer": show_subscription_offer,

    # онбординг
    "send_onboarding": send_onboarding,
    "continue_onboarding": continue_onboarding,
    "retry_onboarding": retry_onboarding,
    "setting_timezone": setting_timezone,
    "finish_onboarding": change_time,

    # время/настройки
    "settings": settings_handler,
    "change_time": change_time,
    "toggle_notifications": toggle_notifications_handler,

    # практика
    "practice_complete": handle_practice_completion,
    "restart_practices": handle_restart_practices,
    "ask_mood_after": ask_mood_after_practice,

    # фидбек
    "skip_comment": handle_comment_skip,
    "feedback": show_feedback,

    # напоминания/уведомления
    "remind_later": remind_later_handler,
    "skip_today": skip_today_handler,
    "pause_notifications": pause_notifications_handler,
    "buy_subscription": buy_subscription,
}

# ВАЖНО: порядок имеет значение!
# Более специфичные префиксы — выше
PREFIX_ROUTES: list[tuple[str, Handler]] = [
    ("set_time_", handle_time_selection),
    ("repeat_practice_", handle_repeat_practice_selection),
    ("mood_", handle_mood_selection),
    ("timezone_", handle_timezone_selection),
    ("article_category_", show_articles_by_category),
    ("article_", show_article),
    ("music_category_", show_music_by_category),
    ("music_", play_music),
    ("video_category_", show_video_by_category),
    ("video_", show_video),
    ("minipractice_", show_mini_practice),
    ("ap_cat1_", show_additional_practices_subcategories),
    ("ap_cat2_", show_additional_practice_content),
    ("buy_ap_", buy_additional_practice),
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
