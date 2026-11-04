"""add token_version to user (session revocation)

Revision ID: b7c1d2e3f4a5
Revises: d4e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa


revision = "b7c1d2e3f4a5"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("user", "token_version")
