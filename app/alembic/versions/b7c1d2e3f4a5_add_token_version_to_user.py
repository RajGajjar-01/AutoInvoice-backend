"""Add token_version to user for server-side session revocation

Revision ID: b7c1d2e3f4a5
Revises: fe56fa70289e
Create Date: 2026-11-02 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c1d2e3f4a5"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("user", "token_version")
