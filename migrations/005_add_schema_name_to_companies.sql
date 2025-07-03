-- Migration 005: Add schema_name field to companies table
-- This field is required for multi-tenant schema support in the backend code

-- Add schema_name column to companies table
ALTER TABLE companies ADD COLUMN IF NOT EXISTS schema_name VARCHAR(255);

-- Set default schema_name values for existing companies
-- Use a pattern based on company name or ID for uniqueness
UPDATE companies 
SET schema_name = 'company_' || replace(lower(name), ' ', '_') || '_' || substring(id::text, 1, 8)
WHERE schema_name IS NULL;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_companies_schema_name ON companies(schema_name);

-- Add constraint to ensure schema_name is unique and not null
ALTER TABLE companies ALTER COLUMN schema_name SET NOT NULL;
ALTER TABLE companies ADD CONSTRAINT unique_schema_name UNIQUE (schema_name);

-- Add check constraint to ensure schema_name format is valid (letters, numbers, underscores only)
ALTER TABLE companies ADD CONSTRAINT check_schema_name_format 
CHECK (schema_name ~ '^[a-z0-9_]+$');

-- Comment for documentation
COMMENT ON COLUMN companies.schema_name IS 'Unique schema name for multi-tenant database isolation';