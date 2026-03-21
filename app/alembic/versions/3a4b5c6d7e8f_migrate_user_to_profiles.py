"""Migrate user table to profiles with Supabase auth integration

Revision ID: 3a4b5c6d7e8f
Revises: 2f7f3b1a9c2a
Create Date: 2024-03-21 12:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "3a4b5c6d7e8f"
down_revision = "2c0c02ae8eff"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.execute("""
        CREATE TABLE profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) NOT NULL,
            full_name VARCHAR(255),
            avatar_url VARCHAR(500),
            is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX ix_profiles_email ON profiles(email)")
    op.execute("CREATE INDEX ix_profiles_id ON profiles(id)")

    op.execute("""
        INSERT INTO profiles (id, email, full_name, is_superuser, is_verified, created_at)
        SELECT 
            gen_random_uuid(),
            email,
            full_name,
            is_superuser,
            FALSE,
            COALESCE(created_at, NOW())
        FROM "user"
    """)

    op.execute("""
        CREATE TABLE items_new (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            title VARCHAR(255) NOT NULL,
            description VARCHAR(255),
            owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO items_new (id, title, description, owner_id, created_at)
        SELECT 
            gen_random_uuid(),
            title,
            description,
            p.id,
            COALESCE(i.created_at, NOW())
        FROM item i
        JOIN "user" u ON i.owner_id = u.id
        JOIN profiles p ON p.email = u.email
    """)

    op.execute("DROP TABLE item")
    op.execute("ALTER TABLE items_new RENAME TO item")
    op.execute("CREATE INDEX ix_item_owner_id ON item(owner_id)")

    op.execute('DROP TABLE "user"')

    op.execute("""
        ALTER TABLE data_tables 
        DROP CONSTRAINT IF EXISTS data_tables_owner_id_fkey,
        ADD CONSTRAINT data_tables_owner_id_fkey 
        FOREIGN KEY (owner_id) REFERENCES profiles(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE customers 
        DROP CONSTRAINT IF EXISTS customers_owner_id_fkey,
        ADD CONSTRAINT customers_owner_id_fkey 
        FOREIGN KEY (owner_id) REFERENCES profiles(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE invoices 
        DROP CONSTRAINT IF EXISTS invoices_owner_id_fkey,
        ADD CONSTRAINT invoices_owner_id_fkey 
        FOREIGN KEY (owner_id) REFERENCES profiles(id) ON DELETE CASCADE
    """)

    op.execute("""
        ALTER TABLE invoice_templates 
        DROP CONSTRAINT IF EXISTS invoice_templates_owner_id_fkey,
        ADD CONSTRAINT invoice_templates_owner_id_fkey 
        FOREIGN KEY (owner_id) REFERENCES profiles(id) ON DELETE CASCADE
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        CREATE TRIGGER update_profiles_updated_at 
            BEFORE UPDATE ON profiles 
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at_column();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION handle_new_user()
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO public.profiles (id, email, full_name, is_verified)
            VALUES (
                NEW.id,
                NEW.email,
                NEW.raw_user_meta_data->>'full_name',
                NEW.email_confirmed_at IS NOT NULL
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW EXECUTE FUNCTION handle_new_user();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION handle_user_update()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE public.profiles
            SET 
                email = NEW.email,
                full_name = COALESCE(NEW.raw_user_meta_data->>'full_name', full_name),
                is_verified = NEW.email_confirmed_at IS NOT NULL,
                updated_at = NOW()
            WHERE id = NEW.id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        
        CREATE TRIGGER on_auth_user_updated
            AFTER UPDATE ON auth.users
            FOR EACH ROW EXECUTE FUNCTION handle_user_update();
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION handle_user_delete()
        RETURNS TRIGGER AS $$
        BEGIN
            DELETE FROM public.profiles WHERE id = OLD.id;
            RETURN OLD;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        
        CREATE TRIGGER on_auth_user_deleted
            AFTER DELETE ON auth.users
            FOR EACH ROW EXECUTE FUNCTION handle_user_delete();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_deleted ON auth.users")
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users")
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users")
    op.execute("DROP FUNCTION IF EXISTS handle_user_delete()")
    op.execute("DROP FUNCTION IF EXISTS handle_user_update()")
    op.execute("DROP FUNCTION IF EXISTS handle_new_user()")

    op.execute("DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    op.execute("""
        CREATE TABLE "user" (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            full_name VARCHAR(255),
            hashed_password VARCHAR(255) NOT NULL DEFAULT '',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO "user" (email, full_name, is_superuser, created_at)
        SELECT email, full_name, is_superuser, created_at
        FROM profiles
    """)

    op.execute("DROP TABLE profiles")

    op.execute("""
        CREATE TABLE item_new (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description VARCHAR(255),
            owner_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO item_new (title, description, owner_id, created_at)
        SELECT i.title, i.description, u.id, i.created_at
        FROM item i
        JOIN profiles p ON i.owner_id = p.id
        JOIN "user" u ON u.email = p.email
    """)

    op.execute("DROP TABLE item")
    op.execute("ALTER TABLE item_new RENAME TO item")
