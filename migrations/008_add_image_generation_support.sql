-- Migration: Add Image Generation Support
-- Adds comprehensive image generation fields to requests table and new image vendors/models

-- Add image-specific fields to requests table
ALTER TABLE requests 
ADD COLUMN IF NOT EXISTS image_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS image_urls TEXT[], -- Array of generated image URLs
ADD COLUMN IF NOT EXISTS image_dimensions VARCHAR(20), -- e.g., "1024x1024", "512x512"
ADD COLUMN IF NOT EXISTS image_quality VARCHAR(20), -- e.g., "standard", "hd"
ADD COLUMN IF NOT EXISTS image_style VARCHAR(50), -- e.g., "vivid", "natural"
ADD COLUMN IF NOT EXISTS prompt TEXT, -- The image generation prompt
ADD COLUMN IF NOT EXISTS negative_prompt TEXT, -- Negative prompt for better control
ADD COLUMN IF NOT EXISTS seed INTEGER, -- Seed for reproducible generation
ADD COLUMN IF NOT EXISTS generation_steps INTEGER, -- Number of diffusion steps
ADD COLUMN IF NOT EXISTS guidance_scale DECIMAL(5,2); -- CFG scale for prompt adherence

-- Add index for image generation requests
CREATE INDEX IF NOT EXISTS idx_requests_image_generation 
ON requests (image_count) WHERE image_count > 0;

-- Add index for image dimensions
CREATE INDEX IF NOT EXISTS idx_requests_image_dimensions 
ON requests (image_dimensions) WHERE image_dimensions IS NOT NULL;

-- Insert Stability AI vendor if not exists
INSERT INTO vendors (id, name, display_name, description, base_url, is_active)
VALUES (
    gen_random_uuid(),
    'stability-ai',
    'Stability AI',
    'Stability AI - SDXL, Stable Diffusion and other generative models',
    'https://api.stability.ai',
    true
) ON CONFLICT (name) DO NOTHING;

-- Insert Midjourney vendor if not exists (for future use)
INSERT INTO vendors (id, name, display_name, description, base_url, is_active)
VALUES (
    gen_random_uuid(),
    'midjourney',
    'Midjourney',
    'Midjourney - High-quality AI art generation',
    'https://api.midjourney.com',
    false  -- Not yet available via API
) ON CONFLICT (name) DO NOTHING;

-- Insert Adobe vendor if not exists
INSERT INTO vendors (id, name, display_name, description, base_url, is_active)
VALUES (
    gen_random_uuid(),
    'adobe',
    'Adobe',
    'Adobe Firefly - Creative generative AI',
    'https://api.adobe.io',
    true
) ON CONFLICT (name) DO NOTHING;

-- Get vendor IDs for model insertion
DO $$
DECLARE
    openai_id UUID;
    stability_id UUID;
    adobe_id UUID;
BEGIN
    -- Get vendor IDs
    SELECT id INTO openai_id FROM vendors WHERE name = 'openai';
    SELECT id INTO stability_id FROM vendors WHERE name = 'stability-ai';
    SELECT id INTO adobe_id FROM vendors WHERE name = 'adobe';

    -- Insert OpenAI image models (if not already exist)
    INSERT INTO vendor_models (id, vendor_id, name, display_name, description, model_type, context_window, max_output_tokens, supports_functions, supports_vision, is_active)
    VALUES 
        (gen_random_uuid(), openai_id, 'dall-e-3', 'DALL-E 3', 'Most advanced image generation from OpenAI', 'image_generation', 0, 0, false, false, true),
        (gen_random_uuid(), openai_id, 'dall-e-2', 'DALL-E 2', 'High-quality image generation from OpenAI', 'image_generation', 0, 0, false, false, true)
    ON CONFLICT (vendor_id, name) DO NOTHING;

    -- Insert Stability AI models
    INSERT INTO vendor_models (id, vendor_id, name, display_name, description, model_type, context_window, max_output_tokens, supports_functions, supports_vision, is_active)
    VALUES 
        (gen_random_uuid(), stability_id, 'stable-diffusion-xl-1024-v1-0', 'SDXL 1.0', 'Stable Diffusion XL 1.0 - High resolution image generation', 'image_generation', 0, 0, false, false, true),
        (gen_random_uuid(), stability_id, 'stable-diffusion-v1-6', 'SD 1.6', 'Stable Diffusion 1.6 - Classic stable diffusion', 'image_generation', 0, 0, false, false, true),
        (gen_random_uuid(), stability_id, 'stable-diffusion-xl-beta-v2-2-2', 'SDXL Beta', 'Stable Diffusion XL Beta - Latest experimental version', 'image_generation', 0, 0, false, false, true)
    ON CONFLICT (vendor_id, name) DO NOTHING;

    -- Insert Adobe Firefly models
    INSERT INTO vendor_models (id, vendor_id, name, display_name, description, model_type, context_window, max_output_tokens, supports_functions, supports_vision, is_active)
    VALUES 
        (gen_random_uuid(), adobe_id, 'firefly-v2', 'Firefly v2', 'Adobe Firefly v2 - Commercial-safe image generation', 'image_generation', 0, 0, false, false, true),
        (gen_random_uuid(), adobe_id, 'firefly-v1', 'Firefly v1', 'Adobe Firefly v1 - Creative image generation', 'image_generation', 0, 0, false, false, true)
    ON CONFLICT (vendor_id, name) DO NOTHING;
