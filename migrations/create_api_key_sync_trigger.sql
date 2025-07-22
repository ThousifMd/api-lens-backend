-- Create function to notify when api_keys change
CREATE OR REPLACE FUNCTION notify_api_key_change()
RETURNS TRIGGER AS $$
DECLARE
    payload json;
    company_data record;
BEGIN
    -- Get company data for the API key
    SELECT c.id, c.name, c.tier, c.is_active
    INTO company_data
    FROM companies c
    WHERE c.id = COALESCE(NEW.company_id, OLD.company_id);
    
    -- Build the payload
    IF TG_OP = 'DELETE' THEN
        payload = json_build_object(
            'operation', 'DELETE',
            'key_hash', OLD.key_hash,
            'timestamp', NOW()
        );
    ELSE
        payload = json_build_object(
            'operation', TG_OP,
            'key_hash', COALESCE(NEW.key_hash, OLD.key_hash),
            'company_id', company_data.id,
            'company_name', company_data.name,
            'company_tier', company_data.tier,
            'is_active', NEW.is_active AND company_data.is_active,
            'timestamp', NOW()
        );
    END IF;
    
    -- Send notification
    PERFORM pg_notify('api_key_changes', payload::text);
    
    -- Also insert into a sync queue table for reliability
    INSERT INTO kv_sync_queue (
        table_name,
        operation,
        key_hash,
        payload,
        created_at
    ) VALUES (
        'api_keys',
        TG_OP,
        COALESCE(NEW.key_hash, OLD.key_hash),
        payload,
        NOW()
    );
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Create the sync queue table
CREATE TABLE IF NOT EXISTS kv_sync_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    key_hash VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for unprocessed items
CREATE INDEX idx_kv_sync_queue_unprocessed 
ON kv_sync_queue(processed, created_at) 
WHERE processed = FALSE;

-- Create the trigger
DROP TRIGGER IF EXISTS api_key_sync_trigger ON api_keys;
CREATE TRIGGER api_key_sync_trigger
AFTER INSERT OR UPDATE OR DELETE ON api_keys
FOR EACH ROW EXECUTE FUNCTION notify_api_key_change();

-- Also trigger on company updates (in case company becomes inactive)
CREATE OR REPLACE FUNCTION notify_company_change()
RETURNS TRIGGER AS $$
DECLARE
    payload json;
    key_record record;
BEGIN
    -- Only care about is_active changes
    IF OLD.is_active IS DISTINCT FROM NEW.is_active THEN
        -- Get all API keys for this company
        FOR key_record IN 
            SELECT key_hash 
            FROM api_keys 
            WHERE company_id = NEW.id
        LOOP
            payload = json_build_object(
                'operation', 'UPDATE',
                'key_hash', key_record.key_hash,
                'company_id', NEW.id,
                'company_name', NEW.name,
                'company_tier', NEW.tier,
                'is_active', NEW.is_active,
                'timestamp', NOW()
            );
            
            -- Insert into sync queue
            INSERT INTO kv_sync_queue (
                table_name,
                operation,
                key_hash,
                payload,
                created_at
            ) VALUES (
                'companies',
                'UPDATE',
                key_record.key_hash,
                payload,
                NOW()
            );
        END LOOP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on companies table
DROP TRIGGER IF EXISTS company_sync_trigger ON companies;
CREATE TRIGGER company_sync_trigger
AFTER UPDATE ON companies
FOR EACH ROW EXECUTE FUNCTION notify_company_change();