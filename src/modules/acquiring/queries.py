from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import (
    EntitlementType,
    Order,
    Payment,
    PaymentStatus,
    Product,
    ProductType,
    UserEntitlement, ProductItemType,
)


async def get_product_by_code(session: AsyncSession, code: str) -> Product | None:
    stmt = (
        select(Product)
        .where(Product.code == code)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_order_by_id(session: AsyncSession, order_id: int) -> Order | None:
    stmt = (
        select(Order)
        .options(selectinload(Order.product), selectinload(Order.payments))
        .where(Order.id == order_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Payment | None:
    stmt = (
        select(Payment)
        .options(selectinload(Payment.order).selectinload(Order.product))
        .where(Payment.id == payment_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_payment_by_provider_id(
    session: AsyncSession,
    provider_payment_id: str,
) -> Payment | None:
    stmt = (
        select(Payment)
        .options(selectinload(Payment.order).selectinload(Order.product))
        .where(Payment.provider_payment_id == provider_payment_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_pending_payments(
    session: AsyncSession,
    limit: int = 100,
) -> list[Payment]:
    stmt = (
        select(Payment)
        .options(selectinload(Payment.order).selectinload(Order.product))
        .where(Payment.status.in_([PaymentStatus.pending, PaymentStatus.waiting_for_capture]))
        .order_by(Payment.created_at.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_active_entitlement(
    session: AsyncSession,
    *,
    user_id: int,
    entitlement_type: EntitlementType,
    article_id: int | None = None,
    music_id: int | None = None,
    video_id: int | None = None,
    mini_practice_id: int | None = None,
    image_id: int | None = None,
    text_id: int | None = None,
) -> UserEntitlement | None:
    stmt = (
        select(UserEntitlement)
        .where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.entitlement_type == entitlement_type,
            UserEntitlement.is_active.is_(True),
        )
    )

    if article_id is not None:
        stmt = stmt.where(UserEntitlement.article_id == article_id)
    if music_id is not None:
        stmt = stmt.where(UserEntitlement.music_id == music_id)
    if video_id is not None:
        stmt = stmt.where(UserEntitlement.video_id == video_id)
    if mini_practice_id is not None:
        stmt = stmt.where(UserEntitlement.mini_practice_id == mini_practice_id)
    if image_id is not None:
        stmt = stmt.where(UserEntitlement.image_id == image_id)
    if text_id is not None:
        stmt = stmt.where(UserEntitlement.text_id == text_id)

    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def user_has_premium_lifetime(session: AsyncSession, user_id: int) -> bool:
    stmt = select(UserEntitlement.id).where(
        UserEntitlement.user_id == user_id,
        UserEntitlement.entitlement_type == EntitlementType.premium_lifetime,
        UserEntitlement.is_active.is_(True),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


def map_product_type_to_entitlement_type(product_type: ProductType) -> EntitlementType:
    mapping = {
        ProductType.premium_lifetime: EntitlementType.premium_lifetime,
        ProductType.article: EntitlementType.article_access,
        ProductType.music: EntitlementType.music_access,
        ProductType.video: EntitlementType.video_access,
        ProductType.mini_practice: EntitlementType.mini_practice_access,
        ProductType.image: EntitlementType.image_access,
        ProductType.text: EntitlementType.text_access,
    }
    return mapping[product_type]


def map_product_item_type_to_entitlement_type(item_type: ProductItemType) -> EntitlementType:
    mapping = {
        ProductItemType.article: EntitlementType.article_access,
        ProductItemType.music: EntitlementType.music_access,
        ProductItemType.video: EntitlementType.video_access,
        ProductItemType.mini_practice: EntitlementType.mini_practice_access,
        ProductItemType.image: EntitlementType.image_access,
        ProductItemType.text: EntitlementType.text_access,
    }
    return mapping[item_type]
