"""Add new Item fields, CompanySettings, Notifications, DocumentType

Revision ID: a1b2c3d4e5f6
Revises: 4b5c6d7e8f9a
Create Date: 2026-03-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "2c0c02ae8eff"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to item table
    op.add_column("item", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("item", sa.Column("category", sa.String(100), nullable=True))
    op.add_column("item", sa.Column("sku", sa.String(50), nullable=True))
    op.add_column("item", sa.Column("unit", sa.String(20), nullable=True))
    op.add_column(
        "item", sa.Column("price", sa.Float, nullable=False, server_default="0")
    )
    op.add_column(
        "item", sa.Column("tax_rate", sa.Float, nullable=False, server_default="0")
    )
    op.add_column(
        "item", sa.Column("stock", sa.Float, nullable=False, server_default="0")
    )
    op.add_column(
        "item",
        sa.Column("low_stock_threshold", sa.Float, nullable=False, server_default="5"),
    )
    op.add_column(
        "item",
        sa.Column(
            "stock_history",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "item", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )

    # Copy title to name, then drop title
    op.execute("UPDATE item SET name = title WHERE name IS NULL")
    op.drop_column("item", "title")

    # Add document_type to invoices
    op.add_column(
        "invoices",
        sa.Column(
            "document_type", sa.String(20), nullable=False, server_default="invoice"
        ),
    )
    op.add_column("invoices", sa.Column("valid_until", sa.Date, nullable=True))
    op.add_column(
        "invoices", sa.Column("discount", sa.Float, nullable=False, server_default="0")
    )
    op.add_column(
        "invoices", sa.Column("place_of_supply", sa.String(100), nullable=True)
    )
    op.add_column(
        "invoices",
        sa.Column("reverse_charge", sa.Boolean, nullable=False, server_default="false"),
    )

    # Create company_settings table
    op.create_table(
        "company_settings",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("gstin", sa.String(50), nullable=True),
        sa.Column("pan", sa.String(20), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("pincode", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("signature_url", sa.String(500), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("bank_account", sa.String(50), nullable=True),
        sa.Column("bank_ifsc", sa.String(20), nullable=True),
        sa.Column("bank_branch", sa.String(100), nullable=True),
        sa.Column("upi_id", sa.String(50), nullable=True),
        sa.Column("terms_and_conditions", sa.String(2000), nullable=True),
        sa.Column(
            "invoice_prefix", sa.String(20), nullable=False, server_default="INV-"
        ),
        sa.Column(
            "quotation_prefix", sa.String(20), nullable=False, server_default="QUO-"
        ),
        sa.Column(
            "proforma_prefix", sa.String(20), nullable=False, server_default="PRO-"
        ),
        sa.Column(
            "challan_prefix", sa.String(20), nullable=False, server_default="CHL-"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_company_settings_owner_id", "company_settings", ["owner_id"], unique=True
    )

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("table_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("table_name", sa.String(255), nullable=True),
        sa.Column("row_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("row_label", sa.String(255), nullable=True),
        sa.Column("read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_notifications_owner_id", "notifications", ["owner_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade():
    # Drop notifications table
    op.drop_index("ix_notifications_created_at", "notifications")
    op.drop_index("ix_notifications_owner_id", "notifications")
    op.drop_table("notifications")

    # Drop company_settings table
    op.drop_index("ix_company_settings_owner_id", "company_settings")
    op.drop_table("company_settings")

    # Remove invoice columns
    op.drop_column("invoices", "reverse_charge")
    op.drop_column("invoices", "place_of_supply")
    op.drop_column("invoices", "discount")
    op.drop_column("invoices", "valid_until")
    op.drop_column("invoices", "document_type")

    # Remove item columns and restore title
    op.add_column("item", sa.Column("title", sa.String(255), nullable=True))
    op.execute("UPDATE item SET title = name")
    op.drop_column("item", "updated_at")
    op.drop_column("item", "stock_history")
    op.drop_column("item", "low_stock_threshold")
    op.drop_column("item", "stock")
    op.drop_column("item", "tax_rate")
    op.drop_column("item", "price")
    op.drop_column("item", "unit")
    op.drop_column("item", "sku")
    op.drop_column("item", "category")
    op.drop_column("item", "name")
