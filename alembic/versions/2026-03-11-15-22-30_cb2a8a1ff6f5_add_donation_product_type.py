"""add donation product type

Revision ID: cb2a8a1ff6f5
Revises: f4a2b1c3d5f6
Create Date: 2026-03-11 15:22:30.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "cb2a8a1ff6f5"
down_revision: Union[str, Sequence[str], None] = "f4a2b1c3d5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE producttype ADD VALUE IF NOT EXISTS 'donation'")


def downgrade() -> None:
    pass
