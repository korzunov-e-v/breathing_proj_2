from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(Integer, index=True, unique=True, nullable=False)
    username = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
