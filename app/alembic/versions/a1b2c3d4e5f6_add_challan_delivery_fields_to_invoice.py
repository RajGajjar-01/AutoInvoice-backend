"""add challan delivery fields to invoice

Revision ID: a1b2c3d4e5f6
Revises: 12d81af290fd
Create Date: 2026-07-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "12d81af290fd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("vehicle_info", sa.String(200), nullable=True))
    op.add_column(
        "invoices", sa.Column("delivery_notes", sa.String(1000), nullable=True)
    )


def downgrade():
    op.drop_column("invoices", "delivery_notes")
    op.drop_column("invoices", "vehicle_info")
