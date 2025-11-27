from flask import Flask
from flask_admin import Admin
from admin.views import (
    UserView, PracticeView, MoodView, ArticleView,
    MusicView, FavoriteView, NotificationLogView
)
from src.database import SessionLocal
from src.models import (
    User, Practice, Mood, Article,
    Music, Favorite, NotificationLog, Emotion
)
from src.settings import settings

# admin/admin_app.py
from admin.views import (
    UserView, PracticeView, MoodView, ArticleView,
    MusicView, FavoriteView, NotificationLogView, EmotionView  # Добавили EmotionView
)


def create_admin_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-super-secret-key-change-this'

    from src.settings import settings
    app.config['SQLALCHEMY_DATABASE_URI'] = str(settings.db_url).replace('+asyncpg', '')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    admin = Admin(app, name='Breathing Bot Admin')
    session = SessionLocal()

    # Регистрируем ВСЕ модели
    admin.add_view(UserView(User, session, category="Users"))
    admin.add_view(MoodView(Mood, session, category="Content"))
    admin.add_view(PracticeView(Practice, session, category="Content"))
    admin.add_view(ArticleView(Article, session, category="Content"))
    admin.add_view(MusicView(Music, session, category="Content"))
    admin.add_view(EmotionView(Emotion, session, category="Users"))  # Добавили
    admin.add_view(FavoriteView(Favorite, session, category="Users"))
    admin.add_view(NotificationLogView(NotificationLog, session, category="System"))

    return app