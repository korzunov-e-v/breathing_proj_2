from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.modules.acquiring.queries import get_pending_payments
from src.modules.acquiring.service import AcquiringService


async def poll_pending_payments(
    session_factory: async_sessionmaker[AsyncSession],
    limit: int = 100,
) -> int:
    processed = 0

    async with session_factory() as session:
        payments = await get_pending_payments(session, limit=limit)

        for payment in payments:
            service = AcquiringService(session)
            await service.sync_payment_status(payment_id=payment.id)
            processed += 1

    return processed
