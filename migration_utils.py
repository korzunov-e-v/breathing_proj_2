# migration_utils.py
import os
import sys

from alembic import command
from alembic.config import Config


def run_migrations():
    """Запустить миграции"""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

def create_migration(message):
    """Создать новую миграцию"""
    alembic_cfg = Config("alembic.ini")
    command.revision(alembic_cfg, autogenerate=True, message=message)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "migrate":
            run_migrations()
        elif sys.argv[1] == "create" and len(sys.argv) > 2:
            create_migration(sys.argv[2])
        else:
            print("Usage: python migration_utils.py [migrate|create 'message']")
    else:
        print("Usage: python migration_utils.py [migrate|create 'message']")