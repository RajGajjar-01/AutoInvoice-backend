"""Enable Row Level Security for all tables

Revision ID: 4b5c6d7e8f9a
Revises: 3a4b5c6d7e8f
Create Date: 2024-03-21 15:00:00.000000

This migration enables RLS on all tables and creates policies that:
- Allow users to access only their own data
- Use auth.uid() from Supabase Auth for user identification
- Follow Supabase best practices for performance
"""

from alembic import op


revision = "4b5c6d7e8f9a"
down_revision = "3a4b5c6d7e8f"
branch_labels = None
depends_on = None


def upgrade():
    # ============================================================================
    # Enable RLS on all tables
    # ============================================================================

    op.execute("ALTER TABLE profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE item ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE data_tables ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE table_rows ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE table_reminders ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE customers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoice_templates ENABLE ROW LEVEL SECURITY")

    # ============================================================================
    # Create indexes for RLS performance
    # ============================================================================

    # Profiles - index on id (primary key already indexed)
    # Item - index on owner_id
    op.execute("CREATE INDEX IF NOT EXISTS idx_item_owner_id ON item(owner_id)")

    # Data tables - index on owner_id
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_data_tables_owner_id ON data_tables(owner_id)"
    )

    # Table rows - index on table_id for joins
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_table_rows_table_id ON table_rows(table_id)"
    )

    # Table reminders - index on table_id
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_table_reminders_table_id ON table_reminders(table_id)"
    )

    # Customers - index on owner_id
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_owner_id ON customers(owner_id)"
    )

    # Invoices - index on owner_id and customer_id
    op.execute("CREATE INDEX IF NOT EXISTS idx_invoices_owner_id ON invoices(owner_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_invoices_customer_id ON invoices(customer_id)"
    )

    # Invoice templates - index on owner_id
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_invoice_templates_owner_id ON invoice_templates(owner_id)"
    )

    # ============================================================================
    # PROFILES - Policies
    # ============================================================================

    # Users can view their own profile
    op.execute("""
        CREATE POLICY "Users can view own profile"
        ON profiles FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = id)
    """)

    # Users can update their own profile
    op.execute("""
        CREATE POLICY "Users can update own profile"
        ON profiles FOR UPDATE
        TO authenticated
        USING ((SELECT auth.uid()) = id)
        WITH CHECK ((SELECT auth.uid()) = id)
    """)

    # Users can insert their own profile (usually handled by trigger)
    op.execute("""
        CREATE POLICY "Users can insert own profile"
        ON profiles FOR INSERT
        TO authenticated
        WITH CHECK ((SELECT auth.uid()) = id)
    """)

    # Users can delete their own profile
    op.execute("""
        CREATE POLICY "Users can delete own profile"
        ON profiles FOR DELETE
        TO authenticated
        USING ((SELECT auth.uid()) = id)
    """)

    # ============================================================================
    # ITEMS - Policies
    # ============================================================================

    # Users can view their own items
    op.execute("""
        CREATE POLICY "Users can view own items"
        ON item FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # Users can create items for themselves
    op.execute("""
        CREATE POLICY "Users can create own items"
        ON item FOR INSERT
        TO authenticated
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can update their own items
    op.execute("""
        CREATE POLICY "Users can update own items"
        ON item FOR UPDATE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can delete their own items
    op.execute("""
        CREATE POLICY "Users can delete own items"
        ON item FOR DELETE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # ============================================================================
    # DATA_TABLES - Policies
    # ============================================================================

    # Users can view their own data tables
    op.execute("""
        CREATE POLICY "Users can view own data tables"
        ON data_tables FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # Users can create data tables for themselves
    op.execute("""
        CREATE POLICY "Users can create own data tables"
        ON data_tables FOR INSERT
        TO authenticated
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can update their own data tables
    op.execute("""
        CREATE POLICY "Users can update own data tables"
        ON data_tables FOR UPDATE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can delete their own data tables
    op.execute("""
        CREATE POLICY "Users can delete own data tables"
        ON data_tables FOR DELETE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # ============================================================================
    # TABLE_ROWS - Policies (inherit from data_tables)
    # ============================================================================

    # Users can view rows of their own tables
    op.execute("""
        CREATE POLICY "Users can view rows of own tables"
        ON table_rows FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_rows.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # Users can insert rows into their own tables
    op.execute("""
        CREATE POLICY "Users can insert rows into own tables"
        ON table_rows FOR INSERT
        TO authenticated
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_rows.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # Users can update rows in their own tables
    op.execute("""
        CREATE POLICY "Users can update rows in own tables"
        ON table_rows FOR UPDATE
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_rows.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_rows.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # Users can delete rows from their own tables
    op.execute("""
        CREATE POLICY "Users can delete rows from own tables"
        ON table_rows FOR DELETE
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_rows.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # ============================================================================
    # TABLE_REMINDERS - Policies (inherit from data_tables)
    # ============================================================================

    # Users can view reminders of their own tables
    op.execute("""
        CREATE POLICY "Users can view reminders of own tables"
        ON table_reminders FOR SELECT
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_reminders.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # Users can create reminders for their own tables
    op.execute("""
        CREATE POLICY "Users can create reminders for own tables"
        ON table_reminders FOR INSERT
        TO authenticated
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_reminders.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # Users can delete reminders from their own tables
    op.execute("""
        CREATE POLICY "Users can delete reminders from own tables"
        ON table_reminders FOR DELETE
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM data_tables
                WHERE data_tables.id = table_reminders.table_id
                AND data_tables.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # ============================================================================
    # CUSTOMERS - Policies
    # ============================================================================

    # Users can view their own customers
    op.execute("""
        CREATE POLICY "Users can view own customers"
        ON customers FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # Users can create customers for themselves
    op.execute("""
        CREATE POLICY "Users can create own customers"
        ON customers FOR INSERT
        TO authenticated
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can update their own customers
    op.execute("""
        CREATE POLICY "Users can update own customers"
        ON customers FOR UPDATE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can delete their own customers
    op.execute("""
        CREATE POLICY "Users can delete own customers"
        ON customers FOR DELETE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # ============================================================================
    # INVOICES - Policies
    # ============================================================================

    # Users can view their own invoices
    op.execute("""
        CREATE POLICY "Users can view own invoices"
        ON invoices FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # Users can create invoices for themselves (customer must be owned by them)
    op.execute("""
        CREATE POLICY "Users can create own invoices"
        ON invoices FOR INSERT
        TO authenticated
        WITH CHECK (
            (SELECT auth.uid()) = owner_id
            AND EXISTS (
                SELECT 1 FROM customers
                WHERE customers.id = invoices.customer_id
                AND customers.owner_id = (SELECT auth.uid())
            )
        )
    """)

    # Users can update their own invoices
    op.execute("""
        CREATE POLICY "Users can update own invoices"
        ON invoices FOR UPDATE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
        WITH CHECK (
            (SELECT auth.uid()) = owner_id
            AND (
                customer_id = (SELECT customer_id FROM invoices WHERE id = invoices.id)
                OR EXISTS (
                    SELECT 1 FROM customers
                    WHERE customers.id = invoices.customer_id
                    AND customers.owner_id = (SELECT auth.uid())
                )
            )
        )
    """)

    # Users can delete their own invoices
    op.execute("""
        CREATE POLICY "Users can delete own invoices"
        ON invoices FOR DELETE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # ============================================================================
    # INVOICE_TEMPLATES - Policies
    # ============================================================================

    # Users can view their own invoice templates
    op.execute("""
        CREATE POLICY "Users can view own invoice templates"
        ON invoice_templates FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # Users can create invoice templates for themselves
    op.execute("""
        CREATE POLICY "Users can create own invoice templates"
        ON invoice_templates FOR INSERT
        TO authenticated
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can update their own invoice templates
    op.execute("""
        CREATE POLICY "Users can update own invoice templates"
        ON invoice_templates FOR UPDATE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
        WITH CHECK ((SELECT auth.uid()) = owner_id)
    """)

    # Users can delete their own invoice templates
    op.execute("""
        CREATE POLICY "Users can delete own invoice templates"
        ON invoice_templates FOR DELETE
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id)
    """)

    # ============================================================================
    # Helper function for checking superuser status
    # ============================================================================

    op.execute("""
        CREATE OR REPLACE FUNCTION is_superuser()
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog
        AS $$
        BEGIN
            RETURN EXISTS (
                SELECT 1 FROM profiles
                WHERE id = auth.uid()
                AND is_superuser = true
            );
        END;
        $$;
    """)

    # ============================================================================
    # Superuser bypass policies (optional - use with caution)
    # ============================================================================

    # Allow superusers to view all profiles
    op.execute("""
        CREATE POLICY "Superusers can view all profiles"
        ON profiles FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = id OR (SELECT is_superuser()))
    """)

    # Allow superusers to view all items
    op.execute("""
        CREATE POLICY "Superusers can view all items"
        ON item FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id OR (SELECT is_superuser()))
    """)

    # Allow superusers to view all data tables
    op.execute("""
        CREATE POLICY "Superusers can view all data tables"
        ON data_tables FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id OR (SELECT is_superuser()))
    """)

    # Allow superusers to view all customers
    op.execute("""
        CREATE POLICY "Superusers can view all customers"
        ON customers FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id OR (SELECT is_superuser()))
    """)

    # Allow superusers to view all invoices
    op.execute("""
        CREATE POLICY "Superusers can view all invoices"
        ON invoices FOR SELECT
        TO authenticated
        USING ((SELECT auth.uid()) = owner_id OR (SELECT is_superuser()))
    """)


def downgrade():
    # Drop helper function
    op.execute("DROP FUNCTION IF EXISTS is_superuser()")

    # Drop invoice_templates policies
    op.execute('DROP POLICY IF EXISTS "Superusers can view all invoices" ON invoices')
    op.execute('DROP POLICY IF EXISTS "Superusers can view all customers" ON customers')
    op.execute(
        'DROP POLICY IF EXISTS "Superusers can view all data tables" ON data_tables'
    )
    op.execute('DROP POLICY IF EXISTS "Superusers can view all items" ON item')
    op.execute('DROP POLICY IF EXISTS "Superusers can view all profiles" ON profiles')

    # Drop invoice_templates policies
    op.execute(
        'DROP POLICY IF EXISTS "Users can delete own invoice templates" ON invoice_templates'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can update own invoice templates" ON invoice_templates'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can create own invoice templates" ON invoice_templates'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can view own invoice templates" ON invoice_templates'
    )

    # Drop invoices policies
    op.execute('DROP POLICY IF EXISTS "Users can delete own invoices" ON invoices')
    op.execute('DROP POLICY IF EXISTS "Users can update own invoices" ON invoices')
    op.execute('DROP POLICY IF EXISTS "Users can create own invoices" ON invoices')
    op.execute('DROP POLICY IF EXISTS "Users can view own invoices" ON invoices')

    # Drop customers policies
    op.execute('DROP POLICY IF EXISTS "Users can delete own customers" ON customers')
    op.execute('DROP POLICY IF EXISTS "Users can update own customers" ON customers')
    op.execute('DROP POLICY IF EXISTS "Users can create own customers" ON customers')
    op.execute('DROP POLICY IF EXISTS "Users can view own customers" ON customers')

    # Drop table_reminders policies
    op.execute(
        'DROP POLICY IF EXISTS "Users can delete reminders from own tables" ON table_reminders'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can create reminders for own tables" ON table_reminders'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can view reminders of own tables" ON table_reminders'
    )

    # Drop table_rows policies
    op.execute(
        'DROP POLICY IF EXISTS "Users can delete rows from own tables" ON table_rows'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can update rows in own tables" ON table_rows'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can insert rows into own tables" ON table_rows'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can view rows of own tables" ON table_rows'
    )

    # Drop data_tables policies
    op.execute(
        'DROP POLICY IF EXISTS "Users can delete own data tables" ON data_tables'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can update own data tables" ON data_tables'
    )
    op.execute(
        'DROP POLICY IF EXISTS "Users can create own data tables" ON data_tables'
    )
    op.execute('DROP POLICY IF EXISTS "Users can view own data tables" ON data_tables')

    # Drop item policies
    op.execute('DROP POLICY IF EXISTS "Users can delete own items" ON item')
    op.execute('DROP POLICY IF EXISTS "Users can update own items" ON item')
    op.execute('DROP POLICY IF EXISTS "Users can create own items" ON item')
    op.execute('DROP POLICY IF EXISTS "Users can view own items" ON item')

    # Drop profiles policies
    op.execute('DROP POLICY IF EXISTS "Users can delete own profile" ON profiles')
    op.execute('DROP POLICY IF EXISTS "Users can insert own profile" ON profiles')
    op.execute('DROP POLICY IF EXISTS "Users can update own profile" ON profiles')
    op.execute('DROP POLICY IF EXISTS "Users can view own profile" ON profiles')

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_invoice_templates_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_invoices_customer_id")
    op.execute("DROP INDEX IF EXISTS idx_invoices_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_customers_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_table_reminders_table_id")
    op.execute("DROP INDEX IF EXISTS idx_table_rows_table_id")
    op.execute("DROP INDEX IF EXISTS idx_data_tables_owner_id")
    op.execute("DROP INDEX IF EXISTS idx_item_owner_id")

    # Disable RLS
    op.execute("ALTER TABLE invoice_templates DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE customers DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE table_reminders DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE table_rows DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE data_tables DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE item DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE profiles DISABLE ROW LEVEL SECURITY")
