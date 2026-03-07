from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    Order,
    OrderStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    Product,
    ProductType,
    User,
    UserEntitlement, EntitlementType, ProductItem,
)
from src.modules.acquiring import queries
from src.modules.acquiring.access import AccessService
from src.modules.acquiring.payment_gateway import (
    build_receipt_item,
    create_yookassa_payment,
    get_yookassa_payment,
)


class AcquiringError(Exception):
    pass


class ProductNotFoundError(AcquiringError):
    pass


class ProductNotAvailableError(AcquiringError):
    pass


class PaymentNotFoundError(AcquiringError):
    pass


@dataclass(slots=True)
class CheckoutResult:
    order_id: int
    payment_id: int
    provider_payment_id: str
    confirmation_url: str | None
    status: str


class AcquiringService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.access_service = AccessService(session)

    async def create_checkout(
        self,
        *,
        user: User,
        product_code: str,
        user_phone: str | None = None,
        user_email: str | None = None,
    ) -> CheckoutResult:
        product = await queries.get_product_by_code(self.session, product_code)
        if not product:
            raise ProductNotFoundError(f"Product with code={product_code} not found")

        can_buy = await self.access_service.can_buy_product(user.id, product)
        if not can_buy:
            raise ProductNotAvailableError(f"User {user.id} cannot buy product {product.code}")

        order = await self._create_order(user_id=user.id, product=product)
        payment = await self._create_payment_for_order(
            user=user,
            order=order,
            product=product,
            user_phone=user_phone,
            user_email=user_email,
        )

        await self.session.commit()
        await self.session.refresh(order)
        await self.session.refresh(payment)

        return CheckoutResult(
            order_id=order.id,
            payment_id=payment.id,
            provider_payment_id=payment.provider_payment_id,
            confirmation_url=payment.confirmation_url,
            status=payment.status.value,
        )

    async def sync_payment_status(self, *, payment_id: int) -> Payment:
        payment = await queries.get_payment_by_id(self.session, payment_id)
        if not payment:
            raise PaymentNotFoundError(f"Payment with id={payment_id} not found")

        gateway_payment = get_yookassa_payment(payment.provider_payment_id)

        payment.status = PaymentStatus(gateway_payment.status)
        payment.paid = gateway_payment.paid
        payment.refundable = gateway_payment.refundable
        payment.test = gateway_payment.test
        payment.payment_method_type = gateway_payment.payment_method_type
        payment.payment_method_id = gateway_payment.payment_method_id
        payment.raw_response = json.dumps(gateway_payment.raw_response, ensure_ascii=False)
        payment.confirmation_url = gateway_payment.confirmation_url
        payment.last_checked_at = self._now()
        payment.status_synced_at = self._now()
        payment.check_attempts += 1
        payment.status_description = gateway_payment.status

        if payment.status in {PaymentStatus.succeeded, PaymentStatus.canceled}:
            payment.finalized_at = self._now()

        if payment.status == PaymentStatus.succeeded:
            payment.confirmed_at = self._now()
            await self._finalize_successful_payment(payment)

        elif payment.status == PaymentStatus.canceled:
            payment.order.status = OrderStatus.canceled

        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(payment)

        return payment

    async def grant_entitlement_once(self, *, order: Order) -> UserEntitlement | None:
        product = order.product

        if product.product_type == ProductType.premium_lifetime:
            entitlement_type = EntitlementType.premium_lifetime

            existing = await queries.get_active_entitlement(
                self.session,
                user_id=order.user_id,
                entitlement_type=entitlement_type,
            )
            if existing:
                return existing

            entitlement = UserEntitlement(
                user_id=order.user_id,
                entitlement_type=entitlement_type,
                product_id=product.id,
                order_id=order.id,
                is_active=True,
            )
            self.session.add(entitlement)
            await self.session.flush()
            return entitlement

        if product.product_type == ProductType.bundle:
            for item in product.items:
                await self._grant_entitlement_for_product_item(
                    order=order,
                    product=product,
                    item=item,
                )
            return None

        entitlement_type = queries.map_product_type_to_entitlement_type(product.product_type)

        filters = {
            "article_id": product.article_id,
            "music_id": product.music_id,
            "video_id": product.video_id,
            "mini_practice_id": product.mini_practice_id,
            "image_id": product.image_id,
            "text_id": product.text_id,
        }
        not_none_filters = {k: v for k, v in filters.items() if v is not None}

        existing = await queries.get_active_entitlement(
            self.session,
            user_id=order.user_id,
            entitlement_type=entitlement_type,
            **not_none_filters,
        )
        if existing:
            return existing

        entitlement = UserEntitlement(
            user_id=order.user_id,
            entitlement_type=entitlement_type,
            product_id=product.id,
            order_id=order.id,
            article_id=product.article_id,
            music_id=product.music_id,
            video_id=product.video_id,
            mini_practice_id=product.mini_practice_id,
            image_id=product.image_id,
            text_id=product.text_id,
            is_active=True,
        )
        self.session.add(entitlement)
        await self.session.flush()
        return entitlement

    async def _grant_entitlement_for_product_item(
        self,
        *,
        order: Order,
        product: Product,
        item: ProductItem,
    ) -> UserEntitlement | None:
        entitlement_type = queries.map_product_item_type_to_entitlement_type(item.item_type)

        filters = {
            "article_id": item.article_id,
            "music_id": item.music_id,
            "video_id": item.video_id,
            "mini_practice_id": item.mini_practice_id,
            "image_id": item.image_id,
            "text_id": item.text_id,
        }
        not_none_filters = {k: v for k, v in filters.items() if v is not None}

        existing = await queries.get_active_entitlement(
            self.session,
            user_id=order.user_id,
            entitlement_type=entitlement_type,
            **not_none_filters,
        )
        if existing:
            return existing

        entitlement = UserEntitlement(
            user_id=order.user_id,
            entitlement_type=entitlement_type,
            product_id=product.id,
            order_id=order.id,
            article_id=item.article_id,
            music_id=item.music_id,
            video_id=item.video_id,
            mini_practice_id=item.mini_practice_id,
            image_id=item.image_id,
            text_id=item.text_id,
            is_active=True,
        )
        self.session.add(entitlement)
        await self.session.flush()
        return entitlement

    async def _create_order(self, *, user_id: int, product: Product) -> Order:
        order = Order(
            user_id=user_id,
            product_id=product.id,
            status=OrderStatus.waiting_for_payment,
            amount_value=product.price_value,
            currency=product.currency,
            external_ref=self._make_external_ref(),
        )
        self.session.add(order)
        await self.session.flush()
        return order

    async def _create_payment_for_order(
        self,
        *,
        user: User,
        order: Order,
        product: Product,
        user_phone: str | None,
        user_email: str | None,
    ) -> Payment:
        payment_idempotence_key = self._make_idempotence_key()
        receipt_items = [
            build_receipt_item(
                description=product.title,
                amount_value_kopecks=order.amount_value,
            )
        ]

        metadata = {
            "order_id": order.id,
            "product_id": product.id,
            "user_id": user.id,
            "product_code": product.code,
        }

        gateway_payment = create_yookassa_payment(
            amount_value_kopecks=order.amount_value,
            description=product.title,
            customer_id=str(user.tg_id),
            metadata=metadata,
            receipt_items=receipt_items,
            idempotence_key=payment_idempotence_key,
            user_phone=user_phone,
            user_email=user_email,
        )

        payment = Payment(
            order_id=order.id,
            provider=PaymentProvider.yookassa,
            provider_payment_id=gateway_payment.provider_payment_id,
            idempotence_key=payment_idempotence_key,
            status=PaymentStatus(gateway_payment.status),
            amount_value=order.amount_value,
            currency=order.currency,
            paid=gateway_payment.paid,
            refundable=gateway_payment.refundable,
            test=gateway_payment.test,
            payment_method_type=gateway_payment.payment_method_type,
            payment_method_id=gateway_payment.payment_method_id,
            confirmation_url=gateway_payment.confirmation_url,
            raw_response=json.dumps(gateway_payment.raw_response, ensure_ascii=False),
            status_description=gateway_payment.status,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def _finalize_successful_payment(self, payment: Payment) -> None:
        order = payment.order

        if order.status != OrderStatus.paid:
            order.status = OrderStatus.paid
            order.paid_at = self._now()

        await self.grant_entitlement_once(order=order)

    @staticmethod
    def _make_idempotence_key() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _make_external_ref() -> str:
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _now():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc)
