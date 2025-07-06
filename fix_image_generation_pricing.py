#!/usr/bin/env python3
"""Fix image generation pricing for DALL-E and other image models"""
import asyncio
from app.database import db_manager
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Image generation pricing data
IMAGE_PRICING_DATA = [
    # OpenAI DALL-E models
    {
        "vendor": "openai",
        "model": "dall-e-3",
        "image_cost": 0.040,  # Standard quality 1024x1024
        "hd_multiplier": 2.0,  # HD quality costs 2x
        "size_multipliers": {
            "1024x1024": 1.0,
            "1024x1792": 2.0,
            "1792x1024": 2.0
        }
    },
    {
        "vendor": "openai",
        "model": "dall-e-2",
        "image_cost": 0.020,  # 1024x1024
        "size_multipliers": {
            "256x256": 0.325,   # $0.016
            "512x512": 0.45,    # $0.018
            "1024x1024": 1.0    # $0.020
        }
    },
    # Stability AI models
    {
        "vendor": "stability-ai",
        "model": "stable-diffusion-xl-1024-v1-0",
        "image_cost": 0.002,  # Per step pricing - 30 steps default
        "steps_default": 30,
        "base_cost": 0.06  # $0.002 * 30 steps
    },
    {
        "vendor": "stability-ai",
        "model": "stable-diffusion-v1-6",
        "image_cost": 0.002,
        "steps_default": 30,
        "base_cost": 0.06
    },
    # Adobe Firefly models
    {
        "vendor": "adobe",
        "model": "firefly-v2",
        "image_cost": 0.065  # Premium tier
    },
    {
        "vendor": "adobe",
        "model": "firefly-v1",
        "image_cost": 0.025  # Standard tier
    }
]

async def update_image_pricing():
    """Update image generation pricing in the database"""
    
    for pricing_data in IMAGE_PRICING_DATA:
        vendor_name = pricing_data["vendor"]
        model_name = pricing_data["model"]
        base_cost = pricing_data.get("base_cost", pricing_data["image_cost"])
        
        async with db_manager.pool.acquire() as conn:
            # Get vendor and model IDs
            model_info = await conn.fetchrow("""
                SELECT vm.id as model_id, vm.vendor_id, v.name as vendor_name
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name = $1 AND vm.name = $2
            """, vendor_name, model_name)
            
            if not model_info:
                logger.warning(f"Model not found: {vendor_name}/{model_name}")
                continue
            
            model_id = model_info['model_id']
            vendor_id = model_info['vendor_id']
            
            # Check if pricing exists
            existing_pricing = await conn.fetchrow("""
                SELECT id, image_cost_per_item 
                FROM vendor_pricing 
                WHERE model_id = $1 AND is_active = true
            """, model_id)
            
            if existing_pricing:
                # Update existing pricing
                await conn.execute("""
                    UPDATE vendor_pricing
                    SET image_cost_per_item = $2
                    WHERE id = $1
                """, existing_pricing['id'], base_cost)
                
                logger.info(f"✅ Updated pricing for {vendor_name}/{model_name}: ${base_cost} per image")
            else:
                # Insert new pricing
                await conn.execute("""
                    INSERT INTO vendor_pricing (
                        vendor_id, model_id,
                        input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                        image_cost_per_item,
                        currency, pricing_tier, effective_date, is_active
                    ) VALUES (
                        $1, $2,
                        0, 0,  -- Image models don't use token pricing
                        $3,
                        'USD', 'standard', NOW(), true
                    )
                """, vendor_id, model_id, base_cost)
                
                logger.info(f"✅ Created pricing for {vendor_name}/{model_name}: ${base_cost} per image")

async def verify_image_pricing():
    """Verify all image model pricing"""
    
    async with db_manager.pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT 
                v.name as vendor_name,
                vm.name as model_name,
                vm.model_type,
                vp.image_cost_per_item,
                vp.currency,
                vp.pricing_tier
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
            WHERE vm.model_type = 'image'
            ORDER BY v.name, vm.name
        """)
        
        logger.info("\n🖼️  IMAGE MODEL PRICING SUMMARY:")
        logger.info("=" * 60)
        
        for row in results:
            price = row['image_cost_per_item']
            price_str = f"${price:.3f}" if price else "NOT SET"
            logger.info(
                f"{row['vendor_name']:<15} | {row['model_name']:<30} | {price_str:<10}"
            )

async def add_size_based_pricing_metadata():
    """Add size and quality multipliers as metadata"""
    
    async with db_manager.pool.acquire() as conn:
        # Add metadata for DALL-E 3
        await conn.execute("""
            UPDATE vendor_models
            SET capabilities = jsonb_build_object(
                'quality_options', '["standard", "hd"]',
                'size_options', '["1024x1024", "1024x1792", "1792x1024"]',
                'quality_multipliers', '{"standard": 1.0, "hd": 2.0}',
                'size_multipliers', '{"1024x1024": 1.0, "1024x1792": 2.0, "1792x1024": 2.0}'
            )
            WHERE name = 'dall-e-3'
        """)
        
        # Add metadata for DALL-E 2
        await conn.execute("""
            UPDATE vendor_models
            SET capabilities = jsonb_build_object(
                'size_options', '["256x256", "512x512", "1024x1024"]',
                'size_multipliers', '{"256x256": 0.8, "512x512": 0.9, "1024x1024": 1.0}'
            )
            WHERE name = 'dall-e-2'
        """)
        
        logger.info("✅ Added size and quality metadata for DALL-E models")

async def main():
    await db_manager.initialize()
    
    try:
        logger.info("🔧 Fixing image generation pricing...")
        
        # Update pricing
        await update_image_pricing()
        
        # Add metadata
        await add_size_based_pricing_metadata()
        
        # Verify results
        await verify_image_pricing()
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())