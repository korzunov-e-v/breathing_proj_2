from sqlalchemy import select

from src.db.database import AsyncSessionLocal
from src.db.models import User


async def is_user_subscribed(user_tg_id):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == user_tg_id)
        )
        user: User | None = result.scalars().first()
        return user and user.subscribed
