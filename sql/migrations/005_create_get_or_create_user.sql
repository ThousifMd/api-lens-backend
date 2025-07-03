-- Migration: Create get_or_create_user function
-- This function ensures a user exists in client_users and returns their UUID

CREATE OR REPLACE FUNCTION get_or_create_user(p_company_id uuid, p_client_user_id varchar)
RETURNS uuid AS $$
DECLARE
    v_user_id uuid;
BEGIN
    -- Try to find the user
    SELECT id INTO v_user_id
    FROM client_users
    WHERE company_id = p_company_id AND client_user_id = p_client_user_id;

    IF v_user_id IS NOT NULL THEN
        RETURN v_user_id;
    END IF;

    -- Insert new user and return id
    INSERT INTO client_users (company_id, client_user_id)
    VALUES (p_company_id, p_client_user_id)
    ON CONFLICT (company_id, client_user_id) DO UPDATE SET company_id = EXCLUDED.company_id
    RETURNING id INTO v_user_id;

    RETURN v_user_id;
END;
$$ LANGUAGE plpgsql; 