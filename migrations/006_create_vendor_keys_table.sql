-- Migration 006: Create vendor_keys table for company-specific vendor API key storage
-- This table stores encrypted vendor API keys for each company (BYOK functionality)

-- Create vendor_keys table in public schema (single-schema approach)
CREATE TABLE IF NOT EXISTS vendor_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    vendor VARCHAR(100) NOT NULL,
    encrypted_key TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    usage_count BIGINT DEFAULT 0,
    
    -- Ensure one active key per vendor per company
    UNIQUE(company_id, vendor)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_vendor_keys_company_vendor ON vendor_keys(company_id, vendor);
CREATE INDEX IF NOT EXISTS idx_vendor_keys_active ON vendor_keys(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_vendor_keys_last_used ON vendor_keys(last_used_at);

-- Add RLS (Row Level Security) for multi-tenancy
ALTER TABLE vendor_keys ENABLE ROW LEVEL SECURITY;

-- Create RLS policy to ensure companies can only access their own keys
CREATE POLICY vendor_keys_company_isolation ON vendor_keys
    FOR ALL
    USING (company_id = current_setting('app.current_company_id')::uuid);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON vendor_keys TO PUBLIC;

-- Add comments for documentation
COMMENT ON TABLE vendor_keys IS 'Encrypted vendor API keys for BYOK (Bring Your Own Key) functionality';
COMMENT ON COLUMN vendor_keys.company_id IS 'Company that owns this vendor key';
COMMENT ON COLUMN vendor_keys.vendor IS 'Vendor name (openai, anthropic, google, etc.)';
COMMENT ON COLUMN vendor_keys.encrypted_key IS 'AES-256 encrypted vendor API key';
COMMENT ON COLUMN vendor_keys.is_active IS 'Whether this key is currently active';
COMMENT ON COLUMN vendor_keys.usage_count IS 'Number of times this key has been used';