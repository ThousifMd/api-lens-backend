#!/usr/bin/env python3
"""Fix model types for image generation models"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Models that should be 'image' type
IMAGE_MODELS = [
    ('openai', 'dall-e-2'),
    ('openai', 'dall-e-3'),
    ('adobe', 'firefly-v2'),
    ('adobe', 'firefly-v1'),
    ('stability-ai', 'stable-diffusion-v1-6'),
    ('stability-ai', 'stable-diffusion-xl-1024-v1-0'),
]

async def main():
    await db_manager.initialize()
    
    try:
        logger.info("🔧 Fixing model types for image generation models...")
        
        async with db_manager.pool.acquire() as conn:
            for vendor_name, model_name in IMAGE_MODELS:
                # Update model type to 'image'
                result = await conn.execute("""
                    UPDATE vendor_models
                    SET model_type = 'image'
                    WHERE vendor_id = (SELECT id FROM vendors WHERE name = $1)
                    AND name = $2
                    RETURNING id, name
                """, vendor_name, model_name)
                
                if result:
                    logger.info(f"✅ Updated {vendor_name}/{model_name} to image type")
                else:
                    logger.warning(f"⚠️  Model not found: {vendor_name}/{model_name}")
            
            # Verify the changes
            logger.info("\n📊 VERIFIED IMAGE MODELS:")
            image_models = await conn.fetch("""
                SELECT 
                    v.name as vendor_name,
                    vm.name as model_name,
                    vm.model_type,
                    vp.image_cost_per_item
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
                WHERE vm.model_type = 'image'
                ORDER BY v.name, vm.name
            """)
            
            for model in image_models:
                price = f"${model['image_cost_per_item']:.3f}" if model['image_cost_per_item'] else "NO PRICE"
                logger.info(f"  {model['vendor_name']}/{model['model_name']} - {price}")
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())