END $$;

-- Insert default pricing for image generation models
DO $$
DECLARE
    model_record RECORD;
BEGIN
    -- OpenAI DALL-E pricing
    FOR model_record IN 
        SELECT vm.id as model_id, vm.name
        FROM vendor_models vm 
        JOIN vendors v ON vm.vendor_id = v.id 
        WHERE v.name = 'openai' AND vm.name LIKE 'dall-e%'
    LOOP
        INSERT INTO vendor_pricing (
            id, model_id, company_id, pricing_type, 
            input_price_per_1k_tokens, output_price_per_1k_tokens,
            per_request_price, per_image_price, currency,
            effective_date, is_active, created_at
        ) VALUES (
            gen_random_uuid(), model_record.model_id, NULL, 'per_image',
            NULL, NULL, NULL,
            CASE 
                WHEN model_record.name = 'dall-e-3' THEN 0.040  -- $0.040 per image for 1024x1024
                WHEN model_record.name = 'dall-e-2' THEN 0.020  -- $0.020 per image for 1024x1024
                ELSE 0.030
            END,
            'USD', NOW(), true, NOW()
        ) ON CONFLICT (model_id, company_id, effective_date) DO NOTHING;
    END LOOP;

    -- Stability AI pricing
    FOR model_record IN 
        SELECT vm.id as model_id, vm.name
        FROM vendor_models vm 
        JOIN vendors v ON vm.vendor_id = v.id 
        WHERE v.name = 'stability-ai'
    LOOP
        INSERT INTO vendor_pricing (
            id, model_id, company_id, pricing_type, 
            input_price_per_1k_tokens, output_price_per_1k_tokens,
            per_request_price, per_image_price, currency,
            effective_date, is_active, created_at
        ) VALUES (
            gen_random_uuid(), model_record.model_id, NULL, 'per_image',
            NULL, NULL, NULL, 0.030,  -- $0.030 per image for Stability AI
            'USD', NOW(), true, NOW()
        ) ON CONFLICT (model_id, company_id, effective_date) DO NOTHING;
    END LOOP;

    -- Adobe Firefly pricing
    FOR model_record IN 
        SELECT vm.id as model_id, vm.name
        FROM vendor_models vm 
        JOIN vendors v ON vm.vendor_id = v.id 
        WHERE v.name = 'adobe'
    LOOP
        INSERT INTO vendor_pricing (
            id, model_id, company_id, pricing_type, 
            input_price_per_1k_tokens, output_price_per_1k_tokens,
            per_request_price, per_image_price, currency,
            effective_date, is_active, created_at
        ) VALUES (
            gen_random_uuid(), model_record.model_id, NULL, 'per_image',
            NULL, NULL, NULL, 0.025,  -- $0.025 per image for Adobe Firefly
            'USD', NOW(), true, NOW()
        ) ON CONFLICT (model_id, company_id, effective_date) DO NOTHING;
    END LOOP;
END $$;

-- Add constraints for image generation fields
ALTER TABLE requests 
ADD CONSTRAINT chk_image_count_valid 
CHECK (image_count >= 0 AND image_count <= 10);

ALTER TABLE requests 
ADD CONSTRAINT chk_image_dimensions_valid 
CHECK (image_dimensions IS NULL OR image_dimensions ~ '^[0-9]+x[0-9]+$');

ALTER TABLE requests 
ADD CONSTRAINT chk_generation_steps_valid 
CHECK (generation_steps IS NULL OR (generation_steps >= 1 AND generation_steps <= 150));

ALTER TABLE requests 
ADD CONSTRAINT chk_guidance_scale_valid 
CHECK (guidance_scale IS NULL OR (guidance_scale >= 1.0 AND guidance_scale <= 20.0));

-- Update existing DALL-E requests if any exist
UPDATE requests 
SET image_count = 1, 
    image_dimensions = '1024x1024',
    prompt = 'Generated image'
WHERE endpoint LIKE '%dall-e%' 
  OR endpoint LIKE '%image%' 
  OR (method = 'POST' AND endpoint LIKE '%generation%')
  AND image_count IS NULL;

COMMENT ON COLUMN requests.image_count IS 'Number of images generated in this request';
COMMENT ON COLUMN requests.image_urls IS 'Array of URLs to generated images';
COMMENT ON COLUMN requests.image_dimensions IS 'Image dimensions in format WIDTHxHEIGHT';
COMMENT ON COLUMN requests.image_quality IS 'Image quality setting (standard, hd, etc.)';
COMMENT ON COLUMN requests.image_style IS 'Image style (vivid, natural, artistic, etc.)';
COMMENT ON COLUMN requests.prompt IS 'The text prompt used for generation';
COMMENT ON COLUMN requests.negative_prompt IS 'Negative prompt to avoid certain elements';
COMMENT ON COLUMN requests.seed IS 'Random seed for reproducible generation';
COMMENT ON COLUMN requests.generation_steps IS 'Number of diffusion steps';
COMMENT ON COLUMN requests.guidance_scale IS 'Classifier-free guidance scale';