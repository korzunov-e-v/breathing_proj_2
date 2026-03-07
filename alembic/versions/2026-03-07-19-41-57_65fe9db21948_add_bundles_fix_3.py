"""add bundles fix 3

Revision ID: 65fe9db21948
Revises: 364bb5e03777
Create Date: 2026-03-07 19:41:57.950426

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65fe9db21948'
down_revision: Union[str, Sequence[str], None] = '364bb5e03777'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TYPE producttype ADD VALUE IF NOT EXISTS 'bundle'")


def downgrade():
    pass
