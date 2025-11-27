from flask import Flask
from flask_admin import Admin
from admin.views import (
    PracticeLogView, PhraseView, AchievementView, UserAchievementView, SubscriptionView
)
from src.database import SessionLocal
from src.models import (
    User, Practice, Mood, Article,
    Music, Favorite, NotificationLog, Emotion, PracticeLog, Phrase, Achievement, UserAchievement, Subscription
)

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

    # Существующие View
    admin.add_view(UserView(User, session, category="Users"))
    admin.add_view(MoodView(Mood, session, category="Content"))
    admin.add_view(PracticeView(Practice, session, category="Content"))
    admin.add_view(ArticleView(Article, session, category="Content"))
    admin.add_view(MusicView(Music, session, category="Content"))
    admin.add_view(EmotionView(Emotion, session, category="Users"))
    admin.add_view(FavoriteView(Favorite, session, category="Users"))
    admin.add_view(NotificationLogView(NotificationLog, session, category="System"))

    # Новые View
    admin.add_view(PracticeLogView(PracticeLog, session, category="Analytics"))
    admin.add_view(PhraseView(Phrase, session, category="Content"))
    admin.add_view(AchievementView(Achievement, session, category="System"))
    admin.add_view(UserAchievementView(UserAchievement, session, category="Analytics"))
    admin.add_view(SubscriptionView(Subscription, session, category="Users"))

    return app
