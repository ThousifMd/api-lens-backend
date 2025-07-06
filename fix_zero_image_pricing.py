#!/usr/bin/env python3
"""Fix zero image pricing for Stability AI models"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await db_manager.initialize()
    
    try:
        async with db_manager.pool.acquire() as conn:
            # Update Stability AI models with proper image pricing
            models_to_fix = [
                ('stable-diffusion-1.5', 0.002),
                ('stable-diffusion-2', 0.002),
                ('stable-diffusion-xl', 0.002),
            ]
            
            for model_name, per_step_cost in models_to_fix:
                # Calculate total cost (per step * 30 steps)
                total_cost = per_step_cost * 30
                
                result = await conn.execute("""
                    UPDATE vendor_pricing
                    SET image_cost_per_item = $2,
                        input_cost_per_1k_tokens = 0,
                        output_cost_per_1k_tokens = 0
                    WHERE model_id IN (
                        SELECT vm.id 
                        FROM vendor_models vm
                        JOIN vendors v ON vm.vendor_id = v.id
                        WHERE v.name = 'stability-ai' AND vm.name = $1
                    )
                    AND is_active = true
                    RETURNING id
                """, model_name, total_cost)
                
                logger.info(f"✅ Updated {model_name} to ${total_cost:.3f} per image")
            
            # Verify all image model pricing
            logger.info("\n📊 VERIFIED IMAGE MODEL PRICING:")
            models = await conn.fetch("""
                SELECT 
                    v.name as vendor_name,
                    vm.name as model_name,
                    vp.image_cost_per_item,
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
                WHERE vm.model_type = 'image'
                ORDER BY v.name, vm.name
            """)
            
            logger.info(f"{'Vendor':<15} | {'Model':<35} | {'Per Image':<10} | {'Status'}")
            logger.info("-" * 75)
            
            for model in models:
                if model['image_cost_per_item'] and model['image_cost_per_item'] > 0:
                    price = f"${model['image_cost_per_item']:.3f}"
                    status = "✅"
                else:
                    price = "NO PRICE"
                    status = "❌"
                
                logger.info(f"{model['vendor_name']:<15} | {model['model_name']:<35} | {price:<10} | {status}")
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())