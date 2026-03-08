"""add_invoice_templates_table

Revision ID: 2f7f3b1a9c2a
Revises: 0b6f0f2a4c1d
Create Date: 2026-03-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = "2f7f3b1a9c2a"
down_revision = "0b6f0f2a4c1d"
branch_labels = None
depends_on = None


def upgrade():
    # Enum for template kind
    invoicetemplatekind = postgresql.ENUM(
        "built_in",
        "custom",
        "imported_html",
        "imported_pdf",
        name="invoicetemplatekind",
        create_type=False,
    )
    invoicetemplatekind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "invoice_templates",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("kind", invoicetemplatekind, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("built_in_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column("custom_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("imported_html", sa.Text(), nullable=True),
        sa.Column("imported_pdf_data_url", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_invoice_templates_owner_id"),
        "invoice_templates",
        ["owner_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_invoice_templates_owner_id"), table_name="invoice_templates")
    op.drop_table("invoice_templates")
    sa.Enum(name="invoicetemplatekind").drop(op.get_bind(), checkfirst=True)
