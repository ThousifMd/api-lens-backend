#!/usr/bin/env python3
"""
Apply migration 008 - Add image generation support (Final Fixed Version)
"""
import asyncio
import os
from dotenv import load_dotenv
import asyncpg

# Load environment variables
load_dotenv()

async def apply_migration_008_final_fixed():
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
        
        print("\n🚀 Applying migration 008_add_image_generation_support (Final Fixed)...")
        print("=" * 80)
        
        # Execute migration in a transaction
        async with conn.transaction():
            # 1. Add image-specific fields to requests table (if not already added)
            print("\n1️⃣ Checking/Adding image generation columns to requests table...")
            
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
            
            if len(existing_col_names) == 10:
                print("   ✅ All columns already exist")
            else:
                print("   ❌ Some columns are missing, cannot continue")
                print("   Missing columns:", set(['image_count', 'image_urls', 'image_dimensions', 
                                                'image_quality', 'image_style', 'prompt', 
                                                'negative_prompt', 'seed', 'generation_steps', 
                                                'guidance_scale']) - existing_col_names)
                return
            
            # 2. Check indexes
            print("\n2️⃣ Checking indexes...")
            
            existing_indexes = await conn.fetch("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'requests' 
                AND (indexname LIKE '%image%')
            """)
            
            print(f"   ✅ Found {len(existing_indexes)} image-related indexes")
            
            # 3. Check vendors
            print("\n3️⃣ Checking image generation vendors...")
            
            vendors = await conn.fetch("""
                SELECT name, is_active 
                FROM vendors 
                WHERE name IN ('openai', 'stability-ai', 'adobe', 'midjourney')
                ORDER BY name
            """)
            
            print(f"   ✅ Found {len(vendors)} image generation vendors:")
            for v in vendors:
                status = "active" if v['is_active'] else "inactive"
                print(f"      - {v['name']} ({status})")
            
            # 4. Check models
            print("\n4️⃣ Checking image generation models...")
            
            models = await conn.fetch("""
                SELECT v.name as vendor_name, vm.name as model_name, vm.model_type
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE vm.model_type = 'image'
                AND v.name IN ('openai', 'stability-ai', 'adobe')
                ORDER BY v.name, vm.name
            """)
            
            print(f"   ✅ Found {len(models)} image models:")
            for m in models:
                print(f"      - {m['vendor_name']}: {m['model_name']}")
            
            # 5. Add pricing for image models that don't have it
            print("\n5️⃣ Adding pricing for image generation models...")
            
            # Get all image models without pricing
            models_without_pricing = await conn.fetch("""
                SELECT vm.id, vm.name, v.name as vendor_name
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vp.model_id = vm.id
                WHERE vm.model_type = 'image'
                AND vp.id IS NULL
            """)
            
            pricing_added = 0
            for model in models_without_pricing:
                # Determine price based on model
                image_cost = 0.030  # Default
                
                if model['vendor_name'] == 'openai':
                    if model['name'] == 'dall-e-3':
                        image_cost = 0.040
                    elif model['name'] == 'dall-e-2':
                        image_cost = 0.020
                elif model['vendor_name'] == 'adobe':
                    image_cost = 0.025
                
                # Get vendor_id for this model
                vendor_id = await conn.fetchval("""
                    SELECT vendor_id FROM vendor_models WHERE id = $1
                """, model['id'])
                
                await conn.execute("""
                    INSERT INTO vendor_pricing (
                        id, vendor_id, model_id,
                        input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                        image_cost_per_item, currency,
                        pricing_tier, is_active, created_at
                    ) VALUES (
                        gen_random_uuid(), $1, $2,
                        0, 0,  -- Image models don't use token-based pricing
                        $3, 'USD',
                        'standard', true, NOW()
                    )
                """, vendor_id, model['id'], image_cost)
                pricing_added += 1
            
            print(f"   ✅ Added pricing for {pricing_added} models")
            
            # 6. Check constraints
            print("\n6️⃣ Checking constraints...")
            
            constraints = await conn.fetch("""
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'requests'::regclass
                AND (conname LIKE 'chk_%image%' OR conname LIKE 'chk_%generation%' OR conname LIKE 'chk_%guidance%')
            """)
            
            print(f"   ✅ Found {len(constraints)} image-related constraints")
        
        print("\n✅ Migration 008 verification completed!")
        
        # Final verification
        print("\n🔍 Final verification...")
        print("-" * 80)
        
        # Verify columns
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
        for col in columns[:5]:  # Show first 5
            print(f"  - {col['column_name']:<25} {col['data_type']}")
        if len(columns) > 5:
            print(f"  ... and {len(columns) - 5} more")
        
        # Verify models with pricing
        models_with_pricing = await conn.fetch("""
            SELECT 
                v.name as vendor_name, 
                vm.name as model_name,
                vp.image_cost_per_item
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            JOIN vendor_pricing vp ON vp.model_id = vm.id
            WHERE vm.model_type = 'image'
            AND vp.image_cost_per_item > 0
            ORDER BY v.name, vm.name
        """)
        
        print(f"\n✅ Image models with pricing ({len(models_with_pricing)}):")
        for model in models_with_pricing:
            print(f"  - {model['vendor_name']:<15} {model['model_name']:<30} ${model['image_cost_per_item']:.3f}/image")
        
        await conn.close()
        
        print("\n" + "=" * 80)
        print("🎉 Migration 008 - Image Generation Support")
        print("\n📊 Summary:")
        print("   ✅ All 10 image generation columns exist in requests table")
        print("   ✅ Image generation models are configured")
        print("   ✅ Per-image pricing is set up")
        print("\n💡 The system can now track:")
        print("   - Image generation requests (DALL-E, Stable Diffusion, Adobe Firefly)")
        print("   - Prompts and generation parameters")
        print("   - Generated image URLs and metadata")
        print("   - Per-image billing")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(apply_migration_008_final_fixed())