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
        return f"Mood(id={self.id}, name={self.name})"

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
    logs = relationship("NotificationLog", back_populates="user")
    practice_logs = relationship("PracticeLog", back_populates="user")

    orders = relationship("Order", back_populates="user")
    entitlements = relationship("UserEntitlement", back_populates="user")

    def __repr__(self):
        return f"User(id={self.id}, tg_id={self.tg_id}, username={self.username})"

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
        return f"Phrase(id={self.id}, category={self.category})"

    def __str__(self):
        return f"{self.text[:50]}..." if len(self.text) > 50 else self.text


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    text = Column(Text)
    category = Column(String(255))

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Article(id={self.id}, title={self.title})"

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
        return f"Music(id={self.id}, title='{self.title})"

    def __str__(self):
        return self.title or f"Music #{self.id}"


class MiniPractice(Base):
    __tablename__ = "mini_practices"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    audio_id = Column(String(255))

    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"MiniPractice(id={self.id})"

    def __str__(self):
        return self.title or f"MiniPractice #{self.id}"


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
        return f"Video(id={self.id})"

    def __str__(self):
        return self.title or f"Video #{self.id}"


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    image_id = Column(String(255))
    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"Image(id={self.id})"

    def __str__(self):
        return self.title or f"Image #{self.id}"


class TextItem(Base):
    __tablename__ = "texts"

    id = Column(Integer, primary_key=True)
    text = Column(String(500))
    category_1 = Column(String(500))
    category_2 = Column(String(500))
    section = Column(String(500))
    premium = Column(Boolean, default=False)

    def __repr__(self):
        return f"TextItem(id={self.id})"

    def __str__(self):
        return self.text[:20] + "..." if self.text else f"TextItem #{self.id}"


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


class ProductType(enum.Enum):
    premium_lifetime = "premium_lifetime"
    article = "article"
    music = "music"
    video = "video"
    mini_practice = "mini_practice"
    image = "image"
    text = "text"
    bundle = "bundle"
    additional_practice = "additional_practice"


class ProductItemType(enum.Enum):
    article = "article"
    music = "music"
    video = "video"
    mini_practice = "mini_practice"
    image = "image"
    text = "text"


class ProductItem(Base):
    __tablename__ = "product_items"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    item_type = Column(Enum(ProductItemType), nullable=False)

    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    music_id = Column(Integer, ForeignKey("music.id"), nullable=True)
    video_id = Column(Integer, ForeignKey("video.id"), nullable=True)
    mini_practice_id = Column(Integer, ForeignKey("mini_practices.id"), nullable=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)
    text_id = Column(Integer, ForeignKey("texts.id"), nullable=True)
    product = relationship("Product", back_populates="items")
    article = relationship("Article")
    music = relationship("Music")
    video = relationship("Video")
    mini_practice = relationship("MiniPractice")
    image = relationship("Image")
    text_item = relationship("TextItem")

    def __repr__(self):
        return f"ProductItem(id={self.id}, product_id={self.product_id}, item_type={self.item_type.value})"

    def __str__(self):
        return f"{self.item_type} item #{self.id}"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    code = Column(String(100), unique=True, nullable=False)  # premium_lifetime, article_15
    title = Column(String(255), nullable=False)
    description = Column(Text)

    product_type = Column(Enum(ProductType), nullable=False)
    price_value = Column(Integer, nullable=False)  # в копейках
    currency = Column(String(3), default="RUB", nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    is_repeatable = Column(Boolean, default=False, nullable=False)  # можно ли покупать повторно

    section = Column(String(100), nullable=True)
    category_1 = Column(String(500), nullable=True)
    category_2 = Column(String(500), nullable=True)

    # ссылка на конкретный контент
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    music_id = Column(Integer, ForeignKey("music.id"), nullable=True)
    video_id = Column(Integer, ForeignKey("video.id"), nullable=True)
    mini_practice_id = Column(Integer, ForeignKey("mini_practices.id"), nullable=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)
    text_id = Column(Integer, ForeignKey("texts.id"), nullable=True)

    orders = relationship("Order", back_populates="product")
    entitlements = relationship("UserEntitlement", back_populates="product")
    article = relationship("Article")
    music = relationship("Music")
    video = relationship("Video")
    mini_practice = relationship("MiniPractice")
    image = relationship("Image")
    text_item = relationship("TextItem")
    items = relationship(
        "ProductItem",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"Product(id={self.id}, code={self.code}, type={self.product_type.value})"

    def __str__(self):
        return self.title or f"{self.code}"


class OrderStatus(enum.Enum):
    pending = "pending"
    waiting_for_payment = "waiting_for_payment"
    paid = "paid"
    canceled = "canceled"
    failed = "failed"
    refunded = "refunded"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)

    amount_value = Column(Integer, nullable=False)  # фиксируем цену на момент покупки
    currency = Column(String(3), default="RUB", nullable=False)

    external_ref = Column(String(100), unique=True)  # твой публичный номер заказа

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    paid_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="orders")
    product = relationship("Product", back_populates="orders")
    payments = relationship("Payment", back_populates="order")
    entitlements = relationship("UserEntitlement", back_populates="order")

    def __repr__(self):
        return f"Order(id={self.id}, external_ref={self.external_ref}, status={self.status.value})"

    def __str__(self):
        return f"Order #{self.external_ref or self.id} - {self.status.value}"


