import os

from flask import Flask
from flask_admin import Admin

from admin.views import (
    NotificationLogView, DefaultView,
)
from src.db.database import SyncSessionLocal
from src.db.models import (
    Article,
    Mood,
    Music,
    NotificationLog,
    Phrase,
    Practice,
    PracticeLog,
    User,
    Video,
    MiniPractice,
    Image,
    TextItem,
    Product,
    Order,
    Payment,
    UserEntitlement,
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
    session = SyncSessionLocal()

    # Существующие View
    admin.add_view(DefaultView(User, session, category="Users"))
    admin.add_view(DefaultView(Mood, session, category="Content"))
    admin.add_view(DefaultView(Practice, session, category="Content"))
    admin.add_view(DefaultView(Article, session, category="Content"))
    admin.add_view(DefaultView(Music, session, category="Content"))
    admin.add_view(NotificationLogView(NotificationLog, session, category="System"))
    admin.add_view(DefaultView(PracticeLog, session, category="Analytics"))
    admin.add_view(DefaultView(Phrase, session, category="Content"))
    admin.add_view(DefaultView(Video, session, category="Content"))
    admin.add_view(DefaultView(MiniPractice, session, category="Content"))
    admin.add_view(DefaultView(Image, session, category="Content"))
    admin.add_view(DefaultView(TextItem, session, category="Content"))
    admin.add_view(DefaultView(Product, session, category="Acquiring"))
    admin.add_view(DefaultView(Order, session, category="Acquiring"))
    admin.add_view(DefaultView(Payment, session, category="Acquiring"))
    admin.add_view(DefaultView(UserEntitlement, session, category="Acquiring"))

    return app
