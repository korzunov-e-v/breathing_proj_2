from sqlalchemy.orm import Session
from src.database import get_db, create_tables
from src.models import User


# Пример функции для работы с базой данных
def create_user(db: Session, username: str, tg_id: int):
    db_user = User(username=username, tg_id=tg_id)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_tg_id(db: Session, tg_id: int):
    return db.query(User).filter(User.tg_id == tg_id).first()

# При запуске приложения создаем таблицы
create_tables()

if __name__ == '__main__':
    session = get_db().__next__()
    user = create_user(session, "test_user", 123456789)
    session.commit()