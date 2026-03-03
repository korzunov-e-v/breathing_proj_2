"""Tools for creating payment orders in Yookassa payment system.

This module provides functionality to create and manage payment orders
using the Yookassa payment gateway API. It handles payment request
building, receipt creation, and payment confirmation.

Example:
    >>> from src.yookassa_tools.tools import create_yookassa_order
    >>> response = create_yookassa_order(
    ...     receipt_items=[...],
    ...     user_phone="+79991234567",
    ...     user_email="user@example.com",
    ...     customer_id="cust_123",
    ...     description="Payment for VPN access",
    ...     metadata={"order_id": 123}
    ... )
"""

from yookassa import Configuration, Payment
from yookassa.domain.common.confirmation_type import ConfirmationType
from yookassa.domain.models.currency import Currency
from yookassa.domain.models.receipt import Receipt, ReceiptItem
from yookassa.domain.request.payment_request_builder import PaymentRequestBuilder
from yookassa.domain.response import PaymentResponse

from src.settings import settings

Configuration.configure(settings.yookassa_api_key, settings.yookassa_api_secret)


def create_yookassa_order(
    receipt_items: list[ReceiptItem],
    user_phone: str,
    user_email: str,
    customer_id: str,
    description: str,
    metadata: dict[str, str | int],
) -> PaymentResponse:
    """Create a payment order in Yookassa.

    Args:
        receipt_items: List of items to include in the receipt.
        user_phone: Customer phone number for the receipt.
        user_email: Customer email for the receipt.
        customer_id: Unique customer identifier for merchant.
        description: Payment description shown to the customer.
        metadata: Additional metadata dictionary for the payment.

    Returns:
        PaymentResponse: Response object containing payment details including
            payment ID, status, and confirmation URL for redirect.
    """
    receipt = Receipt()
    receipt.items = receipt_items
    receipt.customer = {"phone": user_phone, "email": user_email}
    receipt.tax_system_code = settings.yookassa_tax_system_code
    amount = {
        "value": sum((a.quantity * a.amount.value) for a in receipt_items),
        "currency": Currency.RUB,
    }
    confirmation = {"type": ConfirmationType.REDIRECT, "return_url": settings.return_url}

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
    res: PaymentResponse = Payment.create(request)

    print(f"{res.id=}")
    print(f"{res.status=}")
    print(f"{res.confirmation.confirmation_url=}")

    return res
