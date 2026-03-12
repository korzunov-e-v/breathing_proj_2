import base64
import json

from sqlalchemy import select
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.db.database import AsyncSessionLocal
from src.db.models import Music, User
from src.modules.acquiring.access import AccessService
from src.modules.menu_renderer import replace_menu_message


def _encode_music_context(category, subcategory):
    payload = json.dumps({"cat": category, "sub": subcategory}, ensure_ascii=False)
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _decode_music_context(encoded_payload):
    if not encoded_payload:
        return None, None
    padding_len = (-len(encoded_payload)) % 4
    encoded = encoded_payload + ("=" * padding_len)
    try:
        decoded = base64.urlsafe_b64decode(encoded.encode("ascii"))
        payload = json.loads(decoded)
    except (ValueError, TypeError):
        return None, None
    return payload.get("cat"), payload.get("sub")


async def show_music_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории музыки из БД"""
    query = update.callback_query
    if query:
        await query.answer()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Music.category_1)
            .where(Music.section == "library")
            .distinct()
        )
        categories = result.scalars().all()

        buttons = [
            [InlineKeyboardButton(cat, callback_data=f"music_category_{cat}")]
            for cat in categories if cat
        ]
        if not buttons:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text="🎶 Звуки и вибрации\n\nКатегории пока не добавлены.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data="library")]]
                ),
                media_files=None,
            )
            return

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library")])

        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text="🎶 Звуки и вибрации\n\nВыбери категорию:",
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )


async def show_music_by_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает подкатегории музыки для выбранной категории"""
    query = update.callback_query
    await query.answer()

    category = query.data.replace("music_category_", "", 1)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Music.category_2)
            .where(
                Music.category_1 == category,
                Music.section == "library"
            )
            .distinct()
            .order_by(Music.category_2)
        )
        subcategories = result.scalars().all()

        if not subcategories:
            context_payload = _encode_music_context(category, None)
            return await _render_music_tracks(
                update,
                context,
                category,
                None,
                context_payload,
            )

        buttons = []
        for subcategory in subcategories:
            display = subcategory or "Без подкатегории"
            context_payload = _encode_music_context(category, subcategory)
            buttons.append([
                InlineKeyboardButton(
                    display,
                    callback_data=f"music_subcategory_{context_payload}"
                )
            ])

        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="library_sounds")])

        return await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=f"🎶 {category}\n\nВыбери подкатегорию:",
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )


async def show_music_by_subcategory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает треки внутри выбранной подкатегории"""
    query = update.callback_query
    await query.answer()

    payload = query.data.replace("music_subcategory_", "", 1)
    category, subcategory = _decode_music_context(payload)
    return await _render_music_tracks(
        update,
        context,
        category,
        subcategory,
        payload,
    )


async def _render_music_tracks(update, context, category, subcategory, context_payload):
    encoded_context = context_payload or _encode_music_context(category, subcategory)

    async with AsyncSessionLocal() as db:
        stmt = select(Music).where(Music.section == "library")
        if category:
            stmt = stmt.where(Music.category_1 == category)
        else:
            stmt = stmt.where(Music.category_1.is_(None))

        if subcategory is None:
            stmt = stmt.where(Music.category_2.is_(None))
        else:
            stmt = stmt.where(Music.category_2 == subcategory)

        stmt = stmt.order_by(Music.id)
        result = await db.execute(stmt)
        music_tracks = result.scalars().all()

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)

        if not music_tracks:
            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=(f"🎶 {category or 'Музыка'}"
                      "\n\nВ этой подкатегории пока нет треков."),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔙 Назад", callback_data=(
                        f"music_category_{category}" if category is not None else "library_sounds"
                    ))]]
                ),
                media_files=None,
            )
            return

        buttons = []
        has_locked_premium = False
        for music in music_tracks:
            has_access = bool(user) and await access_service.has_music_access(
                user.id,
                music.id,
            )
            prefix = "$ " if music.premium and not has_access else ""
            callback_data = f"music_{music.id}"
            if encoded_context:
                callback_data = f"{callback_data}|{encoded_context}"

            title = (
                "Премиум контент"
                if music.premium and not has_access
                else music.title
            )
            buttons.append([InlineKeyboardButton(f"{prefix}{title}", callback_data=callback_data)])
            if music.premium and not has_access:
                has_locked_premium = True

        back_callback = f"music_category_{category}" if category is not None else "library_sounds"
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data=back_callback)])

        heading = category or "Музыка"
        if subcategory:
            heading = f"{heading} — {subcategory}"

        text = f"🎶 {heading}\n\nВыбери трек:"
        if has_locked_premium:
            text += "\n\n$ - треки доступны по подписке"

        await replace_menu_message(
            chat_id=update.effective_chat.id,
            context=context,
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            media_files=None,
        )


async def play_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню с музыкой с возможностью воспроизведения"""
    query = update.callback_query
    await query.answer()

    data = query.data
    music_identifier, _, context_payload = data.partition("|")
    music_id = int(music_identifier.replace("music_", "", 1))

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Music).where(
                Music.id == music_id,
                Music.section == "library"
            )
        )
        music: Music = result.scalars().first()

        user_result = await db.execute(
            select(User).where(User.tg_id == update.effective_user.id)
        )
        user = user_result.scalars().first()
        access_service = AccessService(db)
        has_access = bool(user) and await access_service.has_music_access(
            user.id,
            music.id,
        )
        if context_payload:
            category_callback = f"music_subcategory_{context_payload}"
        elif music.category_1:
            category_callback = f"music_category_{music.category_1}"
        else:
            category_callback = "library_sounds"

        category_title = music.category_2 or music.category_1 or "Музыка"

        # Определяем доступность трека
        if music.premium and not has_access:
            text = f"🎶 {category_title}\n\n🔒 Этот трек доступен только после покупки."
            buy_callback = f"buy_music_{music.id}"
            if context_payload:
                buy_callback = f"{buy_callback}|{context_payload}"

            buttons = [
                [InlineKeyboardButton("✨ Купить трек", callback_data=buy_callback)],
                [InlineKeyboardButton("🔙 Назад к трекам", callback_data=category_callback)]
            ]

            await replace_menu_message(
                chat_id=update.effective_chat.id,
                context=context,
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                media_files=None,
            )
        else:
            # Доступный трек - отправляем аудио напрямую
            await context.bot.send_audio(
                chat_id=update.effective_chat.id,
                audio=music.audio_id
            )
