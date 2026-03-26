"""merge_heads

Revision ID: 7f1b14447872
Revises: 5a6b7c8d9e0f, migrate_supabase_to_local
Create Date: 2026-03-26 23:34:38.222058

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '7f1b14447872'
down_revision = ('5a6b7c8d9e0f', 'migrate_supabase_to_local')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
