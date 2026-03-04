from flask import redirect, request, session, url_for
from flask_admin.contrib.sqla import ModelView
from wtforms import TextAreaField, ValidationError
from wtforms.widgets import TextArea

from src.db.models import Image

# Админы по TG ID (замените на свои)
ADMIN_IDS = {392350805}


class BaseSecureModelView(ModelView):
    """Базовый View с проверкой доступа"""

    def is_accessible(self):
        return session.get("tg_id") in ADMIN_IDS

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("login", next=request.url))


class CKTextAreaWidget(TextArea):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('class', 'ckeditor')
        return super(CKTextAreaWidget, self).__call__(field, **kwargs)


class CKTextAreaField(TextAreaField):
    widget = CKTextAreaWidget()


# admin/views.py
class MoodView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class PracticeView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class UserView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class EmotionView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None

    column_formatters = {
        'user': lambda v, c, m, p: f"{m.user.username} (ID: {m.user.tg_id})" if m.user else None,
        'created_at': lambda v, c, m, p: m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else ''
    }


class ArticleView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class MusicView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class MiniPracticeView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class VideoView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class TextView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


class FavoriteView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None

    column_formatters = {
        'user': lambda v, c, m, p: f"{m.user.username} (ID: {m.user.tg_id})" if m.user else None
    }


class NotificationLogView(BaseSecureModelView):
    column_list = ("id", "user", "type", "sent_at")
    column_filters = ("type", "sent_at")

    column_formatters = {
        'user': lambda v, c, m, p: f"{m.user.username} (ID: {m.user.tg_id})" if m.user else None,
        'sent_at': lambda v, c, m, p: m.sent_at.strftime('%Y-%m-%d %H:%M') if m.sent_at else ''
    }
    # can_create = False
    # can_edit = False
    # can_delete = False


class PracticeLogView(BaseSecureModelView):
    column_list = ("id", "user", "practice", "completed_at", "feedback_rating")
    column_filters = ("completed_at", "feedback_rating")
    form_columns = ("practice", "mood_before", "mood_after", "completed_at", "feedback_rating", "feedback_comment")


class PhraseView(BaseSecureModelView):
    column_list = ("id", "text", "category", "for_premium")
    column_searchable_list = ("text",)
    column_filters = ("category", "for_premium")
    form_columns = ("text", "category", "for_premium")

    form_overrides = {
        'text': CKTextAreaField
    }


class AchievementView(BaseSecureModelView):
    column_list = ("id", "name", "condition_type", "condition_value")
    column_searchable_list = ("name",)
    column_filters = ("condition_type",)
    form_columns = ("name", "description", "icon", "condition_type", "condition_value")


class UserAchievementView(BaseSecureModelView):
    column_list = ("id", "user", "achievement", "unlocked_at")
    column_filters = ("unlocked_at",)
    form_columns = ("user", "achievement")
    can_create = False  # Разблокируются автоматически


class SubscriptionView(BaseSecureModelView):
    column_list = ("id", "user", "plan_type", "started_at", "expires_at", "is_active")
    column_filters = ("plan_type", "is_active", "started_at")
    form_columns = ("user", "plan_type", "started_at", "expires_at", "is_active")


class ImageView(BaseSecureModelView):
    column_list = ("id", "title", "image_id")
    form_columns = ("title", "image_id",)
