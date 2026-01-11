from sqlalchemy.orm import Session

from src.db.database import create_tables, get_db
from src.db.models import User


def create_user(db: Session, username: str, tg_id: int):
    """Создает нового пользователя в базе данных.

    Args:
        db: Сессия базы данных SQLAlchemy.
        username: Имя пользователя (Telegram username).
        tg_id: Уникальный идентификатор пользователя в Telegram.

    Returns:
        User: Созданный объект пользователя с обновленными данными из базы.
    """
    db_user = User(username=username, tg_id=tg_id)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_username(db: Session, username: str):
    """Получает пользователя по имени пользователя.

    Args:
        db: Сессия базы данных SQLAlchemy.
        username: Имя пользователя для поиска.

    Returns:
        User: Найденный объект пользователя или None, если пользователь не найден.
    """
    return db.query(User).filter(User.username == username).first()


def get_user_by_tg_id(db: Session, tg_id: int):
    """Получает пользователя по Telegram ID.

    Args:
        db: Сессия базы данных SQLAlchemy.
        tg_id: Уникальный идентификатор пользователя в Telegram.

    Returns:
        User: Найденный объект пользователя или None, если пользователь не найден.
    """
    return db.query(User).filter(User.tg_id == tg_id).first()

# При запуске приложения создаем таблицы
create_tables()

if __name__ == '__main__':
    with get_db() as session:
        user = create_user(session, "test_user", 123456789)
