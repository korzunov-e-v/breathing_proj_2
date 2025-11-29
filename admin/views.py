from flask import redirect, request, session, url_for
from flask_admin.contrib.sqla import ModelView
from wtforms import TextAreaField
from wtforms.widgets import TextArea

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
    column_list = ("id", "name", "description", "icon")
    column_searchable_list = ("name",)
    form_columns = ("name", "description", "icon")


class PracticeView(BaseSecureModelView):
    column_list = ("id", "day_number", "mood", "premium", "audio_file_id")
    column_filters = ("day_number", "premium", "mood")
    form_columns = ("day_number", "mood", "audio_file_id", "intro_text", "outro_text", "premium")

    # Для отображения связанной модели в списке
    column_formatters = {
        'mood': lambda v, c, m, p: m.mood.name if m.mood else None
    }


class UserView(BaseSecureModelView):
    column_list = None
    column_searchable_list = ("tg_id", "username")
    column_filters = ("subscribed", "timezone", "current_day", "streak")
    form_columns = None
    form_excluded_columns = ['created_at']


class EmotionView(BaseSecureModelView):
    column_list = ("id", "user", "emotion_name", "created_at")
    column_filters = ("emotion_name", "created_at")

    column_formatters = {
        'user': lambda v, c, m, p: f"{m.user.username} (ID: {m.user.tg_id})" if m.user else None,
        'created_at': lambda v, c, m, p: m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else ''
    }


class ArticleView(BaseSecureModelView):
    column_list = ("id", "title", "category", "premium")
    column_searchable_list = ("title",)
    column_filters = ("category", "premium")
    form_columns = None


class MusicView(BaseSecureModelView):
    column_list = ("id", "audio_id", "category", "premium")
    column_filters = ("category", "premium")
    form_columns = None


class FavoriteView(BaseSecureModelView):
    column_list = ("id", "user", "item_type", "item_id")
    column_filters = ("item_type",)

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
    can_create = False
    can_edit = False
    can_delete = False


class PracticeLogView(BaseSecureModelView):
    column_list = ("id", "user", "practice", "completed_at", "feedback_rating")
    column_filters = ("completed_at", "feedback_rating")
    form_columns = ("user", "practice", "mood_before", "mood_after", "feedback_rating", "feedback_comment")
    can_create = False  # Логи создаются автоматически


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