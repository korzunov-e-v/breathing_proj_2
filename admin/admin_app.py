import os

from flask import Flask
from flask_admin import Admin

from admin.views import (
    AchievementView,
    ArticleView,
    EmotionView,
    FavoriteView,
    MoodView,
    MusicView,
    NotificationLogView,
    PhraseView,
    PracticeLogView,
    PracticeView,
    SubscriptionView,
    UserAchievementView,
    UserView,
    VideoView,
    MiniPracticeView, ImageView, TextView,
)
from src.db.database import SessionLocal
from src.db.models import (
    Achievement,
    Article,
    Emotion,
    Favorite,
    Mood,
    Music,
    NotificationLog,
    Phrase,
    Practice,
    PracticeLog,
    Subscription,
    User,
    UserAchievement,
    Video,
    MiniPractice, Image, Texts,
)


def create_admin_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-super-secret-key-change-this'

    if not os.environ.get("DB_URL"):
        from src.settings import settings
        print(f"{settings.db_url=}")
        app.config['SQLALCHEMY_DATABASE_URI'] = str(settings.db_url).replace('+asyncpg', '')
    else:
        print(f"{os.environ.get("DB_URL")=}")
        app.config['SQLALCHEMY_DATABASE_URI'] = str(os.environ.get("DB_URL")).replace('+asyncpg', '')
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
    admin.add_view(PracticeLogView(PracticeLog, session, category="Analytics"))
    admin.add_view(PhraseView(Phrase, session, category="Content"))
    admin.add_view(AchievementView(Achievement, session, category="System"))
    admin.add_view(UserAchievementView(UserAchievement, session, category="Analytics"))
    admin.add_view(SubscriptionView(Subscription, session, category="Users"))
    admin.add_view(VideoView(Video, session, category="Content"))
    admin.add_view(MiniPracticeView(MiniPractice, session, category="Content"))
    admin.add_view(ImageView(Image, session, category="Content"))
    admin.add_view(TextView(Texts, session, category="Content"))

    return app
