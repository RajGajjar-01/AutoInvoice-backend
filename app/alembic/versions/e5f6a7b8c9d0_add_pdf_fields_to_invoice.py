"""add pricing, po number and bank detail fields to invoice

Revision ID: e5f6a7b8c9d0
Revises: b7c1d2e3f4a5
Create Date: 2026-11-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "b7c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("po_number", sa.String(100), nullable=True))
    op.add_column(
        "invoices", sa.Column("discount_type", sa.String(10), nullable=True)
    )
    op.add_column(
        "invoices",
        sa.Column("discount_value", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "invoices",
        sa.Column("shipping_charge", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "invoices", sa.Column("extra_charge_label", sa.String(100), nullable=True)
    )
    op.add_column(
        "invoices",
        sa.Column(
            "extra_charge_amount", sa.Float(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "round_off", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "bank_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade():
    op.drop_column("invoices", "bank_details")
    op.drop_column("invoices", "round_off")
    op.drop_column("invoices", "extra_charge_amount")
    op.drop_column("invoices", "extra_charge_label")
    op.drop_column("invoices", "shipping_charge")
    op.drop_column("invoices", "discount_value")
    op.drop_column("invoices", "discount_type")
    op.drop_column("invoices", "po_number")
