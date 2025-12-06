# src/emotions.py
from datetime import datetime, timedelta
import logging

from sqlalchemy import func
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.database import SessionLocal
from src.gpt_integration import analyze_emotion_patterns
from src.models import Emotion, Mood, User


async def handle_emotion_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора эмоции из списка"""
    query = update.callback_query
    await query.answer()

    mood_id = int(query.data.replace("log_emotion_", ""))

    db = SessionLocal()
    try:
        mood = db.query(Mood).filter(Mood.id == mood_id).first()
        if not mood:
            await query.edit_message_text("Эмоция не найдена")
            return

        user = db.query(User).filter(User.tg_id == query.from_user.id).first()

        # Записываем эмоцию
        emotion = Emotion(
            user_id=user.id,
            emotion_name=mood.name,
            created_at=datetime.now()
        )
        db.add(emotion)
        db.commit()

        # Получаем анализ через GPT
        analysis = await get_emotion_analysis(user, mood.name)

        await query.edit_message_text(
            f"✅ *Эмоция записана: {mood.icon} {mood.name}*\n\n"
            f"{analysis}\n\n"
            f"Хотите добавить заметку?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📝 Добавить заметку", callback_data=f"add_note_{emotion.id}")],
                    [InlineKeyboardButton("📊 Посмотреть статистику", callback_data="emotion_stats")],
                    [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")]
                ]
            )
        )

    except Exception as e:
        logging.error(f"Ошибка в handle_emotion_selection: {e}")
        await query.edit_message_text("Произошла ошибка при записи эмоции")
    finally:
        db.close()


async def handle_custom_emotion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик для записи своей эмоции"""
    query = update.callback_query
    await query.answer()

    # Просим ввести свою эмоцию
    await query.edit_message_text(
        "✍️ *Запись своей эмоции*\n\n"
        "Опишите одним словом или короткой фразой, что вы чувствуете сейчас:",
        parse_mode='Markdown'
    )

    context.user_data['waiting_for_custom_emotion'] = True


async def handle_custom_emotion_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста с кастомной эмоцией"""
    if not context.user_data.get('waiting_for_custom_emotion'):
        return

    emotion_text = update.message.text
    user_id = update.effective_user.id

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()

        # Записываем эмоцию
        emotion = Emotion(
            user_id=user.id,
            emotion_name=emotion_text,
            created_at=datetime.now()
        )
        db.add(emotion)
        db.commit()

        # Получаем анализ
        analysis = await get_emotion_analysis(user, emotion_text)

        await update.message.reply_text(
            f"✅ *Эмоция записана: {emotion_text}*\n\n"
            f"{analysis}\n\n"
            f"Хотите добавить заметку?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📝 Добавить заметку", callback_data=f"add_note_{emotion.id}")],
                    [InlineKeyboardButton("📊 Посмотреть статистику", callback_data="emotion_stats")],
                    [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")]
                ]
            )
        )

        context.user_data.pop('waiting_for_custom_emotion', None)

    except Exception as e:
        logging.error(f"Ошибка в handle_custom_emotion_text: {e}")
        await update.message.reply_text("Произошла ошибка при записи эмоции")
    finally:
        db.close()


async def handle_add_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик добавления заметки к эмоции"""
    query = update.callback_query
    await query.answer()

    emotion_id = int(query.data.replace("add_note_", ""))
    context.user_data['editing_emotion_id'] = emotion_id

    await query.edit_message_text(
        "📝 *Добавление заметки*\n\n"
        "Напишите заметку к вашей эмоции. Что вызвало это состояние? "
        "О чем вы думали в этот момент?",
        parse_mode='Markdown'
    )


