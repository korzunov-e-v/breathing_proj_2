import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class NotificationType(enum.Enum):
    daily = "daily"
    practice_reminder = "practice_reminder"
    emotion = "emotion"


class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    icon = Column(String(255))

    def __repr__(self):
        return f"Mood(id={self.id}, name='{self.name}')"

    def __str__(self):
        return self.name


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, index=True, unique=True, nullable=False)
    username = Column(String(500))

    timezone = Column(String(50))
    practice_time = Column(String(5))
    subscribed = Column(Boolean, default=False)
    current_day = Column(Integer, default=0)
    streak = Column(Integer, default=0)

    last_practice_at = Column(DateTime(timezone=True))
    last_daily_notification_at = Column(DateTime(timezone=True))
    last_emotion_notification_at = Column(DateTime(timezone=True))

    notification_paused = Column(Boolean, default=False)
    total_practice_minutes = Column(Integer, default=0)
    reminder_count_today = Column(Integer, default=0)
    last_reminder_sent_at = Column(DateTime(timezone=True))
    freeze_reminders = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Отношения
    emotions = relationship("Emotion", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    logs = relationship("NotificationLog", back_populates="user")
    practice_logs = relationship("PracticeLog", back_populates="user")
    achievements = relationship("UserAchievement", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")

    def __repr__(self):
        return f"User(id={self.id}, tg_id={self.tg_id}, username='{self.username}')"

    def __str__(self):
        return f"{self.username} (ID: {self.tg_id})" if self.username else f"User {self.tg_id}"


class Practice(Base):
    __tablename__ = "practices"

    id = Column(Integer, primary_key=True)
    day_number = Column(Integer, index=True, nullable=False)
    audio_file_id = Column(String(500))
    video_file_id = Column(String(500))
    intro_text = Column(Text)
    outro_text = Column(Text)
    premium = Column(Boolean, default=False)

    practice_logs = relationship("PracticeLog", back_populates="practice")

    def __repr__(self):
        return f"Practice(id={self.id}, day={self.day_number})"

    def __str__(self):
        return f"Day {self.day_number}"


class PracticeLog(Base):
    __tablename__ = "practice_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete='CASCADE'), nullable=False)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    mood_before = Column(String(100))
    mood_after = Column(String(100))
    feedback_rating = Column(Integer)
    feedback_comment = Column(Text)
    duration_minutes = Column(Integer, default=5)
    practice_type = Column(String(100))

    user = relationship("User", back_populates="practice_logs")
    practice = relationship("Practice", back_populates="practice_logs")

    def __repr__(self):
        return f"PracticeLog(user_id={self.user_id}, practice_id={self.practice_id})"

    def __str__(self):
        return f"Practice #{self.practice_id} by User #{self.user_id}"


class Phrase(Base):
    __tablename__ = "phrases"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    category = Column(String(100))
    for_premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Phrase(id={self.id}, category='{self.category}')"

    def __str__(self):
        return f"{self.text[:50]}..." if len(self.text) > 50 else self.text


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_type = Column(String(50))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"Subscription(user_id={self.user_id}, plan='{self.plan_type}')"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.plan_type} ({status})"


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    text = Column(Text)
    category = Column(String(255))

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Article(id={self.id}, title='{self.title}')"

    def __str__(self):
        return self.title


class Music(Base):
    __tablename__ = "music"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    audio_id = Column(String(255))
    category_1 = Column(String(500))
    category_2 = Column(String(500))
    section = Column(String(500))

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Music(id={self.id}, category='{self.category}')"

    def __str__(self):
        return f"{self.category} - {self.audio_id[:20]}..."


class MiniPractice(Base):
    __tablename__ = "mini_practices"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    audio_id = Column(String(255))

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"MiniPractice(id={self.id}')"

    def __str__(self):
        return f"{self.audio_id[:20]}..."


class Video(Base):
    __tablename__ = "video"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    category_1 = Column(String(500))
    category_2 = Column(String(500))
    section = Column(String(500))
    video_id = Column(String(255))
    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Video(id={self.id}')"

    def __str__(self):
        return f"{self.video_id[:20]}..."


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    image_id = Column(String(255))
    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Image(id={self.id}')"

    def __str__(self):
        return f"{self.image_id[:20]}..."


class Texts(Base):
    __tablename__ = "texts"

    id = Column(Integer, primary_key=True)
    text = Column(String(500))
    category_1 = Column(String(500))
    category_2 = Column(String(500))
    section = Column(String(500))
    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Text(id={self.id}')"

    def __str__(self):
        return f"{self.text[:20]}..."


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(Enum(NotificationType), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="logs")

    def __repr__(self):
        return f"NotificationLog(id={self.id}, user_id={self.user_id}, type={self.type.value})"

    def __str__(self):
        date_str = self.sent_at.strftime('%Y-%m-%d %H:%M') if self.sent_at else 'Unknown date'
        return f"{self.type.value} - {date_str}"
