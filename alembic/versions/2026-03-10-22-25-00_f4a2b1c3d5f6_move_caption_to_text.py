"""move caption from video to texts

Revision ID: f4a2b1c3d5f6
Revises: 38d79399a83e
Create Date: 2026-03-10 22:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a2b1c3d5f6'
down_revision: Union[str, Sequence[str], None] = '38d79399a83e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('texts', sa.Column('caption', sa.String(length=500), nullable=True))
    op.execute(
        """
        UPDATE texts t
        SET caption = v.caption
        FROM video v
        WHERE t.section = v.section
          AND t.category_1 IS NOT DISTINCT FROM v.category_1
          AND t.category_2 IS NOT DISTINCT FROM v.category_2
          AND v.caption IS NOT NULL
        """
    )
    op.drop_column('video', 'caption')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('video', sa.Column('caption', sa.String(length=500), nullable=True))
    op.execute(
        """
        UPDATE video v
        SET caption = t.caption
        FROM texts t
        WHERE t.section = v.section
          AND t.category_1 IS NOT DISTINCT FROM v.category_1
          AND t.category_2 IS NOT DISTINCT FROM v.category_2
          AND t.caption IS NOT NULL
        """
    )
    op.drop_column('texts', 'caption')
