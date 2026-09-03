"""add retention fields

Revision ID: b1a2c3d4e5f6
Revises: dc5867a2d8e8
Create Date: 2026-09-02 22:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'dc5867a2d8e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status column to clips
    op.add_column('clips', sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='TEMPORARY'))
    
    # Make storage_path nullable in videos
    op.alter_column('videos', 'storage_path', existing_type=sa.String(), nullable=True)
    
    # Make image_path nullable in candidates
    op.alter_column('candidates', 'image_path', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Drop status column from clips
    op.drop_column('clips', 'status')
    
    # Revert storage_path in videos to not nullable
    op.alter_column('videos', 'storage_path', existing_type=sa.String(), nullable=False)
    
    # Revert image_path in candidates to not nullable
    op.alter_column('candidates', 'image_path', existing_type=sa.String(), nullable=False)
