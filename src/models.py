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

    audio_file_id = Column(String(255))
    intro_text = Column(Text)
    outro_text = Column(Text)

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Practice(id={self.id}, day={self.day_number}, mood_id={self.mood_id})"

    def __str__(self):
        mood_name = self.mood.name if self.mood else "Unknown Mood"
        return f"Day {self.day_number} - {mood_name}"


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