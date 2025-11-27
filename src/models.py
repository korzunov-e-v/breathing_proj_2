from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Text,
    ForeignKey,
    Enum,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from src.database import Base
import enum


class FavoriteItemType(enum.Enum):
    article = "article"
    music = "music"
    practice = "practice"


class NotificationType(enum.Enum):
    daily = "daily"
    practice_reminder = "practice_reminder"
    emotion = "emotion"


class Mood(Base):
    __tablename__ = "moods"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    icon = Column(String(255))  # опционально

    practices = relationship("Practice", back_populates="mood")

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
    practice_time = Column(String(5))  # "HH:MM"
    subscribed = Column(Boolean, default=False)
    current_day = Column(Integer, default=1)
    streak = Column(Integer, default=0)

    last_practice_at = Column(DateTime(timezone=True))
    last_daily_notification_at = Column(DateTime(timezone=True))
    last_emotion_notification_at = Column(DateTime(timezone=True))

    notification_paused = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    emotions = relationship("Emotion", back_populates="user")
    favorites = relationship("Favorite", back_populates="user")
    logs = relationship("NotificationLog", back_populates="user")

    # Новые поля
    total_practice_minutes = Column(Integer, default=0)
    reminder_count_today = Column(Integer, default=0)
    last_reminder_sent_at = Column(DateTime(timezone=True))
    freeze_reminders = Column(Boolean, default=False)

    # Связи с новыми таблицами
    practice_logs = relationship("PracticeLog")
    achievements = relationship("UserAchievement")
    subscriptions = relationship("Subscription")


    def __repr__(self):
        return f"User(id={self.id}, tg_id={self.tg_id}, username='{self.username}')"

    def __str__(self):
        return f"{self.username} (ID: {self.tg_id})" if self.username else f"User {self.tg_id}"


class Practice(Base):
    __tablename__ = "practices"

    id = Column(Integer, primary_key=True)
    day_number = Column(Integer, index=True, nullable=False)

    mood_id = Column(Integer, ForeignKey("moods.id"), nullable=False)
    mood = relationship("Mood", back_populates="practices")

    audio_file_id = Column(String(500))
    intro_text = Column(Text)
    outro_text = Column(Text)

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Practice(id={self.id}, day={self.day_number}, mood_id={self.mood_id})"

    def __str__(self):
        mood_name = self.mood.name if self.mood else "Unknown Mood"
        return f"Day {self.day_number} - {mood_name}"


class PracticeLog(Base):
    __tablename__ = "practice_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    practice_id = Column(Integer, ForeignKey("practices.id"), nullable=False)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())
    mood_before = Column(String(100))  # настроение до практики
    mood_after = Column(String(100))  # настроение после практики
    feedback_rating = Column(Integer)  # 1-5 звезд
    feedback_comment = Column(Text)  # текстовый отзыв

    user = relationship("User")
    practice = relationship("Practice")
    # Новые поля
    duration_minutes = Column(Integer, default=5)
    practice_type = Column(String(100))  # 'basic', 'advanced', 'kundalini', etc.

    # Связи
    practice_logs = relationship("PracticeLog")
    def __repr__(self):
        return f"PracticeLog(user_id={self.user_id}, practice_id={self.practice_id})"

    def __str__(self):
        return f"Practice #{self.practice_id} by User #{self.user_id}"


class Phrase(Base):
    __tablename__ = "phrases"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    category = Column(String(100))  # 'discipline', 'breathing', 'stress', 'attention', 'body', 'exhalation_cycle'
    for_premium = Column(Boolean, default=False)  # только для премиум?

    def __repr__(self):
        return f"Phrase(id={self.id}, category='{self.category}')"

    def __str__(self):
        return f"{self.text[:50]}..." if len(self.text) > 50 else self.text


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    icon = Column(String(255))
    condition_type = Column(String(100))  # 'streak', 'practice_count', 'emotion_count', etc.
    condition_value = Column(Integer)

    def __repr__(self):
        return f"Achievement(id={self.id}, name='{self.name}')"

    def __str__(self):
        return self.name


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    achievement = relationship("Achievement")

    def __repr__(self):
        return f"UserAchievement(user_id={self.user_id}, achievement_id={self.achievement_id})"

    def __str__(self):
        return f"{self.achievement.name} - {self.user.username}"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_type = Column(String(50))  # 'basic', 'premium'
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)

    user = relationship("User")

    def __repr__(self):
        return f"Subscription(user_id={self.user_id}, plan='{self.plan_type}')"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.plan_type} ({status})"


class Emotion(Base):
    __tablename__ = "emotions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    emotion_name = Column(String(255))
    note = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="emotions")

    def __repr__(self):
        return f"Emotion(id={self.id}, user_id={self.user_id}, emotion='{self.emotion_name}')"

    def __str__(self):
        return f"{self.emotion_name} - {self.created_at.strftime('%Y-%m-%d') if self.created_at else ''}"


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
    audio_id = Column(String(255))
    category = Column(String(255))

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Music(id={self.id}, category='{self.category}')"

    def __str__(self):
        return f"{self.category} - {self.audio_id[:20]}..."


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    item_type = Column(Enum(FavoriteItemType), nullable=False)
    item_id = Column(Integer, nullable=False)

    user = relationship("User", back_populates="favorites")

    def __repr__(self):
        return f"Favorite(id={self.id}, user_id={self.user_id}, type={self.item_type.value})"

    def __str__(self):
        return f"{self.item_type.value} #{self.item_id}"


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
