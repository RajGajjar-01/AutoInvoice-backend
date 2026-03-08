"""Add data tables models

Revision ID: abc123def456
Revises: fe56fa70289e
Create Date: 2024-03-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    # Create data_tables table
    op.create_table(
        'data_tables',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.VARCHAR(length=255), nullable=False),
        sa.Column('owner_id', sa.UUID(), nullable=False),
        sa.Column('columns', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for data_tables
    op.create_index('idx_data_tables_owner_id', 'data_tables', ['owner_id'])
    op.create_index('idx_data_tables_created_at', 'data_tables', ['created_at'])
    op.create_index('idx_data_tables_name', 'data_tables', ['name'])
    op.create_index('idx_data_tables_columns_gin', 'data_tables', ['columns'], 
                    postgresql_using='gin')
    op.create_index('idx_data_tables_owner_created', 'data_tables', 
                    ['owner_id', sa.text('created_at DESC')])
    
    # Create table_rows table
    op.create_table(
        'table_rows',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('table_id', sa.UUID(), nullable=False),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['table_id'], ['data_tables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for table_rows
    op.create_index('idx_table_rows_table_id', 'table_rows', ['table_id'])
    op.create_index('idx_table_rows_created_at', 'table_rows', ['created_at'])
    op.create_index('idx_table_rows_data_gin', 'table_rows', ['data'], 
                    postgresql_using='gin')
    op.create_index('idx_table_rows_table_created', 'table_rows', 
                    ['table_id', sa.text('created_at DESC')])
    
    # Create table_reminders table
    op.create_table(
        'table_reminders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('table_id', sa.UUID(), nullable=False),
        sa.Column('reminder_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['table_id'], ['data_tables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for table_reminders
    op.create_index('idx_table_reminders_table_id', 'table_reminders', ['table_id'])
    op.create_index('idx_table_reminders_data_gin', 'table_reminders', ['reminder_data'], 
                    postgresql_using='gin')


def downgrade():
    op.drop_table('table_reminders')
    op.drop_table('table_rows')
    op.drop_table('data_tables')
