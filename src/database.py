from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config
from src.settings import settings


# Получаем параметры подключения из переменных окружения
POSTGRES_USER = settings.db_user
POSTGRES_PASSWORD = settings.db_password
POSTGRES_DB = settings.db_name
POSTGRES_HOST = settings.db_host
POSTGRES_PORT = settings.db_port

# Формируем URL для подключения к базе данных
SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Создаем движок базы данных
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # Для разработки можно добавить echo=True для логирования SQL-запросов
    echo=False,
    pool_pre_ping=True,  # Проверяет соединение перед использованием
    pool_recycle=300,  # Переподключается каждые 300 секунд
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


# Зависимость для получения сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Запустить миграции Alembic"""
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✅ Миграции успешно применены")
    except Exception as e:
        print(f"❌ Ошибка при применении миграций: {e}")
        raise


def create_tables():
    """Создать таблицы через миграции"""
    run_migrations()
