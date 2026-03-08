"""extend_customers_fields_for_ui

Revision ID: 5f2c1b8d9eaa
Revises: 0b6f0f2a4c1d
Create Date: 2026-03-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "5f2c1b8d9eaa"
down_revision = "0b6f0f2a4c1d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "customers",
        sa.Column(
            "party_type",
            sa.VARCHAR(length=20),
            nullable=True,
            server_default="customer",
        ),
    )
    op.add_column(
        "customers",
        sa.Column("whatsapp", sa.VARCHAR(length=50), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("billing_address", sa.VARCHAR(length=500), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("shipping_address", sa.VARCHAR(length=500), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("gstin", sa.VARCHAR(length=50), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "customers",
        sa.Column(
            "opening_balance",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "customers",
        sa.Column("credit_limit", sa.Float(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("payment_terms", sa.VARCHAR(length=500), nullable=True),
    )


def downgrade():
    op.drop_column("customers", "payment_terms")
    op.drop_column("customers", "credit_limit")
    op.drop_column("customers", "opening_balance")
    op.drop_column("customers", "tags")
    op.drop_column("customers", "gstin")
    op.drop_column("customers", "shipping_address")
    op.drop_column("customers", "billing_address")
    op.drop_column("customers", "whatsapp")
    op.drop_column("customers", "party_type")
