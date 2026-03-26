"""add_imported_excel_columns_to_invoice_templates

Revision ID: 5a6b7c8d9e0f
Revises: 2f7f3b1a9c2a
Create Date: 2026-03-26 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "5a6b7c8d9e0f"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # Add new enum value for imported_excel
    invoicetemplatekind = postgresql.ENUM(
        "built_in",
        "custom",
        "imported_html",
        "imported_pdf",
        "imported_excel",
        name="invoicetemplatekind",
        create_type=False,
    )
    invoicetemplatekind.create(op.get_bind(), checkfirst=True)

    # Add new columns for Excel import
    op.add_column(
        "invoice_templates",
        sa.Column(
            "imported_excel_columns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "invoice_templates",
        sa.Column(
            "imported_excel_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("invoice_templates", "imported_excel_data")
    op.drop_column("invoice_templates", "imported_excel_columns")
    sa.Enum(name="invoicetemplatekind").drop(op.get_bind(), checkfirst=True)
