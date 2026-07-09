"""add google oauth fields to user

Revision ID: 12d81af290fd
Revises: 001_initial
Create Date: 2026-07-09 00:39:08.918489

"""
from alembic import op
import sqlalchemy as sa

revision = "12d81af290fd"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("google_email", sa.String(255), nullable=True))
    op.add_column("user", sa.Column("google_access_token", sa.String(4096), nullable=True))
    op.add_column("user", sa.Column("google_refresh_token", sa.String(4096), nullable=True))
    op.add_column(
        "user",
        sa.Column("google_token_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("user", "google_token_expires_at")
    op.drop_column("user", "google_refresh_token")
    op.drop_column("user", "google_access_token")
    op.drop_column("user", "google_email")
