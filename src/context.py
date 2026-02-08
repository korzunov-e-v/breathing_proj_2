from enum import Enum
from typing import Optional
from pydantic import BaseModel

from telegram.ext import ContextTypes


class UserState(str, Enum):
    """Enum for user states"""
    IDLE = "idle"
    CHAT = "chat"
    WAITING_TIMEZONE = "waiting_timezone"
    WAITING_TIME = "waiting_time"
    WAITING_MOOD_BEFORE = "waiting_mood_before"
    WAITING_MOOD_AFTER = "waiting_mood_after"
    WAITING_COMMENT = "waiting_comment"


class PracticeData(BaseModel):
    """Nested model for practice-related data"""
    mood_before: Optional[int] = None
    mood_after: Optional[int] = None
    feedback_comment: Optional[str] = None
    selected_practice_id: Optional[int] = None
    is_repeat: Optional[bool] = None
    practice_message_ids: list = []
    feedback_ai_reply: Optional[str] = None


class UserContextData(BaseModel):
    """Pydantic model for user context data"""
    state: UserState = UserState.IDLE
    practice_data: PracticeData = PracticeData()
    messages_ids: list = []
    screen_message_id: Optional[int] = None

    def clear_practice_data(self) -> None:
        """Clear practice-related fields"""
        self.practice_data = PracticeData()
        self.state = UserState.IDLE


context_types = ContextTypes(
    user_data=lambda: UserContextData()
)
