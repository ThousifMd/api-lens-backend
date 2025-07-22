#!/usr/bin/env python3
"""
Simple script to populate vendor_models table with current AI models
"""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from app.database import DatabaseUtils, db_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Current AI models organized by vendor
MODELS = {
    "OpenAI": [
        # GPT-4 Models
        {"name": "gpt-4o", "model_type": "chat", "context_window": 128000, "supports_vision": True, "supports_functions": True},
        {"name": "gpt-4o-mini", "model_type": "chat", "context_window": 128000, "supports_vision": True, "supports_functions": True},
        {"name": "gpt-4-turbo", "model_type": "chat", "context_window": 128000, "supports_vision": True, "supports_functions": True},
        {"name": "gpt-4", "model_type": "chat", "context_window": 8192, "supports_vision": False, "supports_functions": True},
        {"name": "gpt-3.5-turbo", "model_type": "chat", "context_window": 16385, "supports_vision": False, "supports_functions": True},
        
        # Image Models
        {"name": "dall-e-3", "model_type": "image", "context_window": 0, "supports_vision": False, "supports_functions": False},
        {"name": "dall-e-2", "model_type": "image", "context_window": 0, "supports_vision": False, "supports_functions": False},
        
        # Embedding Models
        {"name": "text-embedding-3-large", "model_type": "embedding", "context_window": 8191, "supports_vision": False, "supports_functions": False},
        {"name": "text-embedding-3-small", "model_type": "embedding", "context_window": 8191, "supports_vision": False, "supports_functions": False},
        {"name": "text-embedding-ada-002", "model_type": "embedding", "context_window": 8191, "supports_vision": False, "supports_functions": False},
        
        # Audio Models
        {"name": "whisper-1", "model_type": "audio", "context_window": 0, "supports_vision": False, "supports_functions": False},
        {"name": "tts-1", "model_type": "audio", "context_window": 0, "supports_vision": False, "supports_functions": False},
        {"name": "tts-1-hd", "model_type": "audio", "context_window": 0, "supports_vision": False, "supports_functions": False},
    ],
    
    "Anthropic": [
        {"name": "claude-3-opus-20240229", "model_type": "chat", "context_window": 200000, "supports_vision": True, "supports_functions": False},
        {"name": "claude-3-sonnet-20240229", "model_type": "chat", "context_window": 200000, "supports_vision": True, "supports_functions": False},
        {"name": "claude-3-haiku-20240307", "model_type": "chat", "context_window": 200000, "supports_vision": True, "supports_functions": False},
        {"name": "claude-3.5-sonnet-20240620", "model_type": "chat", "context_window": 200000, "supports_vision": True, "supports_functions": False},
        {"name": "claude-2.1", "model_type": "chat", "context_window": 200000, "supports_vision": False, "supports_functions": False},
        {"name": "claude-2.0", "model_type": "chat", "context_window": 100000, "supports_vision": False, "supports_functions": False},
    ],
    
    "Google": [
        {"name": "gemini-1.5-pro", "model_type": "chat", "context_window": 1048576, "supports_vision": True, "supports_functions": True},
        {"name": "gemini-1.5-flash", "model_type": "chat", "context_window": 1048576, "supports_vision": True, "supports_functions": True},
        {"name": "gemini-1.0-pro", "model_type": "chat", "context_window": 30720, "supports_vision": False, "supports_functions": True},
    ],
    
    "Cohere": [
        {"name": "command-r-plus", "model_type": "chat", "context_window": 128000, "supports_vision": False, "supports_functions": True},
        {"name": "command-r", "model_type": "chat", "context_window": 128000, "supports_vision": False, "supports_functions": True},
        {"name": "embed-english-v3.0", "model_type": "embedding", "context_window": 512, "supports_vision": False, "supports_functions": False},
        {"name": "embed-multilingual-v3.0", "model_type": "embedding", "context_window": 512, "supports_vision": False, "supports_functions": False},
    ],
    
    "Mistral": [
        {"name": "mistral-large-latest", "model_type": "chat", "context_window": 32000, "supports_vision": False, "supports_functions": True},
        {"name": "mistral-medium-latest", "model_type": "chat", "context_window": 32000, "supports_vision": False, "supports_functions": True},
        {"name": "mistral-small-latest", "model_type": "chat", "context_window": 32000, "supports_vision": False, "supports_functions": True},
        {"name": "mixtral-8x7b-instruct", "model_type": "chat", "context_window": 32000, "supports_vision": False, "supports_functions": False},
    ],
}

async def create_vendor(name: str) -> str:
    """Create vendor and return ID"""
    vendor_id = str(uuid4())
    await DatabaseUtils.execute_query("""
        INSERT INTO vendors (id, name, slug, is_active, is_supported, created_at)
        VALUES ($1, $2, $3, true, true, $4)
    """, [vendor_id, name, name.lower(), datetime.now(timezone.utc)])
    logger.info(f"Created vendor: {name}")
    return vendor_id

async def create_model(vendor_id: str, vendor_name: str, model: dict):
    """Create model entry"""
    model_id = str(uuid4())
    slug = model['name'].lower().replace('.', '-').replace(' ', '-')
    
    await DatabaseUtils.execute_query("""
        INSERT INTO vendor_models (
            id, vendor_id, name, slug, model_type,
            context_window, supports_functions, supports_vision,
            is_active, created_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, true, $9)
    """, [
        model_id,
        vendor_id,
        model['name'],
        slug,
        model['model_type'],
        model['context_window'],
        model.get('supports_functions', False),
        model.get('supports_vision', False),
        datetime.now(timezone.utc)
    ])
    logger.info(f"Created model: {vendor_name}/{model['name']}")

async def populate_models():
    """Populate all models"""
    try:
        await db_manager.initialize()
        
        total_vendors = len(MODELS)
        total_models = sum(len(models) for models in MODELS.values())
        
        logger.info(f"Populating {total_models} models from {total_vendors} vendors")
        
        for vendor_name, models in MODELS.items():
            logger.info(f"\nProcessing {vendor_name}...")
            
            # Create vendor
            vendor_id = await create_vendor(vendor_name)
            
            # Create models
            for model in models:
                await create_model(vendor_id, vendor_name, model)
        
        # Show summary
        result = await DatabaseUtils.execute_query("""
            SELECT v.name, COUNT(vm.id) as model_count
            FROM vendors v
            LEFT JOIN vendor_models vm ON v.id = vm.vendor_id
            GROUP BY v.name
            ORDER BY v.name
        """, fetch_all=True)
        
        print("\n✅ Population complete!")
        print("\nSummary:")
        print("=" * 40)
        for row in result:
            print(f"{row['name']}: {row['model_count']} models")
            
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db_manager.close()

if __name__ == "__main__":
    asyncio.run(populate_models())