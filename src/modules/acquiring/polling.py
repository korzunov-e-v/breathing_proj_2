from __future__ import annotations

import asyncio
import logging
from email.mime import application

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.db.models import (
    Music,
    PaymentStatus,
    ProductType,
    TextItem,
    User,
    Video,
)
from src.modules.acquiring.queries import get_pending_payments
from src.modules.acquiring.service import AcquiringService

logger = logging.getLogger(__name__)


async def poll_pending_payments(
    session_factory: async_sessionmaker[AsyncSession],
    application,
    limit: int = 100,
) -> int:
    while True:
        processed = 0

        async with session_factory() as session:
            payments = await get_pending_payments(session, limit=limit)

            for payment in payments:
                logger.info(f"new_payment {payment}")
                service = AcquiringService(session)
                updated_payment = await service.sync_payment_status(payment_id=payment.id)
                if updated_payment.status == PaymentStatus.succeeded:
                    await _notify_successful_payment(application, session, updated_payment)
                processed += 1

        await asyncio.sleep(5)


async def _notify_successful_payment(application, session, payment):
    order = payment.order
    if not order:
        return

    user = await session.get(User, order.user_id)
    if not user or not user.tg_id:
        return

    product = order.product
    if not product:
        return

    product_name = product.title or product.code
    if not product_name:
        parts = [product.category_1, product.category_2]
        product_name = " — ".join(part for part in parts if part)
    product_name = product_name or "покупка"
    amount_text = f"{product.price_value / 100:.2f} ₽" if product.price_value is not None else ""

    text = (
        "✨ Оплата подтверждена\n\n"
        f"<b>{product_name}</b>\n"
        f"Спасибо тебе за доверие. 🌿\n"
        f"Стоимость: {amount_text}\n\n"
        "Материалы отправляю в этом чате."
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📋 В моё пространство", callback_data="menu")]]
    )
    try:
        await application.bot.send_message(
            chat_id=user.tg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    except Exception as exc:
        logger.error("failed to notify user %s about payment %s: %s", user.tg_id, payment.id, exc)
        return

    if product.product_type == ProductType.additional_practice:
        await _send_additional_practice_materials(
            application=application,
            session=session,
            chat_id=user.tg_id,
            section=product.section,
            category_1=product.category_1,
            category_2=product.category_2,
        )


async def _send_additional_practice_materials(
    *,
    application,
    session,
    chat_id: int,
    section: str | None,
    category_1: str | None,
    category_2: str | None,
) -> None:
    if not section or not category_1 or not category_2:
        return

    videos_result = await session.execute(
        select(Video)
        .where(
            Video.section == section,
            Video.category_1 == category_1,
            Video.category_2 == category_2,
        )
        .order_by(Video.id)
    )
    videos = videos_result.scalars().all()

    audios_result = await session.execute(
        select(Music)
        .where(
            Music.section == section,
            Music.category_1 == category_1,
            Music.category_2 == category_2,
        )
        .order_by(Music.id)
    )
    audios = audios_result.scalars().all()

    texts_result = await session.execute(
        select(TextItem)
        .where(
            TextItem.section == section,
            TextItem.category_1 == category_1,
            TextItem.category_2 == category_2,
        )
        .order_by(TextItem.id)
    )
    texts = texts_result.scalars().all()

    for video in videos:
        fid = getattr(video, "video_id", None)
        if not fid:
            continue
        caption = getattr(video, "title", None) or ""
        try:
            await application.bot.send_video(
                chat_id=chat_id,
                video=fid,
                caption=caption[:1024] if caption else None,
            )
        except Exception:
            logger.exception("failed to send practice video to %s", chat_id)

    for audio in audios:
        fid = getattr(audio, "audio_id", None) or getattr(audio, "file_id", None)
        if not fid:
            continue
        title = getattr(audio, "title", None)
        performer = getattr(audio, "artist", None)
        caption = getattr(audio, "description", None)
        try:
            await application.bot.send_audio(
                chat_id=chat_id,
                audio=fid,
                title=title,
                performer=performer,
                caption=(caption[:1024] if caption else None),
            )
        except Exception:
            logger.exception("failed to send practice audio to %s", chat_id)

    text_parts: list[str] = []
    for text in texts:
        body = (text.text or "").strip()
        if body:
            text_parts.append(body)

    header = f"🧘 {category_1}\n\n{category_2}"

    if text_parts:
        body = "\n\n— — —\n\n".join(text_parts)
        text_message = f"{header}\n\n{body}"
    else:
        text_message = f"{header}\n\nПока нет доступных текстовых материалов, но аудио и видео отправлены."


    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📋 В моё пространство", callback_data="menu")]]
    )
    try:
        await application.bot.send_message(chat_id=chat_id, text=text_message, reply_markup=keyboard)
    except Exception:
        logger.exception("failed to send practice text summary to %s", chat_id)
