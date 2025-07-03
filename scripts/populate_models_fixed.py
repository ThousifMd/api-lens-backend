#!/usr/bin/env python3
"""
Populate all active models from OpenAI, Google, and Anthropic
Fixed version matching actual database schema
"""
import asyncio
import sys
from datetime import datetime
sys.path.insert(0, '/Users/thousifudayagiri/Desktop/api-lens-backend')

# Comprehensive model definitions
VENDOR_MODELS = {
    "openai": {
        "display_name": "OpenAI",
        "description": "OpenAI API models including GPT, DALL-E, and Whisper",
        "models": [
            # GPT-4 Models
            {
                "name": "gpt-4o",
                "display_name": "GPT-4o",
                "description": "Most advanced GPT-4 model with improved reasoning and multimodal capabilities",
                "model_type": "chat",
                "context_window": 128000,
                "max_output_tokens": 16384,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "gpt-4o-mini",
                "display_name": "GPT-4o Mini",
                "description": "Faster, more cost-effective version of GPT-4o",
                "model_type": "chat",
                "context_window": 128000,
                "max_output_tokens": 16384,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "gpt-4-turbo",
                "display_name": "GPT-4 Turbo",
                "description": "Latest GPT-4 Turbo model with improved performance",
                "model_type": "chat",
                "context_window": 128000,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "gpt-4",
                "display_name": "GPT-4",
                "description": "Standard GPT-4 model with 8K context",
                "model_type": "chat",
                "context_window": 8192,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "gpt-4-32k",
                "display_name": "GPT-4 32K",
                "description": "GPT-4 model with extended 32K context window",
                "model_type": "chat",
                "context_window": 32768,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": False,
                "is_active": True
            },
            
            # GPT-3.5 Models
            {
                "name": "gpt-3.5-turbo",
                "display_name": "GPT-3.5 Turbo",
                "description": "Most capable GPT-3.5 model with function calling",
                "model_type": "chat",
                "context_window": 16384,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "gpt-3.5-turbo-instruct",
                "display_name": "GPT-3.5 Turbo Instruct",
                "description": "Instruction-following model based on GPT-3.5",
                "model_type": "completion",
                "context_window": 4096,
                "max_output_tokens": 4096,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            
            # DALL-E Models
            {
                "name": "dall-e-3",
                "display_name": "DALL-E 3",
                "description": "Latest image generation model with improved quality and safety",
                "model_type": "image",
                "context_window": None,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "dall-e-2",
                "display_name": "DALL-E 2",
                "description": "Previous generation image generation model",
                "model_type": "image",
                "context_window": None,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            
            # Whisper Models
            {
                "name": "whisper-1",
                "display_name": "Whisper",
                "description": "Automatic speech recognition model",
                "model_type": "audio",
                "context_window": None,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            
            # Text-to-Speech Models
            {
                "name": "tts-1",
                "display_name": "TTS-1",
                "description": "Standard text-to-speech model",
                "model_type": "audio",
                "context_window": 4096,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "tts-1-hd",
                "display_name": "TTS-1 HD",
                "description": "High-quality text-to-speech model",
                "model_type": "audio",
                "context_window": 4096,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            
            # Embeddings Models
            {
                "name": "text-embedding-3-large",
                "display_name": "Text Embedding 3 Large",
                "description": "Latest large embedding model with 3072 dimensions",
                "model_type": "embedding",
                "context_window": 8191,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "text-embedding-3-small",
                "display_name": "Text Embedding 3 Small",
                "description": "Latest small embedding model with 1536 dimensions",
                "model_type": "embedding",
                "context_window": 8191,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "text-embedding-ada-002",
                "display_name": "Text Embedding Ada 002",
                "description": "Previous generation embedding model",
                "model_type": "embedding",
                "context_window": 8191,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            }
        ]
    },
    
    "anthropic": {
        "display_name": "Anthropic",
        "description": "Anthropic's Claude models for conversation and analysis",
        "models": [
            # Claude 3.5 Models
            {
                "name": "claude-3-5-sonnet-20241022",
                "display_name": "Claude 3.5 Sonnet",
                "description": "Most intelligent model with superior performance on complex tasks",
                "model_type": "chat",
                "context_window": 200000,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "claude-3-5-haiku-20241022",
                "display_name": "Claude 3.5 Haiku",
                "description": "Fastest model for real-time applications",
                "model_type": "chat",
                "context_window": 200000,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            
            # Claude 3 Models
            {
                "name": "claude-3-opus-20240229",
                "display_name": "Claude 3 Opus",
                "description": "Most powerful model for highly complex tasks",
                "model_type": "chat",
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "claude-3-sonnet-20240229",
                "display_name": "Claude 3 Sonnet",
                "description": "Balanced model for enterprise workloads",
                "model_type": "chat",
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "claude-3-haiku-20240307",
                "display_name": "Claude 3 Haiku",
                "description": "Fastest and most compact model",
                "model_type": "chat",
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            
            # Claude 2 Models (Legacy)
            {
                "name": "claude-2.1",
                "display_name": "Claude 2.1",
                "description": "Previous generation Claude model with large context",
                "model_type": "chat",
                "context_window": 200000,
                "max_output_tokens": 4096,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": False
            },
            {
                "name": "claude-2.0",
                "display_name": "Claude 2.0",
                "description": "Legacy Claude 2.0 model",
                "model_type": "chat",
                "context_window": 100000,
                "max_output_tokens": 4096,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": False
            },
            
            # Claude Instant (Legacy)
            {
                "name": "claude-instant-1.2",
                "display_name": "Claude Instant 1.2",
                "description": "Legacy faster model for simple tasks",
                "model_type": "chat",
                "context_window": 100000,
                "max_output_tokens": 4096,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": False
            }
        ]
    },
    
    "google": {
        "display_name": "Google",
        "description": "Google's Gemini and PaLM models",
        "models": [
            # Gemini 2.0 Models (Latest)
            {
                "name": "gemini-2.0-flash-exp",
                "display_name": "Gemini 2.0 Flash Experimental",
                "description": "Experimental next-generation Gemini model",
                "model_type": "chat",
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            
            # Gemini 1.5 Models
            {
                "name": "gemini-1.5-pro",
                "display_name": "Gemini 1.5 Pro",
                "description": "Most capable Gemini model with 2M token context",
                "model_type": "chat",
                "context_window": 2097152,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "gemini-1.5-flash",
                "display_name": "Gemini 1.5 Flash",
                "description": "Fast and versatile model for diverse tasks",
                "model_type": "chat",
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            {
                "name": "gemini-1.5-flash-8b",
                "display_name": "Gemini 1.5 Flash 8B",
                "description": "High-volume, lower-intelligence tasks",
                "model_type": "chat",
                "context_window": 1048576,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": True,
                "is_active": True
            },
            
            # Gemini 1.0 Models
            {
                "name": "gemini-1.0-pro",
                "display_name": "Gemini 1.0 Pro",
                "description": "Balanced model for text tasks",
                "model_type": "chat",
                "context_window": 32768,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "gemini-1.0-pro-vision",
                "display_name": "Gemini 1.0 Pro Vision",
                "description": "Multimodal model with vision capabilities",
                "model_type": "chat",
                "context_window": 16384,
                "max_output_tokens": 8192,
                "supports_functions": False,
                "supports_vision": True,
                "is_active": True
            },
            
            # Legacy Gemini Pro
            {
                "name": "gemini-pro",
                "display_name": "Gemini Pro (Legacy)",
                "description": "Legacy Gemini Pro model",
                "model_type": "chat",
                "context_window": 32768,
                "max_output_tokens": 8192,
                "supports_functions": True,
                "supports_vision": False,
                "is_active": False
            },
            {
                "name": "gemini-pro-vision",
                "display_name": "Gemini Pro Vision (Legacy)",
                "description": "Legacy Gemini Pro Vision model",
                "model_type": "chat",
                "context_window": 16384,
                "max_output_tokens": 8192,
                "supports_functions": False,
                "supports_vision": True,
                "is_active": False
            },
            
            # Text Embeddings
            {
                "name": "text-embedding-004",
                "display_name": "Text Embedding 004",
                "description": "Latest text embedding model",
                "model_type": "embedding",
                "context_window": 2048,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            },
            {
                "name": "text-embedding-gecko-001",
                "display_name": "Text Embedding Gecko 001",
                "description": "Lightweight embedding model",
                "model_type": "embedding",
                "context_window": 2048,
                "max_output_tokens": None,
                "supports_functions": False,
                "supports_vision": False,
                "is_active": True
            }
        ]
    }
}

async def populate_all_models():
    from app.database import init_database, close_database, DatabaseUtils
    from uuid import uuid4
    
    try:
        await init_database()
        print("🚀 Starting comprehensive model population...")
        
        total_added = 0
        total_updated = 0
        
        for vendor_name, vendor_data in VENDOR_MODELS.items():
            print(f"\n📁 Processing {vendor_data['display_name']} ({vendor_name})...")
            
            # Get or update vendor
            vendor_query = """
                INSERT INTO vendors (id, name, display_name, description, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, true, NOW(), NOW())
                ON CONFLICT (name) 
                DO UPDATE SET 
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    updated_at = NOW()
                RETURNING id
            """
            
            vendor_result = await DatabaseUtils.execute_query(
                vendor_query,
                [uuid4(), vendor_name, vendor_data['display_name'], vendor_data['description']],
                fetch_all=False
            )
            
            vendor_id = vendor_result['id']
            print(f"  ✅ Vendor {vendor_data['display_name']} ready (ID: {vendor_id})")
            
            # Process models
            for model_data in vendor_data['models']:
                try:
                    # Insert or update model with correct schema
                    model_query = """
                        INSERT INTO vendor_models (
                            id, vendor_id, name, display_name, description, model_type,
                            context_window, max_output_tokens, supports_functions,
                            supports_vision, is_active, created_at, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())
                        ON CONFLICT (vendor_id, name)
                        DO UPDATE SET
                            display_name = EXCLUDED.display_name,
                            description = EXCLUDED.description,
                            model_type = EXCLUDED.model_type,
                            context_window = EXCLUDED.context_window,
                            max_output_tokens = EXCLUDED.max_output_tokens,
                            supports_functions = EXCLUDED.supports_functions,
                            supports_vision = EXCLUDED.supports_vision,
                            is_active = EXCLUDED.is_active,
                            updated_at = NOW()
                        RETURNING id, (xmax = 0) as inserted
                    """
                    
                    model_result = await DatabaseUtils.execute_query(
                        model_query,
                        [
                            uuid4(),                                      # id
                            vendor_id,                                   # vendor_id
                            model_data['name'],                          # name
                            model_data['display_name'],                  # display_name
                            model_data['description'],                   # description
                            model_data['model_type'],                    # model_type
                            model_data.get('context_window'),           # context_window
                            model_data.get('max_output_tokens'),        # max_output_tokens
                            model_data.get('supports_functions', False), # supports_functions
                            model_data.get('supports_vision', False),   # supports_vision
                            model_data['is_active']                      # is_active
                        ],
                        fetch_all=False
                    )
                    
                    if model_result['inserted']:
                        total_added += 1
                        print(f"    ➕ Added: {model_data['name']} ({model_data['model_type']})")
                    else:
                        total_updated += 1
                        print(f"    🔄 Updated: {model_data['name']} ({model_data['model_type']})")
                        
                except Exception as e:
                    print(f"    ❌ Error with {model_data['name']}: {str(e)}")
        
        print(f"\n✅ Model population completed!")
        print(f"   📊 Added: {total_added} new models")
        print(f"   🔄 Updated: {total_updated} existing models")
        print(f"   📈 Total processed: {total_added + total_updated} models")
        
        # Show final summary
        summary_query = """
            SELECT 
                v.name as vendor, 
                COUNT(*) as total_models,
                COUNT(*) FILTER (WHERE vm.is_active = true) as active_models,
                COUNT(*) FILTER (WHERE vm.model_type = 'chat') as chat_models,
                COUNT(*) FILTER (WHERE vm.model_type = 'completion') as completion_models,
                COUNT(*) FILTER (WHERE vm.model_type = 'image') as image_models,
                COUNT(*) FILTER (WHERE vm.model_type = 'audio') as audio_models,
                COUNT(*) FILTER (WHERE vm.model_type = 'embedding') as embedding_models
            FROM vendor_models vm 
            JOIN vendors v ON vm.vendor_id = v.id 
            GROUP BY v.name 
            ORDER BY v.name
        """
        
        summary = await DatabaseUtils.execute_query(summary_query, [], fetch_all=True)
        
        print(f"\n📊 Final Model Summary:")
        for row in summary:
            print(f"  {row['vendor'].upper()}:")
            print(f"    Total: {row['total_models']} | Active: {row['active_models']}")
            print(f"    Chat: {row['chat_models']} | Completion: {row['completion_models']} | Embeddings: {row['embedding_models']}")
            if row['image_models'] > 0 or row['audio_models'] > 0:
                print(f"    Images: {row['image_models']} | Audio: {row['audio_models']}")
        
        # List all active chat models
        active_models_query = """
            SELECT v.name as vendor, vm.name as model_name, vm.display_name, vm.context_window
            FROM vendor_models vm 
            JOIN vendors v ON vm.vendor_id = v.id 
            WHERE vm.is_active = true AND vm.model_type = 'chat'
            ORDER BY v.name, vm.name
        """
        
        active_models = await DatabaseUtils.execute_query(active_models_query, [], fetch_all=True)
        
        print(f"\n🎯 Active Chat Models ({len(active_models)} total):")
        current_vendor = None
        for model in active_models:
            if model['vendor'] != current_vendor:
                current_vendor = model['vendor']
                print(f"\n  {current_vendor.upper()}:")
            context = f"{model['context_window']:,}" if model['context_window'] else "N/A"
            print(f"    • {model['model_name']} - {model['display_name']} (context: {context})")
        
    except Exception as e:
        print(f"❌ Error during model population: {str(e)}")
        import traceback
        print(traceback.format_exc())
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(populate_all_models())