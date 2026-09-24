"""add google_sub column and make hashed_password nullable

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("google_sub", sa.String(255), nullable=True))
    op.create_index(op.f("ix_user_google_sub"), "user", ["google_sub"], unique=True)
    op.alter_column(
        "user", "hashed_password", existing_type=sa.String(), nullable=True
    )


def downgrade():
    op.alter_column(
        "user", "hashed_password", existing_type=sa.String(), nullable=False
    )
    op.drop_index(op.f("ix_user_google_sub"), table_name="user")
    op.drop_column("user", "google_sub")