async def handle_note_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста заметки"""
    if 'editing_emotion_id' not in context.user_data:
        return

    emotion_id = context.user_data['editing_emotion_id']
    note_text = update.message.text

    db = SessionLocal()
    try:
        emotion = db.query(Emotion).filter(Emotion.id == emotion_id).first()
        if emotion:
            emotion.note = note_text
            db.commit()

            await update.message.reply_text(
                "✅ *Заметка сохранена!*\n\n"
                "Ваша эмоция и заметка записаны в дневник.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("📊 Посмотреть статистику", callback_data="emotion_stats")],
                        [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")]
                    ]
                )
            )
        else:
            await update.message.reply_text("Эмоция не найдена")

    except Exception as e:
        logging.error(f"Ошибка в handle_note_text: {e}")
        await update.message.reply_text("Произошла ошибка при сохранении заметки")
    finally:
        context.user_data.pop('editing_emotion_id', None)
        db.close()


async def show_emotion_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику эмоций"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()

        # Получаем статистику за последние 30 дней
        thirty_days_ago = datetime.now() - timedelta(days=30)

        # Самые частые эмоции
        frequent_emotions = db.query(
            Emotion.emotion_name,
            func.count(Emotion.id).label('count')
        ).filter(
            Emotion.user_id == user.id,
            Emotion.created_at >= thirty_days_ago
        ).group_by(Emotion.emotion_name).order_by(func.count(Emotion.id).desc()).limit(5).all()

        # Эмоции по дням недели
        emotions_by_day = db.query(
            func.extract('dow', Emotion.created_at).label('day_of_week'),
            func.string_agg(Emotion.emotion_name, ', ').label('emotions')
        ).filter(
            Emotion.user_id == user.id,
            Emotion.created_at >= thirty_days_ago
        ).group_by(func.extract('dow', Emotion.created_at)).all()

        # Формируем текст
        text = "📊 *Статистика эмоций*\n\n"

        if frequent_emotions:
            text += "*Частые эмоции:*\n"
            for emotion, count in frequent_emotions:
                text += f"• {emotion}: {count} раз\n"
            text += "\n"

        # GPT-анализ
        gpt_analysis = await analyze_emotion_patterns(user.id)
        if gpt_analysis:
            text += f"*Анализ паттернов:*\n{gpt_analysis}\n\n"

        text += "Вы можете продолжить отслеживать эмоции для более детальной статистики."

        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("📈 График эмоций", callback_data="emotion_chart")],
                    [InlineKeyboardButton("📅 Экспорт данных", callback_data="export_emotions")],
                    [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu")]
                ]
            )
        )

    except Exception as e:
        logging.error(f"Ошибка в show_emotion_stats: {e}")
        await query.edit_message_text("Произошла ошибка при загрузке статистики")
    finally:
        db.close()


async def show_emotion_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает график эмоций (генерирует изображение)"""
    query = update.callback_query
    await query.answer()

    # TODO: Реализовать генерацию графика с помощью matplotlib/seaborn
    await query.edit_message_text(
        "📈 *График эмоций*\n\n"
        "Эта функция скоро будет доступна!\n"
        "Мы работаем над визуализацией ваших эмоций.",
        parse_mode='Markdown'
    )


async def export_emotions_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Экспорт данных эмоций в CSV"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tg_id == user_id).first()

        # Получаем все эмоции пользователя
        emotions = db.query(Emotion).filter(
            Emotion.user_id == user.id
        ).order_by(Emotion.created_at).all()

        # Создаем CSV
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow(['Дата', 'Время', 'Эмоция', 'Заметка'])

        # Данные
        for emotion in emotions:
            writer.writerow(
                [
                    emotion.created_at.strftime('%Y-%m-%d') if emotion.created_at else '',
                    emotion.created_at.strftime('%H:%M') if emotion.created_at else '',
                    emotion.emotion_name,
                    emotion.note or ''
                ]
            )

        # Отправляем файл
        from telegram import InputFile
        csv_data = io.BytesIO(output.getvalue().encode())
        csv_data.name = f'emotions_export_{datetime.now().strftime("%Y%m%d")}.csv'

        await context.bot.send_document(
            chat_id=user.tg_id,
            document=InputFile(csv_data, filename=csv_data.name),
            caption="📁 *Экспорт данных эмоций*\n\nВаши записи из дневника эмоций."
        )

        await query.edit_message_text(
            "✅ *Данные экспортированы!*\n\n"
            "Файл CSV отправлен вам в чат.",
            parse_mode='Markdown'
        )

    except Exception as e:
        logging.error(f"Ошибка в export_emotions_data: {e}")
        await query.edit_message_text("Произошла ошибка при экспорте данных")
    finally:
        db.close()


async def get_emotion_analysis(user: User, emotion: str) -> str:
    """Получает анализ эмоции через GPT"""
    try:
        # TODO: Реализовать вызов GPT API
        # Временные ответы
        analyses = {
            "радость": "Отлично! Радость - прекрасное состояние. Попробуйте поделиться им с кем-то сегодня.",
            "спокойствие": "Спокойствие - признак гармонии. Цените эти моменты внутреннего покоя.",
            "тревога": "Тревога - естественная реакция. Попробуйте технику 4-7-8: вдох на 4, задержка на 7, выдох на 8.",
            "злость": "Энергия злости может быть преобразована. Попробуйте интенсивное дыхание для высвобождения.",
            "грусть": "Грусть имеет свою глубину. Позвольте себе почувствовать, не сопротивляясь."
        }

        return analyses.get(
            emotion.lower(),
            "Спасибо за запись. Отслеживание эмоций - важный шаг к осознанности."
            )

    except Exception as e:
        logging.error(f"Ошибка в get_emotion_analysis: {e}")
        return "Спасибо за запись вашей эмоции. Продолжайте наблюдать за своим состоянием."