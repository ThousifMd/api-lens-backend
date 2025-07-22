-- ============================================================================
-- Migration: Create separate backend and frontend schemas
-- ============================================================================
-- This migration creates dedicated schemas without breaking the existing public schema

-- Step 1: Create the backend schema
CREATE SCHEMA IF NOT EXISTS backend;

-- Step 2: Create the frontend schema
CREATE SCHEMA IF NOT EXISTS frontend;

-- Step 3: Copy all table structures from public to backend (WITHOUT data first)
DO $$
DECLARE
    r RECORD;
    create_stmt TEXT;
BEGIN
    -- Copy all tables structure
    FOR r IN 
        SELECT 
            'CREATE TABLE backend.' || quote_ident(tablename) || ' (LIKE public.' || quote_ident(tablename) || ' INCLUDING ALL)' as stmt
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT LIKE 'pg_%'
        AND tablename NOT LIKE 'schema_migrations'
    LOOP
        EXECUTE r.stmt;
    END LOOP;
END $$;

-- Step 4: Copy all data from public to backend
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT LIKE 'pg_%'
        AND tablename NOT LIKE 'schema_migrations'
    LOOP
        EXECUTE format('INSERT INTO backend.%I SELECT * FROM public.%I', r.tablename, r.tablename);
    END LOOP;
END $$;

-- Step 5: Copy all views
DO $$
DECLARE
    r RECORD;
    view_def TEXT;
BEGIN
    FOR r IN 
        SELECT viewname, definition
        FROM pg_views
        WHERE schemaname = 'public'
    LOOP
        view_def := replace(r.definition, 'public.', 'backend.');
        EXECUTE format('CREATE VIEW backend.%I AS %s', r.viewname, view_def);
    END LOOP;
END $$;

-- Step 6: Copy all functions
DO $$
DECLARE
    r RECORD;
    func_def TEXT;
BEGIN
    FOR r IN 
        SELECT 
            proname,
            pg_get_function_identity_arguments(oid) as args,
            pg_get_functiondef(oid) as def
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'public'
        AND p.prokind = 'f'
    LOOP
        func_def := replace(r.def, 'public.', 'backend.');
        func_def := replace(func_def, 'FUNCTION public.', 'FUNCTION backend.');
        EXECUTE func_def;
    END LOOP;
END $$;

-- Step 7: Grant necessary permissions
GRANT USAGE ON SCHEMA backend TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA backend TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA backend TO postgres;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA backend TO postgres;

GRANT USAGE ON SCHEMA frontend TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA frontend TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA frontend TO postgres;

-- Step 8: Add comments for documentation
COMMENT ON SCHEMA backend IS 'API Lens backend schema - contains all backend tables, views, and functions';
COMMENT ON SCHEMA frontend IS 'API Lens frontend schema - for frontend-specific data and caching';

-- Note: After running this migration:
-- 1. Update your .env file to include: DATABASE_URL="...?search_path=backend"
-- 2. Or update your database connection code to set search_path
-- 3. The public schema remains untouched as a safety net