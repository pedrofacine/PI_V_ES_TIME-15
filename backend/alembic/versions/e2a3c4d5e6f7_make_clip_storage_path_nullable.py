"""make clip storage_path nullable

Revision ID: e2a3c4d5e6f7
Revises: b1a2c3d4e5f6
Create Date: 2026-09-03 23:18:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e2a3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make storage_path nullable in clips
    op.alter_column('clips', 'storage_path', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Revert storage_path in clips to not nullable
    op.alter_column('clips', 'storage_path', existing_type=sa.String(), nullable=False)

