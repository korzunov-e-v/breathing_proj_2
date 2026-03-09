"""fix types

Revision ID: 159cfaa13dc1
Revises: 9232ee6ac878
Create Date: 2026-03-07 21:03:47.876720

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '159cfaa13dc1'
down_revision: Union[str, Sequence[str], None] = '9232ee6ac878'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.execute("ALTER TYPE producttype ADD VALUE IF NOT EXISTS 'bundle'")
    op.execute("ALTER TYPE producttype ADD VALUE IF NOT EXISTS 'additional_practice'")
    op.execute("ALTER TYPE entitlementtype ADD VALUE IF NOT EXISTS 'additional_practice_access'")


def downgrade():
    pass
