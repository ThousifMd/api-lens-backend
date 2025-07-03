-- ============================================================================
-- Initial Data and Configuration
-- ============================================================================

-- Insert sample vendors and models
INSERT INTO vendors (name, display_name, description, website_url) VALUES
('openai', 'OpenAI', 'OpenAI API services', 'https://openai.com'),
('anthropic', 'Anthropic', 'Claude AI services', 'https://anthropic.com'),
('google', 'Google', 'Google AI services', 'https://ai.google.dev'),
('cohere', 'Cohere', 'Cohere AI services', 'https://cohere.ai'),
('mistral', 'Mistral AI', 'Mistral AI services', 'https://mistral.ai')
ON CONFLICT (name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    updated_at = NOW();

-- Insert vendor models with enhanced metadata
INSERT INTO vendor_models (vendor_id, name, display_name, model_type, context_window, max_output_tokens) VALUES
-- OpenAI models
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-3.5-turbo', 'GPT-3.5 Turbo', 'chat', 16384, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4', 'GPT-4', 'chat', 8192, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4-turbo', 'GPT-4 Turbo', 'chat', 128000, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4o', 'GPT-4o', 'chat', 128000, 4096),
((SELECT id FROM vendors WHERE name = 'openai'), 'gpt-4o-mini', 'GPT-4o Mini', 'chat', 128000, 16384),
-- Anthropic models
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-opus-20240229', 'Claude 3 Opus', 'chat', 200000, 4096),
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-sonnet-20240229', 'Claude 3 Sonnet', 'chat', 200000, 4096),
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-haiku-20240307', 'Claude 3 Haiku', 'chat', 200000, 4096),
((SELECT id FROM vendors WHERE name = 'anthropic'), 'claude-3-5-sonnet-20241022', 'Claude 3.5 Sonnet', 'chat', 200000, 8192),
-- Google models
((SELECT id FROM vendors WHERE name = 'google'), 'gemini-pro', 'Gemini Pro', 'chat', 32768, 8192),
((SELECT id FROM vendors WHERE name = 'google'), 'gemini-pro-vision', 'Gemini Pro Vision', 'chat', 32768, 8192),
((SELECT id FROM vendors WHERE name = 'google'), 'gemini-1.5-pro', 'Gemini 1.5 Pro', 'chat', 1048576, 8192),
-- Cohere models
((SELECT id FROM vendors WHERE name = 'cohere'), 'command-r', 'Command R', 'chat', 128000, 4096),
((SELECT id FROM vendors WHERE name = 'cohere'), 'command-r-plus', 'Command R+', 'chat', 128000, 4096),
-- Mistral models
((SELECT id FROM vendors WHERE name = 'mistral'), 'mistral-medium', 'Mistral Medium', 'chat', 32000, 8192),
((SELECT id FROM vendors WHERE name = 'mistral'), 'mistral-large', 'Mistral Large', 'chat', 32000, 8192)
ON CONFLICT (vendor_id, name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    context_window = EXCLUDED.context_window,
    max_output_tokens = EXCLUDED.max_output_tokens,
    updated_at = NOW();

-- Insert current pricing (2024 rates)
INSERT INTO vendor_pricing (vendor_id, model_id, input_cost_per_1k_tokens, output_cost_per_1k_tokens) VALUES
-- OpenAI pricing
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-3.5-turbo'), 0.0005, 0.0015),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4'), 0.03, 0.06),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4-turbo'), 0.01, 0.03),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4o'), 0.0025, 0.01),
((SELECT id FROM vendors WHERE name = 'openai'), (SELECT id FROM vendor_models WHERE name = 'gpt-4o-mini'), 0.00015, 0.0006),
-- Anthropic pricing
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-opus-20240229'), 0.015, 0.075),
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-sonnet-20240229'), 0.003, 0.015),
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-haiku-20240307'), 0.00025, 0.00125),
((SELECT id FROM vendors WHERE name = 'anthropic'), (SELECT id FROM vendor_models WHERE name = 'claude-3-5-sonnet-20241022'), 0.003, 0.015),
-- Google pricing
((SELECT id FROM vendors WHERE name = 'google'), (SELECT id FROM vendor_models WHERE name = 'gemini-pro'), 0.0005, 0.0015),
((SELECT id FROM vendors WHERE name = 'google'), (SELECT id FROM vendor_models WHERE name = 'gemini-pro-vision'), 0.0005, 0.0015),
((SELECT id FROM vendors WHERE name = 'google'), (SELECT id FROM vendor_models WHERE name = 'gemini-1.5-pro'), 0.00175, 0.007),
-- Cohere pricing
((SELECT id FROM vendors WHERE name = 'cohere'), (SELECT id FROM vendor_models WHERE name = 'command-r'), 0.0005, 0.0015),
((SELECT id FROM vendors WHERE name = 'cohere'), (SELECT id FROM vendor_models WHERE name = 'command-r-plus'), 0.003, 0.015),
-- Mistral pricing
((SELECT id FROM vendors WHERE name = 'mistral'), (SELECT id FROM vendor_models WHERE name = 'mistral-medium'), 0.00275, 0.0081),
((SELECT id FROM vendors WHERE name = 'mistral'), (SELECT id FROM vendor_models WHERE name = 'mistral-large'), 0.008, 0.024)
ON CONFLICT DO NOTHING;

