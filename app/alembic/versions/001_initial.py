"""Initial migration - all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-03-27

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "item",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("sku", sa.String(50), nullable=True),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("price", sa.Float, nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Float, nullable=False, server_default="0"),
        sa.Column("stock", sa.Float, nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Float, nullable=False, server_default="5"),
        sa.Column(
            "stock_history", postgresql.JSONB, nullable=False, server_default="[]"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_item_owner_id", "item", ["owner_id"])

    op.create_table(
        "data_tables",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("columns", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_data_tables_owner_id", "data_tables", ["owner_id"])

    op.create_table(
        "table_rows",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("table_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["table_id"], ["data_tables.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_table_rows_table_id", "table_rows", ["table_id"])

    op.create_table(
        "table_reminders",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("table_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("row_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("reminder_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["table_id"], ["data_tables.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["row_id"], ["table_rows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_table_reminders_table_id", "table_reminders", ["table_id"])
    op.create_index("ix_table_reminders_owner_id", "table_reminders", ["owner_id"])

    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("gstin", sa.String(50), nullable=True),
        sa.Column("pan", sa.String(20), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("pincode", sa.String(20), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("billing_address", sa.String(500), nullable=True),
        sa.Column("shipping_address", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_customers_owner_id", "customers", ["owner_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("customer_id", sa.UUID(as_uuid=False), nullable=True),
        sa.Column("invoice_number", sa.String(50), nullable=False),
        sa.Column(
            "document_type", sa.String(20), nullable=False, server_default="invoice"
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("items", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("subtotal", sa.Float, nullable=False, server_default="0"),
        sa.Column("tax", sa.Float, nullable=False, server_default="0"),
        sa.Column("discount", sa.Float, nullable=False, server_default="0"),
        sa.Column("total", sa.Float, nullable=False, server_default="0"),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("terms", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("place_of_supply", sa.String(100), nullable=True),
        sa.Column("reverse_charge", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invoices_owner_id", "invoices", ["owner_id"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])

    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invoicetemplatekind') THEN CREATE TYPE invoicetemplatekind AS ENUM ('built_in', 'custom', 'imported_html', 'imported_pdf', 'imported_excel'); END IF; END $$;"
    )

    op.create_table(
        "invoice_templates",
        sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
        sa.Column("owner_id", sa.UUID(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "built_in",
                "custom",
                "imported_html",
                "imported_pdf",
                "imported_excel",
                name="invoicetemplatekind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("built_in_id", sa.String(100), nullable=True),
        sa.Column("custom_data", postgresql.JSONB, nullable=True),
        sa.Column("imported_html", sa.Text, nullable=True),
        sa.Column("imported_pdf_data_url", sa.Text, nullable=True),
        sa.Column("imported_excel_columns", postgresql.JSONB, nullable=True),
        sa.Column("imported_excel_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_invoice_templates_owner_id", "invoice_templates", ["owner_id"])

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
    op.drop_index("ix_notifications_created_at", "notifications")
    op.drop_index("ix_notifications_owner_id", "notifications")
    op.drop_table("notifications")

    op.drop_index("ix_company_settings_owner_id", "company_settings")
    op.drop_table("company_settings")

    op.drop_index("ix_invoice_templates_owner_id", "invoice_templates")
    op.drop_table("invoice_templates")
    sa.Enum(name="invoicetemplatekind").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_invoices_customer_id", "invoices")
    op.drop_index("ix_invoices_owner_id", "invoices")
    op.drop_table("invoices")

    op.drop_index("ix_customers_owner_id", "customers")
    op.drop_table("customers")

    op.drop_index("ix_table_reminders_owner_id", "table_reminders")
    op.drop_index("ix_table_reminders_table_id", "table_reminders")
    op.drop_table("table_reminders")

    op.drop_index("ix_table_rows_table_id", "table_rows")
    op.drop_table("table_rows")

    op.drop_index("ix_data_tables_owner_id", "data_tables")
    op.drop_table("data_tables")

    op.drop_index("ix_item_owner_id", "item")
    op.drop_table("item")

    op.drop_index("ix_user_email", "user")
    op.drop_table("user")
