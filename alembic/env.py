# alembic/env.py
from logging.config import fileConfig
import os
import sys

from sqlalchemy import create_engine, pool

from alembic import context


# Добавляем путь к проекту в sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.db.models import *
from src.settings import settings


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def get_url():
    """Получаем URL базы данных без asyncpg для Alembic"""
    # Преобразуем URL: заменяем asyncpg на psycopg2 для Alembic
    url = str(settings.db_url).replace('+asyncpg', '+psycopg2')
    print(f"Alembic database URL: {url}")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Создаем движок напрямую, минуя engine_from_config
    url = get_url()

    # Создаем движок SQLAlchemy
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        echo=False
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
