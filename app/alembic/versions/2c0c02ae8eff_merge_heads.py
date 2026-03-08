"""merge heads

Revision ID: 2c0c02ae8eff
Revises: 2f7f3b1a9c2a, 5f2c1b8d9eaa
Create Date: 2026-03-08 18:56:09.979250

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '2c0c02ae8eff'
down_revision = ('2f7f3b1a9c2a', '5f2c1b8d9eaa')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
