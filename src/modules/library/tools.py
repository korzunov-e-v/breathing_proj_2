from sqlalchemy import select

from src.db.database import AsyncSessionLocal
from src.db.models import User
from src.modules.acquiring.access import AccessService


async def is_user_subscribed(user_tg_id: int) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.tg_id == user_tg_id))
        user: User | None = result.scalars().first()
        if not user:
            return False
        access_service = AccessService(db)
        return await access_service.has_premium(user.id)
