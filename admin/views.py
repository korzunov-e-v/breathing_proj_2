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
class DefaultView(BaseSecureModelView):
    column_list = None
    column_filters = None
    form_columns = None


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