class PaymentStatus(enum.Enum):
    pending = "pending"
    waiting_for_capture = "waiting_for_capture"
    succeeded = "succeeded"
    canceled = "canceled"


class PaymentProvider(enum.Enum):
    yookassa = "yookassa"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)

    provider = Column(Enum(PaymentProvider), default=PaymentProvider.yookassa, nullable=False)
    provider_payment_id = Column(String(100), unique=True, nullable=False)  # payment.id из ЮKassa

    status = Column(Enum(PaymentStatus), nullable=False)
    amount_value = Column(Integer, nullable=False)
    income_amount_value = Column(Integer)  # если пригодится
    currency = Column(String(3), default="RUB", nullable=False)

    paid = Column(Boolean, default=False, nullable=False)
    refundable = Column(Boolean, default=False, nullable=False)
    test = Column(Boolean, default=False, nullable=False)
    idempotence_key = Column(String(64), unique=True, nullable=False)

    payment_method_type = Column(String(50))
    payment_method_id = Column(String(100))  # для будущих рекуррентов
    confirmation_url = Column(Text)

    raw_response = Column(Text)  # json строкой или JSONB, если postgres
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    confirmed_at = Column(DateTime(timezone=True))

    order = relationship("Order", back_populates="payments")
    last_checked_at = Column(DateTime(timezone=True))
    status_synced_at = Column(DateTime(timezone=True))
    check_attempts = Column(Integer, default=0, nullable=False)
    finalized_at = Column(DateTime(timezone=True))
    status_description = Column(Text)

    def __repr__(self):
        return f"Payment(id={self.id}, provider_payment_id={self.provider_payment_id}, status={self.status.value})"

    def __str__(self):
        return f"Payment {self.provider_payment_id} - {self.status.value}"


class EntitlementType(enum.Enum):
    premium_lifetime = "premium_lifetime"
    article_access = "article_access"
    music_access = "music_access"
    video_access = "video_access"
    mini_practice_access = "mini_practice_access"
    image_access = "image_access"
    text_access = "text_access"
    additional_practice_access = "additional_practice_access"


class UserEntitlement(Base):
    __tablename__ = "user_entitlements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    entitlement_type = Column(Enum(EntitlementType), nullable=False)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)

    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    music_id = Column(Integer, ForeignKey("music.id"), nullable=True)
    video_id = Column(Integer, ForeignKey("video.id"), nullable=True)
    mini_practice_id = Column(Integer, ForeignKey("mini_practices.id"), nullable=True)
    image_id = Column(Integer, ForeignKey("images.id"), nullable=True)
    text_id = Column(Integer, ForeignKey("texts.id"), nullable=True)

    section = Column(String(100), nullable=True)
    category_1 = Column(String(500), nullable=True)
    category_2 = Column(String(500), nullable=True)

    granted_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)  # null = навсегда
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="entitlements")
    product = relationship("Product", back_populates="entitlements")
    order = relationship("Order", back_populates="entitlements")
    article = relationship("Article")
    music = relationship("Music")
    video = relationship("Video")
    mini_practice = relationship("MiniPractice")
    image = relationship("Image")
    text_item = relationship("TextItem")

    def __repr__(self):
        return f"UserEntitlement(id={self.id}, user_id={self.user_id}, type={self.entitlement_type.value})"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.entitlement_type.value} for User #{self.user_id} ({status})"
