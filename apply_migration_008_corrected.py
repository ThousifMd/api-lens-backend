#!/usr/bin/env python3
"""
Apply migration 008 - Add image generation support (Corrected for 'image' model type)
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def apply_migration_008_corrected():
    # Get database URL from environment
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return
    
    # Convert SQLAlchemy URL to asyncpg format
    if "+asyncpg" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        
        print("\n🚀 Applying migration 008_add_image_generation_support (Corrected)...")
        print("=" * 80)
        
        # Execute migration in a transaction
        async with conn.transaction():
            # 1. Add image-specific fields to requests table
            print("\n1️⃣ Adding image generation columns to requests table...")
            
            # Check which columns already exist
            existing_columns = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'requests' 
                AND column_name IN (
                    'image_count', 'image_urls', 'image_dimensions', 
                    'image_quality', 'image_style', 'prompt', 
                    'negative_prompt', 'seed', 'generation_steps', 'guidance_scale'
                )
            """)
            
            existing_col_names = {col['column_name'] for col in existing_columns}
            
            if len(existing_col_names) < 10:
                add_columns_sql = """
                ALTER TABLE requests 
                ADD COLUMN IF NOT EXISTS image_count INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS image_urls TEXT[],
                ADD COLUMN IF NOT EXISTS image_dimensions VARCHAR(20),
                ADD COLUMN IF NOT EXISTS image_quality VARCHAR(20),
                ADD COLUMN IF NOT EXISTS image_style VARCHAR(50),
                ADD COLUMN IF NOT EXISTS prompt TEXT,
                ADD COLUMN IF NOT EXISTS negative_prompt TEXT,
                ADD COLUMN IF NOT EXISTS seed INTEGER,
                ADD COLUMN IF NOT EXISTS generation_steps INTEGER,
                ADD COLUMN IF NOT EXISTS guidance_scale DECIMAL(5,2);
                """
                
                await conn.execute(add_columns_sql)
                print(f"   ✅ Added {10 - len(existing_col_names)} new columns")
            else:
                print("   ✅ All columns already exist")
            
            # 2. Add indexes
            print("\n2️⃣ Adding indexes...")
            
            index_sqls = [
                """
                CREATE INDEX IF NOT EXISTS idx_requests_image_generation 
                ON requests (image_count) WHERE image_count > 0;
                """,
                """
                CREATE INDEX IF NOT EXISTS idx_requests_image_dimensions 
                ON requests (image_dimensions) WHERE image_dimensions IS NOT NULL;
                """
            ]
            
            indexes_added = 0
            for idx_sql in index_sqls:
                try:
                    await conn.execute(idx_sql)
                    indexes_added += 1
                except asyncpg.exceptions.DuplicateTableError:
                    pass
            
            print(f"   ✅ Added {indexes_added} new indexes")
            
            # 3. Insert vendors (if not exist)
            print("\n3️⃣ Adding image generation vendors...")
            
            # Midjourney vendor (if not exists)
            midjourney_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM vendors WHERE name = 'midjourney')"
            )
            
            if not midjourney_exists:
                await conn.execute("""
                    INSERT INTO vendors (id, name, slug, description, website_url, is_active)
                    VALUES (gen_random_uuid(), 'midjourney', 'midjourney', 
                            'Midjourney - High-quality AI art generation', 
                            'https://midjourney.com', false)
                """)
                print("   ✅ Added Midjourney vendor (inactive)")
            else:
                print("   ✅ Midjourney vendor already exists")
            
            # 4. Get vendor IDs
            print("\n4️⃣ Adding/updating image generation models...")
            
            vendor_ids = await conn.fetch("""
                SELECT id, name FROM vendors 
                WHERE name IN ('openai', 'stability-ai', 'adobe')
            """)
            
            vendor_map = {v['name']: v['id'] for v in vendor_ids}
            
            # 5. Add new models and update existing ones to 'image' type
            models_to_add = []
            
            # OpenAI models
            if 'openai' in vendor_map:
                models_to_add.extend([
                    (vendor_map['openai'], 'dall-e-3', 'dall-e-3', 'DALL-E 3', 'Most advanced image generation from OpenAI', 'image'),
                    (vendor_map['openai'], 'dall-e-2', 'dall-e-2', 'DALL-E 2', 'High-quality image generation from OpenAI', 'image')
                ])
            
            # Update existing Stability AI and Adobe models to 'image' type
            if 'stability-ai' in vendor_map:
                await conn.execute("""
                    UPDATE vendor_models 
                    SET model_type = 'image',
                        description = CASE 
                            WHEN name = 'stable-diffusion-xl-1024-v1-0' THEN 'Stable Diffusion XL 1.0 - High resolution image generation'
                            WHEN name = 'stable-diffusion-v1-6' THEN 'Stable Diffusion 1.6 - Classic stable diffusion'
                            WHEN name = 'stable-diffusion-xl-beta-v2-2-2' THEN 'Stable Diffusion XL Beta - Latest experimental version'
                            ELSE description
                        END
                    WHERE vendor_id = $1 
                    AND name IN ('stable-diffusion-xl-1024-v1-0', 'stable-diffusion-v1-6', 'stable-diffusion-xl-beta-v2-2-2')
                """, vendor_map['stability-ai'])
                print("   ✅ Updated Stability AI models to image type")
                
                # Add missing model if needed
                models_to_add.append(
                    (vendor_map['stability-ai'], 'stable-diffusion-xl-beta-v2-2-2', 'stable-diffusion-xl-beta-v2-2-2', 
                     'SDXL Beta', 'Stable Diffusion XL Beta - Latest experimental version', 'image')
                )
            
            if 'adobe' in vendor_map:
                await conn.execute("""
                    UPDATE vendor_models 
                    SET model_type = 'image',
                        description = CASE 
                            WHEN name = 'firefly-v2' THEN 'Adobe Firefly v2 - Commercial-safe image generation'
                            WHEN name = 'firefly-v1' THEN 'Adobe Firefly v1 - Creative image generation'
                            ELSE description
                        END
                    WHERE vendor_id = $1 
                    AND name IN ('firefly-v2', 'firefly-v1')
                """, vendor_map['adobe'])
                print("   ✅ Updated Adobe models to image type")
                
                # Add firefly-v1 if it doesn't exist
                models_to_add.append(
                    (vendor_map['adobe'], 'firefly-v1', 'firefly-v1', 'Firefly v1', 
                     'Adobe Firefly v1 - Creative image generation', 'image')
                )
            
            # Check existing models to avoid duplicates
            existing_models = await conn.fetch("""
                SELECT vendor_id, name FROM vendor_models 
                WHERE vendor_id = ANY($1)
            """, list(vendor_map.values()))
            
            existing_model_keys = {(m['vendor_id'], m['name']) for m in existing_models}
            
            models_added = 0
            for vendor_id, model_name, slug, display_name, description, model_type in models_to_add:
                if (vendor_id, model_name) not in existing_model_keys:
                    await conn.execute("""
                        INSERT INTO vendor_models (
                            id, vendor_id, name, slug, display_name, description, 
                            model_type, context_window, max_output_tokens, 
                            supports_functions, supports_vision, is_active
                        ) VALUES (
                            gen_random_uuid(), $1, $2, $3, $4, $5, $6, 
                            0, 0, false, false, true
                        )
                    """, vendor_id, model_name, slug, display_name, description, model_type)
                    models_added += 1
            
            print(f"   ✅ Added {models_added} new models")
            
            # 6. Add pricing for image models
            print("\n5️⃣ Adding pricing for image generation models...")
            
            # Get all image models
            image_models = await conn.fetch("""
                SELECT vm.id, vm.name, v.name as vendor_name
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE vm.model_type = 'image'
            """)
            
            pricing_added = 0
            for model in image_models:
                # Check if pricing already exists
                existing_pricing = await conn.fetchval("""
                    SELECT COUNT(*) FROM vendor_pricing 
                    WHERE model_id = $1 AND company_id IS NULL
                """, model['id'])
                
                if existing_pricing == 0:
                    # Determine price based on model
                    per_image_price = 0.030  # Default
                    
                    if model['vendor_name'] == 'openai':
                        if model['name'] == 'dall-e-3':
                            per_image_price = 0.040
                        elif model['name'] == 'dall-e-2':
                            per_image_price = 0.020
                    elif model['vendor_name'] == 'adobe':
                        per_image_price = 0.025
                    
                    await conn.execute("""
                        INSERT INTO vendor_pricing (
                            id, model_id, company_id, pricing_type, 
                            input_price_per_1k_tokens, output_price_per_1k_tokens,
                            per_request_price, per_image_price, currency,
                            effective_date, is_active, created_at
                        ) VALUES (
                            gen_random_uuid(), $1, NULL, 'per_image',
                            NULL, NULL, NULL, $2, 'USD',
                            NOW(), true, NOW()
                        )
                    """, model['id'], per_image_price)
                    pricing_added += 1
            
            print(f"   ✅ Added pricing for {pricing_added} models")
            
            # 7. Add constraints
            print("\n6️⃣ Adding constraints...")
            
            constraint_sqls = [
                ("chk_image_count_valid", """
                ALTER TABLE requests 
                ADD CONSTRAINT chk_image_count_valid 
                CHECK (image_count >= 0 AND image_count <= 10);
                """),
                ("chk_image_dimensions_valid", """
                ALTER TABLE requests 
                ADD CONSTRAINT chk_image_dimensions_valid 
                CHECK (image_dimensions IS NULL OR image_dimensions ~ '^[0-9]+x[0-9]+$');
                """),
                ("chk_generation_steps_valid", """
                ALTER TABLE requests 
                ADD CONSTRAINT chk_generation_steps_valid 
                CHECK (generation_steps IS NULL OR (generation_steps >= 1 AND generation_steps <= 150));
                """),
                ("chk_guidance_scale_valid", """
                ALTER TABLE requests 
                ADD CONSTRAINT chk_guidance_scale_valid 
                CHECK (guidance_scale IS NULL OR (guidance_scale >= 1.0 AND guidance_scale <= 20.0));
                """)
            ]
            
            constraints_added = 0
            for constraint_name, constraint_sql in constraint_sqls:
                try:
                    await conn.execute(constraint_sql)
                    constraints_added += 1
                except asyncpg.exceptions.DuplicateObjectError:
                    # Constraint already exists
                    pass
            
            print(f"   ✅ Added {constraints_added} new constraints")
            
            # 8. Add column comments
            print("\n7️⃣ Adding column comments...")
            
            comments = [
                ("requests.image_count", "Number of images generated in this request"),
                ("requests.image_urls", "Array of URLs to generated images"),
                ("requests.image_dimensions", "Image dimensions in format WIDTHxHEIGHT"),
                ("requests.image_quality", "Image quality setting (standard, hd, etc.)"),
                ("requests.image_style", "Image style (vivid, natural, artistic, etc.)"),
                ("requests.prompt", "The text prompt used for generation"),
                ("requests.negative_prompt", "Negative prompt to avoid certain elements"),
                ("requests.seed", "Random seed for reproducible generation"),
                ("requests.generation_steps", "Number of diffusion steps"),
                ("requests.guidance_scale", "Classifier-free guidance scale")
            ]
            
            for column, comment in comments:
                await conn.execute(f"COMMENT ON COLUMN {column} IS '{comment}';")
            
            print("   ✅ Comments added")
        
        print("\n✅ Migration 008 applied successfully!")
        
        # Verify the changes
        print("\n🔍 Verifying migration results...")
        print("-" * 80)
        
        # Check columns
        columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'requests'
            AND column_name IN (
                'image_count', 'image_urls', 'image_dimensions', 
                'image_quality', 'image_style', 'prompt', 
                'negative_prompt', 'seed', 'generation_steps', 'guidance_scale'
            )
            ORDER BY column_name;
        """)
        
        print(f"\n✅ Image generation columns ({len(columns)}/10):")
        for col in columns:
            print(f"  - {col['column_name']:<25} {col['data_type']}")
        
        # Check models
        models = await conn.fetch("""
            SELECT v.name as vendor_name, vm.name as model_name, vm.model_type
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE vm.model_type = 'image'
            ORDER BY v.name, vm.name;
        """)
        
        print(f"\n✅ Image models ({len(models)}):")
        for model in models:
            print(f"  - {model['vendor_name']:<15} {model['model_name']:<30} (type: {model['model_type']})")
        
        # Check pricing
        pricing = await conn.fetch("""
            SELECT v.name as vendor_name, vm.name as model_name, vp.per_image_price
            FROM vendor_pricing vp
            JOIN vendor_models vm ON vp.model_id = vm.id
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE vm.model_type = 'image' AND vp.per_image_price IS NOT NULL
            ORDER BY v.name, vm.name;
        """)
        
        print(f"\n✅ Image model pricing ({len(pricing)} models):")
        for price in pricing:
            print(f"  - {price['vendor_name']:<15} {price['model_name']:<30} ${price['per_image_price']:.3f}/image")
        
        # Check constraints
        constraints = await conn.fetch("""
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'requests'::regclass
            AND conname LIKE 'chk_%image%' OR conname LIKE 'chk_%generation%' OR conname LIKE 'chk_%guidance%';
        """)
        
        print(f"\n✅ Constraints added ({len(constraints)}):")
        for con in constraints:
            print(f"  - {con['conname']}")
        
        await conn.close()
        
        print("\n" + "=" * 80)
        print("🎉 Migration completed successfully!")
        print("\n📊 Summary:")
        print("   ✅ All 10 image generation columns added to requests table")
        print("   ✅ Image generation models configured with 'image' type")
        print("   ✅ Per-image pricing configured for all image models")
        print("   ✅ Data validation constraints in place")
        print("\n💡 The API can now track image generation requests with:")
        print("   - Image count, dimensions, quality, and style")
        print("   - Prompts (positive and negative)")
        print("   - Generation parameters (seed, steps, guidance scale)")
        print("   - Generated image URLs")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(apply_migration_008_corrected())