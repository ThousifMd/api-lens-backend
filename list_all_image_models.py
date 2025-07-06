#!/usr/bin/env python3
"""List all image models in the database"""
import asyncio
from app.database import db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    await db_manager.initialize()
    
    try:
        async with db_manager.pool.acquire() as conn:
            # Get all models (not just image type)
            models = await conn.fetch("""
                SELECT 
                    v.name as vendor_name,
                    vm.name as model_name,
                    vm.model_type
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name IN ('openai', 'stability-ai', 'adobe')
                ORDER BY v.name, vm.model_type, vm.name
            """)
            
            logger.info("\n📊 MODELS BY VENDOR:")
            current_vendor = None
            
            for model in models:
                if model['vendor_name'] != current_vendor:
                    current_vendor = model['vendor_name']
                    logger.info(f"\n{current_vendor.upper()}:")
                
                logger.info(f"  - {model['model_name']} ({model['model_type']})")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(main())