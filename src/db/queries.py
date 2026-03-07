from sqlalchemy import select

from src.db.database import AsyncSessionLocal
from src.db.models import User


async def get_user(user_tg_id: int):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == user_tg_id)
        )
        user = result.scalars().first()
        return user
