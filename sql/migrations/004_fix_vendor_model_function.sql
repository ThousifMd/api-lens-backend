-- ============================================================================
-- Fix get_or_create_vendor_model function to include required columns
-- ============================================================================

-- Drop the existing function
DROP FUNCTION IF EXISTS get_or_create_vendor_model(VARCHAR, VARCHAR);

-- Create the fixed function
CREATE OR REPLACE FUNCTION get_or_create_vendor_model(p_vendor_name VARCHAR, p_model_name VARCHAR)
RETURNS UUID AS $$
DECLARE
    v_vendor_id UUID;
    v_model_id UUID;
BEGIN
    -- Get or create vendor
    v_vendor_id := get_or_create_vendor(p_vendor_name);
    
    -- Try to get existing model
    SELECT id INTO v_model_id FROM vendor_models 
    WHERE vendor_id = v_vendor_id AND name = p_model_name;
    
    -- Create if doesn't exist
    IF v_model_id IS NULL THEN
        INSERT INTO vendor_models (
            vendor_id, 
            name, 
            slug, 
            model_type, 
            input_price_per_1k, 
            output_price_per_1k,
            is_active
        ) VALUES (
            v_vendor_id, 
            p_model_name, 
            p_model_name, -- Use model name as slug
            'chat', 
            0.01, -- Default input price
            0.02, -- Default output price
            true
        ) RETURNING id INTO v_model_id;
    END IF;
    
    RETURN v_model_id;
END;
$$ LANGUAGE plpgsql; 