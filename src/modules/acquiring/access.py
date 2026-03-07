from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import EntitlementType, Product, ProductType, UserEntitlement
from src.modules.acquiring import queries


class AccessService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def has_premium(self, user_id: int) -> bool:
        return await queries.user_has_premium_lifetime(self.session, user_id)

    async def has_article_access(self, user_id: int, article_id: int) -> bool:
        if await self.has_premium(user_id):
            return True

        entitlement = await queries.get_active_entitlement(
            self.session,
            user_id=user_id,
            entitlement_type=EntitlementType.article_access,
            article_id=article_id,
        )
        return entitlement is not None

    async def has_music_access(self, user_id: int, music_id: int) -> bool:
        if await self.has_premium(user_id):
            return True

        entitlement = await queries.get_active_entitlement(
            self.session,
            user_id=user_id,
            entitlement_type=EntitlementType.music_access,
            music_id=music_id,
        )
        return entitlement is not None

    async def has_video_access(self, user_id: int, video_id: int) -> bool:
        if await self.has_premium(user_id):
            return True

        entitlement = await queries.get_active_entitlement(
            self.session,
            user_id=user_id,
            entitlement_type=EntitlementType.video_access,
            video_id=video_id,
        )
        return entitlement is not None

    async def has_mini_practice_access(self, user_id: int, mini_practice_id: int) -> bool:
        if await self.has_premium(user_id):
            return True

        entitlement = await queries.get_active_entitlement(
            self.session,
            user_id=user_id,
            entitlement_type=EntitlementType.mini_practice_access,
            mini_practice_id=mini_practice_id,
        )
        return entitlement is not None

    async def has_image_access(self, user_id: int, image_id: int) -> bool:
        if await self.has_premium(user_id):
            return True

        entitlement = await queries.get_active_entitlement(
            self.session,
            user_id=user_id,
            entitlement_type=EntitlementType.image_access,
            image_id=image_id,
        )
        return entitlement is not None

    async def has_text_access(self, user_id: int, text_id: int) -> bool:
        if await self.has_premium(user_id):
            return True

        entitlement = await queries.get_active_entitlement(
            self.session,
            user_id=user_id,
            entitlement_type=EntitlementType.text_access,
            text_id=text_id,
        )
        return entitlement is not None

    async def can_buy_product(self, user_id: int, product: Product) -> bool:
        if not product.is_active:
            return False

        if product.is_repeatable:
            return True

        if product.product_type == ProductType.premium_lifetime:
            return not await self.has_premium(user_id)

        if product.product_type == ProductType.article and product.article_id:
            return not await self.has_article_access(user_id, product.article_id)

        if product.product_type == ProductType.music and product.music_id:
            return not await self.has_music_access(user_id, product.music_id)

        if product.product_type == ProductType.video and product.video_id:
            return not await self.has_video_access(user_id, product.video_id)

        if product.product_type == ProductType.mini_practice and product.mini_practice_id:
            return not await self.has_mini_practice_access(user_id, product.mini_practice_id)

        if product.product_type == ProductType.image and product.image_id:
            return not await self.has_image_access(user_id, product.image_id)

        if product.product_type == ProductType.text and product.text_id:
            return not await self.has_text_access(user_id, product.text_id)

        return False

    async def has_additional_practice_access(
        self,
        *,
        user_id: int,
        section: str,
        category_1: str,
        category_2: str,
    ) -> bool:
        if await self.has_premium(user_id):
            return True

        stmt = select(UserEntitlement.id).where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.entitlement_type == EntitlementType.additional_practice_access,
            UserEntitlement.section == section,
            UserEntitlement.category_1 == category_1,
            UserEntitlement.category_2 == category_2,
            UserEntitlement.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
