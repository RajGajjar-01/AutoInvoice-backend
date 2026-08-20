"""expand column sizes and encrypt sensitive company fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # Alter column lengths to accommodate ciphertext strings (base64 ~120-200 chars)
    op.alter_column(
        "company_settings",
        "bank_account",
        existing_type=sa.String(50),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "company_settings",
        "bank_ifsc",
        existing_type=sa.String(20),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "company_settings",
        "pan",
        existing_type=sa.String(20),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "company_settings",
        "upi_id",
        existing_type=sa.String(50),
        type_=sa.String(500),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "company_settings",
        "upi_id",
        existing_type=sa.String(500),
        type_=sa.String(50),
        existing_nullable=True,
    )
    op.alter_column(
        "company_settings",
        "pan",
        existing_type=sa.String(500),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.alter_column(
        "company_settings",
        "bank_ifsc",
        existing_type=sa.String(500),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.alter_column(
        "company_settings",
        "bank_account",
        existing_type=sa.String(500),
        type_=sa.String(50),
        existing_nullable=True,
    )
