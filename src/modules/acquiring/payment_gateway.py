from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from yookassa import Configuration, Payment
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.currency import Currency
from yookassa.domain.models.receipt import Receipt, ReceiptItem
from yookassa.domain.request.payment_request_builder import PaymentRequestBuilder

from src.settings import settings


Configuration.configure(settings.yookassa_api_key, settings.yookassa_api_secret)


@dataclass(slots=True)
class YooKassaPaymentResult:
    provider_payment_id: str
    status: str
    confirmation_url: str | None
    paid: bool
    refundable: bool
    test: bool
    payment_method_type: str | None
    payment_method_id: str | None
    raw_response: dict[str, Any]


def kopecks_to_rub_decimal(value: int) -> Decimal:
    return (Decimal(value) / Decimal("100")).quantize(Decimal("0.00"))


def build_receipt_item(
    description: str,
    amount_value_kopecks: int,
    quantity: str = "1.00",
    vat_code: int = 1,
    payment_mode: str = "full_payment",
    payment_subject: str = "service",
) -> ReceiptItem:
    item = ReceiptItem()
    item.description = description
    item.quantity = quantity
    item.amount = {
        "value": str(kopecks_to_rub_decimal(amount_value_kopecks)),
        "currency": Currency.RUB,
    }
    item.vat_code = vat_code
    item.payment_mode = payment_mode
    item.payment_subject = payment_subject
    return item


def create_yookassa_payment(
    *,
    amount_value_kopecks: int,
    description: str,
    customer_id: str,
    metadata: dict[str, str | int | bool],
    receipt_items: list[ReceiptItem],
    idempotence_key: str,
    user_phone: str | None = None,
    user_email: str | None = None,
) -> YooKassaPaymentResult:
    receipt = Receipt()
    receipt.items = receipt_items
    receipt.tax_system_code = settings.yookassa_tax_system_code

    customer: dict[str, str] = {}
    if user_phone:
        customer["phone"] = user_phone
    if user_email:
        customer["email"] = user_email
    if customer:
        receipt.customer = customer

    amount = {
        "value": str(kopecks_to_rub_decimal(amount_value_kopecks)),
        "currency": Currency.RUB,
    }
    confirmation = {
        "type": ConfirmationType.REDIRECT,
        "return_url": settings.return_url,
    }

    builder = PaymentRequestBuilder()
    (
        builder.set_amount(amount)
        .set_confirmation(confirmation)
        .set_capture(True)
        .set_description(description)
        .set_metadata(metadata)
        .set_merchant_customer_id(customer_id)
        .set_receipt(receipt)
    )
    request = builder.build()

    response = Payment.create(request, idempotence_key)

    confirmation_url = None
    if getattr(response, "confirmation", None):
        confirmation_url = getattr(response.confirmation, "confirmation_url", None)

    payment_method_type = None
    payment_method_id = None
    if getattr(response, "payment_method", None):
        payment_method_type = getattr(response.payment_method, "type", None)
        payment_method_id = getattr(response.payment_method, "id", None)

    return YooKassaPaymentResult(
        provider_payment_id=response.id,
        status=response.status,
        confirmation_url=confirmation_url,
        paid=bool(getattr(response, "paid", False)),
        refundable=bool(getattr(response, "refundable", False)),
        test=bool(getattr(response, "test", False)),
        payment_method_type=payment_method_type,
        payment_method_id=payment_method_id,
        raw_response=response.json(),
    )


def get_yookassa_payment(provider_payment_id: str) -> YooKassaPaymentResult:
    response = Payment.find_one(provider_payment_id)

    confirmation_url = None
    if getattr(response, "confirmation", None):
        confirmation_url = getattr(response.confirmation, "confirmation_url", None)

    payment_method_type = None
    payment_method_id = None
    if getattr(response, "payment_method", None):
        payment_method_type = getattr(response.payment_method, "type", None)
        payment_method_id = getattr(response.payment_method, "id", None)

    return YooKassaPaymentResult(
        provider_payment_id=response.id,
        status=response.status,
        confirmation_url=confirmation_url,
        paid=bool(getattr(response, "paid", False)),
        refundable=bool(getattr(response, "refundable", False)),
        test=bool(getattr(response, "test", False)),
        payment_method_type=payment_method_type,
        payment_method_id=payment_method_id,
        raw_response=response.json(),
    )
