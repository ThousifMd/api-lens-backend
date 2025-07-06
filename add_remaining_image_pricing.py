#!/usr/bin/env python3
"""Add pricing for remaining image models"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Remaining models that need pricing
REMAINING_PRICING = [
    ('stability-ai', 'stable-diffusion-1.5', 0.002),  # Legacy model, cheaper
    ('stability-ai', 'stable-diffusion-2', 0.002),    # Legacy model, cheaper
    ('stability-ai', 'stable-diffusion-xl', 0.002),   # Per step, ~30 steps = $0.06
    ('adobe', 'firefly-v1', 0.025),                   # Assuming v1 exists
]

async def main():
    await db_manager.initialize()
    
    try:
        logger.info("🔧 Adding pricing for remaining image models...")
        
        async with db_manager.pool.acquire() as conn:
            for vendor_name, model_name, cost_per_image in REMAINING_PRICING:
                # Get model info
                model_info = await conn.fetchrow("""
                    SELECT vm.id as model_id, vm.vendor_id
                    FROM vendor_models vm
                    JOIN vendors v ON vm.vendor_id = v.id
                    WHERE v.name = $1 AND vm.name = $2
                """, vendor_name, model_name)
                
                if not model_info:
                    logger.warning(f"⚠️  Model not found: {vendor_name}/{model_name}")
                    continue
                
                # Check if pricing exists
                existing = await conn.fetchrow("""
                    SELECT id FROM vendor_pricing
                    WHERE model_id = $1 AND is_active = true
                """, model_info['model_id'])
                
                if not existing:
                    # For Stability AI, calculate base cost (per step * default steps)
                    if vendor_name == 'stability-ai':
                        base_cost = cost_per_image * 30  # 30 steps default
                    else:
                        base_cost = cost_per_image
                    
                    await conn.execute("""
                        INSERT INTO vendor_pricing (
                            vendor_id, model_id,
                            input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                            image_cost_per_item,
                            currency, pricing_tier, effective_date, is_active
                        ) VALUES (
                            $1, $2,
                            0, 0,
                            $3,
                            'USD', 'standard', NOW(), true
                        )
                    """, model_info['vendor_id'], model_info['model_id'], base_cost)
                    
                    logger.info(f"✅ Added pricing for {vendor_name}/{model_name}: ${base_cost:.3f} per image")
                else:
                    logger.info(f"✅ Pricing already exists for {vendor_name}/{model_name}")
            
            # Final verification
            logger.info("\n📊 FINAL IMAGE MODEL PRICING:")
            models = await conn.fetch("""
                SELECT 
                    v.name as vendor_name,
                    vm.name as model_name,
                    vp.image_cost_per_item
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
                WHERE vm.model_type = 'image'
                ORDER BY v.name, vm.name
            """)
            
            for model in models:
                price = f"${model['image_cost_per_item']:.3f}" if model['image_cost_per_item'] else "NO PRICE"
                logger.info(f"  {model['vendor_name']:<15} | {model['model_name']:<35} | {price}")
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())