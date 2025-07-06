#!/usr/bin/env python3
"""Add pricing for gpt-4o model"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await db_manager.initialize()
    
    try:
        async with db_manager.pool.acquire() as conn:
            # Get gpt-4o model ID
            model = await conn.fetchrow("""
                SELECT vm.id, vm.vendor_id, vm.name
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name = 'openai' AND vm.name = 'gpt-4o'
            """)
            
            if not model:
                logger.error("❌ gpt-4o model not found!")
                return
                
            model_id = model['id']
            vendor_id = model['vendor_id']
            
            # Check if pricing already exists
            pricing = await conn.fetchrow("""
                SELECT id FROM vendor_pricing 
                WHERE model_id = $1 AND is_active = true
            """, model_id)
            
            if pricing:
                logger.info("✅ Pricing already exists for gpt-4o")
            else:
                logger.info("Adding pricing for gpt-4o...")
                
                await conn.execute("""
                    INSERT INTO vendor_pricing (
                        vendor_id, model_id,
                        input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                        currency, pricing_tier, effective_date, is_active
                    ) VALUES (
                        $1, $2,
                        0.0025, 0.01,
                        'USD', 'standard', NOW(), true
                    )
                """, vendor_id, model_id)
                
                logger.info("✅ Created pricing for gpt-4o: $0.0025/1K input, $0.01/1K output")
            
            # Verify the setup
            verification = await conn.fetchrow("""
                SELECT 
                    vm.name as model_name,
                    v.name as vendor_name,
                    vm.model_type,
                    vm.context_window,
                    vm.max_output_tokens,
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
                WHERE vm.name = 'gpt-4o'
            """)
            
            if verification:
                logger.info("\n✅ COMPLETE VERIFICATION:")
                logger.info(f"   Model: {verification['model_name']}")
                logger.info(f"   Vendor: {verification['vendor_name']}")
                logger.info(f"   Type: {verification['model_type']}")
                logger.info(f"   Context: {verification['context_window']:,} tokens")
                logger.info(f"   Max Output: {verification['max_output_tokens']:,} tokens")
                logger.info(f"   Input Cost: ${verification['input_cost_per_1k_tokens']:.4f}/1K tokens")
                logger.info(f"   Output Cost: ${verification['output_cost_per_1k_tokens']:.4f}/1K tokens")
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())