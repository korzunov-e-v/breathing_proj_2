from enum import Enum
from typing import Optional
from pydantic import BaseModel

from telegram.ext import ContextTypes


class UserState(str, Enum):
    """Enum for user states"""
    IDLE = "idle"
    CHAT = "chat"
    WAITING_TIME = "waiting_time"
    WAITING_MOOD_BEFORE = "waiting_mood_before"
    WAITING_MOOD_AFTER = "waiting_mood_after"
    WAITING_COMMENT = "waiting_comment"
    FEEDBACK = "FEEDBACK"
    WAITING_PHONE = "waiting_phone"
    WAITING_EMAIL = "waiting_email"
    WAITING_DONATION_AMOUNT = "waiting_donation_amount"

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
    ai_chat_context: list = []
    last_chat_message_id: Optional[int] = None
    pending_purchase_product_code: Optional[str] = None
    pending_donation_video_id: Optional[int] = None
    pending_donation_video_title: Optional[str] = None

    def clear_practice_data(self) -> None:
        """Clear practice-related fields"""
        self.practice_data = PracticeData()
        self.state = UserState.IDLE
        self.ai_chat_context = []
        self.pending_donation_video_id = None
        self.pending_donation_video_title = None

    def clear_donation_state(self) -> None:
        """Reset donation-related context fields."""
        self.state = UserState.IDLE
        self.pending_donation_video_id = None
        self.pending_donation_video_title = None


context_types = ContextTypes(
    user_data=lambda: UserContextData()
)
