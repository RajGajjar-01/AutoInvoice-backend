"""Migrate from Supabase Auth to local auth

Revision ID: migrate_supabase_to_local
Revises:
Create Date: 2026-03-26

This migration:
- Renames profiles table to user
- Adds hashed_password and is_active columns
- Updates foreign key references
- Drops Supabase RLS policies
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "migrate_supabase_to_local"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop RLS policies if they exist (Supabase specific)
    op.execute("DROP POLICY IF EXISTS profiles_select_policy ON profiles")
    op.execute("DROP POLICY IF EXISTS profiles_insert_policy ON profiles")
    op.execute("DROP POLICY IF EXISTS profiles_update_policy ON profiles")
    op.execute("DROP POLICY IF EXISTS profiles_delete_policy ON profiles")
    op.execute("DROP POLICY IF EXISTS item_select_policy ON item")
    op.execute("DROP POLICY IF EXISTS item_insert_policy ON item")
    op.execute("DROP POLICY IF EXISTS item_update_policy ON item")
    op.execute("DROP POLICY IF EXISTS item_delete_policy ON item")
    op.execute("DROP POLICY IF EXISTS data_tables_select_policy ON data_tables")
    op.execute("DROP POLICY IF EXISTS data_tables_insert_policy ON data_tables")
    op.execute("DROP POLICY IF EXISTS data_tables_update_policy ON data_tables")
    op.execute("DROP POLICY IF EXISTS data_tables_delete_policy ON data_tables")
    op.execute("DROP POLICY IF EXISTS customers_select_policy ON customers")
    op.execute("DROP POLICY IF EXISTS customers_insert_policy ON customers")
    op.execute("DROP POLICY IF EXISTS customers_update_policy ON customers")
    op.execute("DROP POLICY IF EXISTS customers_delete_policy ON customers")
    op.execute("DROP POLICY IF EXISTS invoices_select_policy ON invoices")
    op.execute("DROP POLICY IF EXISTS invoices_insert_policy ON invoices")
    op.execute("DROP POLICY IF EXISTS invoices_update_policy ON invoices")
    op.execute("DROP POLICY IF EXISTS invoices_delete_policy ON invoices")
    op.execute(
        "DROP POLICY IF EXISTS invoice_templates_select_policy ON invoice_templates"
    )
    op.execute(
        "DROP POLICY IF EXISTS invoice_templates_insert_policy ON invoice_templates"
    )
    op.execute(
        "DROP POLICY IF EXISTS invoice_templates_update_policy ON invoice_templates"
    )
    op.execute(
        "DROP POLICY IF EXISTS invoice_templates_delete_policy ON invoice_templates"
    )
    op.execute(
        "DROP POLICY IF EXISTS company_settings_select_policy ON company_settings"
    )
    op.execute(
        "DROP POLICY IF EXISTS company_settings_insert_policy ON company_settings"
    )
    op.execute(
        "DROP POLICY IF EXISTS company_settings_update_policy ON company_settings"
    )
    op.execute(
        "DROP POLICY IF EXISTS company_settings_delete_policy ON company_settings"
    )
    op.execute("DROP POLICY IF EXISTS notifications_select_policy ON notifications")
    op.execute("DROP POLICY IF EXISTS notifications_insert_policy ON notifications")
    op.execute("DROP POLICY IF EXISTS notifications_update_policy ON notifications")
    op.execute("DROP POLICY IF EXISTS notifications_delete_policy ON notifications")
    op.execute("DROP POLICY IF EXISTS table_rows_select_policy ON table_rows")
    op.execute("DROP POLICY IF EXISTS table_rows_insert_policy ON table_rows")
    op.execute("DROP POLICY IF EXISTS table_rows_update_policy ON table_rows")
    op.execute("DROP POLICY IF EXISTS table_rows_delete_policy ON table_rows")
    op.execute("DROP POLICY IF EXISTS table_reminders_select_policy ON table_reminders")
    op.execute("DROP POLICY IF EXISTS table_reminders_insert_policy ON table_reminders")
    op.execute("DROP POLICY IF EXISTS table_reminders_delete_policy ON table_reminders")

    # Disable RLS on all tables
    op.execute("ALTER TABLE profiles DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE item DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE data_tables DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE customers DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_templates DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE company_settings DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE table_rows DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE table_reminders DISABLE ROW LEVEL SECURITY")

    # Add new columns to profiles table before renaming
    op.add_column("profiles", sa.Column("hashed_password", sa.String(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default="true"),
    )

    # Set placeholder password for existing users (they will need to reset)
    op.execute(
        "UPDATE profiles SET hashed_password = '$argon2id$v=19$m=65536,t=3,p=4$placeholder', is_active = true WHERE hashed_password IS NULL"
    )

    # Make hashed_password non-nullable
    op.alter_column("profiles", "hashed_password", nullable=False)

    # Drop old unique constraint on email if exists and add new one
    op.create_unique_constraint("profiles_email_key", "profiles", ["email"])

    # Rename profiles table to user
    op.rename_table("profiles", "user")

    # Update foreign key references in all related tables
    # Note: In PostgreSQL, we need to drop and recreate foreign keys

    # Item table
    op.drop_constraint("item_owner_id_fkey", "item", type_="foreignkey")
    op.create_foreign_key(
        "item_owner_id_fkey", "item", "user", ["owner_id"], ["id"], ondelete="CASCADE"
    )

    # data_tables
    op.drop_constraint("data_tables_owner_id_fkey", "data_tables", type_="foreignkey")
    op.create_foreign_key(
        "data_tables_owner_id_fkey",
        "data_tables",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # customers
    op.drop_constraint("customers_owner_id_fkey", "customers", type_="foreignkey")
    op.create_foreign_key(
        "customers_owner_id_fkey",
        "customers",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # invoices
    op.drop_constraint("invoices_owner_id_fkey", "invoices", type_="foreignkey")
    op.create_foreign_key(
        "invoices_owner_id_fkey",
        "invoices",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # invoice_templates
    op.drop_constraint(
        "invoice_templates_owner_id_fkey", "invoice_templates", type_="foreignkey"
    )
    op.create_foreign_key(
        "invoice_templates_owner_id_fkey",
        "invoice_templates",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # company_settings
    op.drop_constraint(
        "company_settings_owner_id_fkey", "company_settings", type_="foreignkey"
    )
    op.create_foreign_key(
        "company_settings_owner_id_fkey",
        "company_settings",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # notifications
    op.drop_constraint(
        "notifications_owner_id_fkey", "notifications", type_="foreignkey"
    )
    op.create_foreign_key(
        "notifications_owner_id_fkey",
        "notifications",
        "user",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revert foreign key references
    op.drop_constraint(
        "notifications_owner_id_fkey", "notifications", type_="foreignkey"
    )
    op.create_foreign_key(
        "notifications_owner_id_fkey",
        "notifications",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "company_settings_owner_id_fkey", "company_settings", type_="foreignkey"
    )
    op.create_foreign_key(
        "company_settings_owner_id_fkey",
        "company_settings",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "invoice_templates_owner_id_fkey", "invoice_templates", type_="foreignkey"
    )
    op.create_foreign_key(
        "invoice_templates_owner_id_fkey",
        "invoice_templates",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("invoices_owner_id_fkey", "invoices", type_="foreignkey")
    op.create_foreign_key(
        "invoices_owner_id_fkey",
        "invoices",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("customers_owner_id_fkey", "customers", type_="foreignkey")
    op.create_foreign_key(
        "customers_owner_id_fkey",
        "customers",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("data_tables_owner_id_fkey", "data_tables", type_="foreignkey")
    op.create_foreign_key(
        "data_tables_owner_id_fkey",
        "data_tables",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint("item_owner_id_fkey", "item", type_="foreignkey")
    op.create_foreign_key(
        "item_owner_id_fkey",
        "item",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Rename user back to profiles
    op.rename_table("user", "profiles")

    # Drop new columns
    op.drop_column("profiles", "is_active")
    op.drop_column("profiles", "hashed_password")

    # Drop unique constraint
    op.drop_constraint("profiles_email_key", "profiles", type_="unique")
