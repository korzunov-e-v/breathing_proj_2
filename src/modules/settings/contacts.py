from sqlalchemy import select
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes

from src.context import UserContextData, UserState
from src.db.database import AsyncSessionLocal
from src.db.models import User


async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact:
        return
    if contact.user_id != update.effective_user.id:
        await update.message.reply_text("Пожалуйста отправьте свой номер.")
        return
    phone = contact.phone_number
    user_ctx: UserContextData = context.user_data
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = result.scalar_one()
        user.phone = phone
        await db.commit()
    if user_ctx.state == UserState.WAITING_PHONE:
        user_ctx.state = UserState.WAITING_EMAIL
    await update.message.reply_text(
        "Телефон сохранён. Теперь введите email.",
        reply_markup=ReplyKeyboardRemove(),
    )

async def handle_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ctx: UserContextData = context.user_data
    if user_ctx.state != UserState.WAITING_EMAIL:
        return
    email = update.message.text
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = result.scalar_one()
        user.email = email
        await db.commit()
    user_ctx.state = UserState.IDLE
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌌 Продолжить", callback_data="subscription")],
        ]
    )
    await update.message.reply_text(
        "Email сохранён. Теперь можно продолжить.", reply_markup=keyboard
    )
