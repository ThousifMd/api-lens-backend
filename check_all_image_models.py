#!/usr/bin/env python3
"""Check all image models and their pricing"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await db_manager.initialize()
    
    try:
        async with db_manager.pool.acquire() as conn:
            # Get all image models
            models = await conn.fetch("""
                SELECT 
                    v.name as vendor_name,
                    vm.id as model_id,
                    vm.name as model_name,
                    vm.display_name,
                    vm.model_type,
                    vm.is_active,
                    vp.id as pricing_id,
                    vp.image_cost_per_item,
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
                WHERE vm.model_type = 'image'
                ORDER BY v.name, vm.name
            """)
            
            logger.info("\n📊 ALL IMAGE MODELS:")
            logger.info("=" * 100)
            logger.info(f"{'Vendor':<15} | {'Model Name':<30} | {'Display Name':<25} | {'Active':<8} | {'Pricing':<12}")
            logger.info("-" * 100)
            
            for model in models:
                active = "Yes" if model['is_active'] else "No"
                if model['pricing_id']:
                    price = f"${model['image_cost_per_item']:.3f}/img" if model['image_cost_per_item'] else "Token-based"
                else:
                    price = "NO PRICING"
                
                logger.info(
                    f"{model['vendor_name']:<15} | "
                    f"{model['model_name']:<30} | "
                    f"{model['display_name'] or 'N/A':<25} | "
                    f"{active:<8} | "
                    f"{price:<12}"
                )
            
            # Summary
            total_models = len(models)
            models_with_pricing = sum(1 for m in models if m['pricing_id'])
            logger.info("-" * 100)
            logger.info(f"Total image models: {total_models}")
            logger.info(f"Models with pricing: {models_with_pricing}")
            logger.info(f"Models without pricing: {total_models - models_with_pricing}")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())