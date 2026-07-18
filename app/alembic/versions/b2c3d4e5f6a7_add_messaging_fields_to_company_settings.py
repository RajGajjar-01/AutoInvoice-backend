"""add whatsapp/openwa/smtp fields to company_settings

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "company_settings",
        sa.Column(
            "whatsapp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "company_settings",
        sa.Column(
            "openwa_base_url",
            sa.String(500),
            nullable=False,
            server_default="http://localhost:2785",
        ),
    )
    op.add_column(
        "company_settings",
        sa.Column("openwa_api_key", sa.String(500), nullable=True),
    )
    op.add_column(
        "company_settings",
        sa.Column("openwa_session_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "company_settings",
        sa.Column("smtp_host", sa.String(255), nullable=True),
    )
    op.add_column(
        "company_settings",
        sa.Column(
            "smtp_port", sa.Integer(), nullable=False, server_default="587"
        ),
    )
    op.add_column(
        "company_settings",
        sa.Column("smtp_user", sa.String(255), nullable=True),
    )
    op.add_column(
        "company_settings",
        sa.Column("smtp_password", sa.String(500), nullable=True),
    )
    op.add_column(
        "company_settings",
        sa.Column(
            "smtp_tls", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "company_settings",
        sa.Column("emails_from_email", sa.String(255), nullable=True),
    )
    op.add_column(
        "company_settings",
        sa.Column("emails_from_name", sa.String(255), nullable=True),
    )


def downgrade():
    op.drop_column("company_settings", "emails_from_name")
    op.drop_column("company_settings", "emails_from_email")
    op.drop_column("company_settings", "smtp_tls")
    op.drop_column("company_settings", "smtp_password")
    op.drop_column("company_settings", "smtp_user")
    op.drop_column("company_settings", "smtp_port")
    op.drop_column("company_settings", "smtp_host")
    op.drop_column("company_settings", "openwa_session_id")
    op.drop_column("company_settings", "openwa_api_key")
    op.drop_column("company_settings", "openwa_base_url")
    op.drop_column("company_settings", "whatsapp_enabled")
