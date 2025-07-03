-- ============================================================================
-- Migration 002: Composite Keys and Partitioning Support
-- ============================================================================
-- This migration updates the database to support composite primary keys
-- and proper partitioning for the requests table

-- Step 1: Drop existing foreign key constraints that reference requests(id)
ALTER TABLE IF EXISTS cost_calculations DROP CONSTRAINT IF EXISTS cost_calculations_request_id_fkey;
ALTER TABLE IF EXISTS request_errors DROP CONSTRAINT IF EXISTS request_errors_request_id_fkey;

-- Step 2: Add request_created_at column to cost_calculations
ALTER TABLE cost_calculations ADD COLUMN IF NOT EXISTS request_created_at TIMESTAMPTZ;

-- Step 3: Update cost_calculations to populate request_created_at
UPDATE cost_calculations 
SET request_created_at = r.created_at 
FROM requests r 
WHERE cost_calculations.request_id = r.id 
AND cost_calculations.request_created_at IS NULL;

-- Step 4: Make request_created_at NOT NULL after populating
ALTER TABLE cost_calculations ALTER COLUMN request_created_at SET NOT NULL;

-- Step 5: Add composite foreign key constraint to cost_calculations
ALTER TABLE cost_calculations 
ADD CONSTRAINT cost_calculations_request_fkey 
FOREIGN KEY (request_id, request_created_at) REFERENCES requests(id, created_at) ON DELETE CASCADE;

-- Step 6: Create request_errors table if it doesn't exist
CREATE TABLE IF NOT EXISTS request_errors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL,
    request_created_at TIMESTAMPTZ NOT NULL,
    
    -- Error details
    error_message TEXT NOT NULL,
    error_code VARCHAR(100),
    error_type VARCHAR(50) NOT NULL CHECK (error_type IN ('api_error', 'timeout', 'rate_limit', 'quota_exceeded', 'authentication', 'validation')),
    
    -- Error context
    error_metadata JSONB DEFAULT '{}',
    stack_trace TEXT,
    
    -- Timing
    error_timestamp TIMESTAMPTZ DEFAULT NOW(),
    calculated_timestamp TEXT, -- Local timezone timestamp
    
    -- Constraints
    FOREIGN KEY (request_id, request_created_at) REFERENCES requests(id, created_at) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 7: Add generated column for easier partitioning
ALTER TABLE requests ADD COLUMN IF NOT EXISTS created_date DATE GENERATED ALWAYS AS (created_at::DATE) STORED;

-- Step 8: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_cost_calculations_request ON cost_calculations(request_id, request_created_at);
CREATE INDEX IF NOT EXISTS idx_cost_calculations_timestamp ON cost_calculations(calculation_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_errors_request ON request_errors(request_id, request_created_at);
CREATE INDEX IF NOT EXISTS idx_request_errors_timestamp ON request_errors(error_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_errors_type ON request_errors(error_type, error_timestamp DESC);

-- Step 9: Verify the migration
DO $$
BEGIN
    -- Check that all cost_calculations have request_created_at populated
    IF EXISTS (
        SELECT 1 FROM cost_calculations 
        WHERE request_created_at IS NULL
    ) THEN
        RAISE EXCEPTION 'Some cost_calculations records have NULL request_created_at';
    END IF;
    
    -- Check that foreign key constraints are working
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'cost_calculations_request_fkey'
        AND table_name = 'cost_calculations'
    ) THEN
        RAISE EXCEPTION 'Composite foreign key constraint not created';
    END IF;
    
    RAISE NOTICE 'Migration 002 completed successfully';
END $$; 