-- Insert sample companies for testing
INSERT INTO companies (name, slug, contact_email, tier, require_user_id) VALUES
('Test Company', 'test-company', 'admin@test.com', 'enterprise', true),
('Demo Corp', 'demo-corp', 'demo@demo.com', 'professional', false)
ON CONFLICT (slug) DO NOTHING;

-- Generate sample API keys for testing companies
DO $$
DECLARE
    test_company_id UUID;
    demo_company_id UUID;
    test_key_result RECORD;
    demo_key_result RECORD;
BEGIN
    -- Get company IDs
    SELECT id INTO test_company_id FROM companies WHERE slug = 'test-company';
    SELECT id INTO demo_company_id FROM companies WHERE slug = 'demo-corp';
    
    -- Generate API keys
    SELECT * INTO test_key_result FROM generate_api_key(test_company_id, 'Test API Key', 'production', 'system');
    SELECT * INTO demo_key_result FROM generate_api_key(demo_company_id, 'Demo API Key', 'production', 'system');
    
    -- Log the generated keys (in production, these would be securely delivered)
    RAISE NOTICE 'Test Company API Key: %', test_key_result.api_key;
    RAISE NOTICE 'Demo Company API Key: %', demo_key_result.api_key;
END $$;

-- ============================================================================
-- Create roles and permissions
-- ============================================================================

-- Create roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_lens_readonly') THEN
        CREATE ROLE api_lens_readonly;
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_lens_api') THEN
        CREATE ROLE api_lens_api;
    END IF;
    
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_lens_admin') THEN
        CREATE ROLE api_lens_admin;
    END IF;
END $$;

-- Grant permissions to readonly role
GRANT SELECT ON ALL TABLES IN SCHEMA public TO api_lens_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO api_lens_readonly;

-- Grant permissions to API role
GRANT SELECT, INSERT, UPDATE ON requests, client_users, user_sessions TO api_lens_api;
GRANT SELECT ON companies, api_keys, vendors, vendor_models, vendor_pricing TO api_lens_api;
GRANT EXECUTE ON FUNCTION track_request TO api_lens_api;
GRANT EXECUTE ON FUNCTION get_or_create_vendor TO api_lens_api;
GRANT EXECUTE ON FUNCTION get_or_create_vendor_model TO api_lens_api;
GRANT EXECUTE ON FUNCTION get_or_create_client_user TO api_lens_api;

-- Grant all permissions to admin role
GRANT ALL ON ALL TABLES IN SCHEMA public TO api_lens_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO api_lens_admin;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO api_lens_admin;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check schema health
SELECT 
    'Schema created successfully!' as status,
    (SELECT COUNT(*) FROM vendors) as vendor_count,
    (SELECT COUNT(*) FROM vendor_models) as model_count,
    (SELECT COUNT(*) FROM vendor_pricing WHERE is_active = true) as active_pricing_count,
    (SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE 'requests_%') as request_partitions,
    (SELECT COUNT(*) FROM companies) as company_count,
    (SELECT COUNT(*) FROM api_keys) as api_key_count;