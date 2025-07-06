#!/usr/bin/env python3
"""Add gpt-4o model to vendor_models table with correct schema"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await db_manager.initialize()
    
    try:
        logger.info("🔧 Adding gpt-4o model...")
        
        # Check if gpt-4o model exists
        async with db_manager.pool.acquire() as conn:
            existing_model = await conn.fetchrow("""
                SELECT vm.id, vm.name, v.name as vendor_name
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name = 'openai' AND vm.name = 'gpt-4o'
            """)
            
            if existing_model:
                logger.info(f"✅ gpt-4o model already exists with ID: {existing_model['id']}")
                model_id = existing_model['id']
            else:
                logger.info("Adding gpt-4o model...")
                
                # Get OpenAI vendor ID
                vendor = await conn.fetchrow("""
                    SELECT id FROM vendors WHERE name = 'openai'
                """)
                
                if not vendor:
                    logger.error("❌ OpenAI vendor not found!")
                    return
                
                vendor_id = vendor['id']
                
                # Insert gpt-4o model
                model = await conn.fetchrow("""
                    INSERT INTO vendor_models (
                        vendor_id, name, display_name, description, model_type,
                        context_window, max_output_tokens, supports_functions, supports_vision, is_active
                    ) VALUES (
                        $1, 'gpt-4o', 'GPT-4o', 'Most capable and cost-effective GPT-4 model', 'chat',
                        128000, 4096, true, true, true
                    ) RETURNING id
                """, vendor_id)
                
                model_id = model['id']
                logger.info(f"✅ Created gpt-4o model with ID: {model_id}")
            
            # Check if pricing exists
            pricing = await conn.fetchrow("""
                SELECT id FROM vendor_pricing 
                WHERE model_id = $1 AND is_active = true
            """, model_id)
            
            if not pricing:
                logger.info("Adding pricing for gpt-4o...")
                
                # Get vendor_id for pricing
                vendor_id = await conn.fetchval("""
                    SELECT vendor_id FROM vendor_models WHERE id = $1
                """, model_id)
                
                await conn.execute("""
                    INSERT INTO vendor_pricing (
                        vendor_id, model_id, model_type,
                        input_cost_per_1k_tokens, output_cost_per_1k_tokens,
                        currency, pricing_tier, effective_date, is_active
                    ) VALUES (
                        $1, $2, 'chat',
                        0.0025, 0.01,
                        'USD', 'standard', NOW(), true
                    )
                """, vendor_id, model_id)
                
                logger.info("✅ Created pricing for gpt-4o: $0.0025/1K input, $0.01/1K output")
            else:
                logger.info("✅ Pricing already exists for gpt-4o")
            
            # Verify the setup
            verification = await conn.fetchrow("""
                SELECT 
                    vm.name as model_name,
                    v.name as vendor_name,
                    vm.model_type,
                    vm.context_window,
                    vm.max_output_tokens,
                    vm.supports_functions,
                    vm.supports_vision,
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                LEFT JOIN vendor_pricing vp ON vm.id = vp.model_id AND vp.is_active = true
                WHERE vm.name = 'gpt-4o'
            """)
            
            if verification:
                logger.info("\n✅ VERIFICATION SUCCESSFUL:")
                logger.info(f"   Model: {verification['model_name']}")
                logger.info(f"   Vendor: {verification['vendor_name']}")
                logger.info(f"   Type: {verification['model_type']}")
                logger.info(f"   Context: {verification['context_window']:,} tokens")
                logger.info(f"   Max Output: {verification['max_output_tokens']:,} tokens")
                logger.info(f"   Supports Functions: {verification['supports_functions']}")
                logger.info(f"   Supports Vision: {verification['supports_vision']}")
                logger.info(f"   Input Cost: ${verification['input_cost_per_1k_tokens']:.4f}/1K tokens")
                logger.info(f"   Output Cost: ${verification['output_cost_per_1k_tokens']:.4f}/1K tokens")
            else:
                logger.error("❌ Verification failed - model not found")
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())