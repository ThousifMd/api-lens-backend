#!/usr/bin/env python3
"""Debug why some models don't have pricing"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await db_manager.initialize()
    
    try:
        async with db_manager.pool.acquire() as conn:
            # Check stable-diffusion-1.5
            result = await conn.fetch("""
                SELECT 
                    vm.id as model_id,
                    vm.name as model_name,
                    vp.id as pricing_id,
                    vp.image_cost_per_item,
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens,
                    vp.is_active
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id
                WHERE v.name = 'stability-ai' 
                AND vm.name IN ('stable-diffusion-1.5', 'stable-diffusion-2', 'stable-diffusion-xl')
                ORDER BY vm.name, vp.is_active DESC
            """)
            
            logger.info("Debug pricing records:")
            for row in result:
                logger.info(f"Model: {row['model_name']}, Pricing ID: {row['pricing_id']}, "
                          f"Image Cost: {row['image_cost_per_item']}, "
                          f"Input Cost: {row['input_cost_per_1k_tokens']}, "
                          f"Active: {row['is_active']}")
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())