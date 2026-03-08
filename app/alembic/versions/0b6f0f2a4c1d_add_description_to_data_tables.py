"""Add description to data tables

Revision ID: 0b6f0f2a4c1d
Revises: 97f0383745b1
Create Date: 2026-03-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0b6f0f2a4c1d"
down_revision = "97f0383745b1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "data_tables",
        sa.Column("description", sa.VARCHAR(length=500), nullable=True),
    )


def downgrade():
    op.drop_column("data_tables", "description")
