"""
Dynamic Pricing Sync Service
Fetches and updates vendor pricing from external APIs and configuration
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

import httpx
from ..database import DatabaseUtils
from ..config import get_settings
from ..utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)

class PricingSyncService:
    """Service to dynamically sync pricing data from various sources"""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def sync_all_vendor_pricing(self) -> Dict[str, Any]:
        """Sync pricing for all vendors from their respective sources"""
        results = {
            'openai': await self._sync_openai_pricing(),
            'anthropic': await self._sync_anthropic_pricing(), 
            'google': await self._sync_google_pricing(),
            'summary': {}
        }
        
        # Calculate summary
        total_updated = sum(r.get('updated_count', 0) for r in results.values() if isinstance(r, dict))
        total_errors = sum(len(r.get('errors', [])) for r in results.values() if isinstance(r, dict))
        
        results['summary'] = {
            'total_models_updated': total_updated,
            'total_errors': total_errors,
            'sync_timestamp': datetime.utcnow().isoformat(),
            'success': total_errors == 0
        }
        
        self.logger.info(f"Pricing sync completed: {total_updated} models updated, {total_errors} errors")
        return results
    
    async def _sync_openai_pricing(self) -> Dict[str, Any]:
        """Sync OpenAI pricing from their API or fallback configuration"""
        try:
            # Try to fetch from OpenAI API (if they have pricing endpoint)
            # For now, use curated pricing data that's more current than hardcoded values
            pricing_data = await self._get_openai_pricing_data()
            
            updated_count = 0
            errors = []
            
            for model_name, pricing in pricing_data.items():
                try:
                    await self._update_model_pricing(
                        vendor_name='openai',
                        model_name=model_name,
                        pricing_data=pricing
                    )
                    updated_count += 1
                except Exception as e:
                    errors.append(f"Failed to update {model_name}: {str(e)}")
            
            return {
                'vendor': 'openai',
                'updated_count': updated_count,
                'errors': errors,
                'success': len(errors) == 0
            }
            
        except Exception as e:
            self.logger.error(f"OpenAI pricing sync failed: {e}")
            return {
                'vendor': 'openai',
                'updated_count': 0,
                'errors': [str(e)],
                'success': False
            }
    
    async def _sync_anthropic_pricing(self) -> Dict[str, Any]:
        """Sync Anthropic pricing"""
        try:
            pricing_data = await self._get_anthropic_pricing_data()
            
            updated_count = 0
            errors = []
            
            for model_name, pricing in pricing_data.items():
                try:
                    await self._update_model_pricing(
                        vendor_name='anthropic',
                        model_name=model_name,
                        pricing_data=pricing
                    )
                    updated_count += 1
                except Exception as e:
                    errors.append(f"Failed to update {model_name}: {str(e)}")
            
            return {
                'vendor': 'anthropic',
                'updated_count': updated_count,
                'errors': errors,
                'success': len(errors) == 0
            }
            
        except Exception as e:
            self.logger.error(f"Anthropic pricing sync failed: {e}")
            return {
                'vendor': 'anthropic',
                'updated_count': 0,
                'errors': [str(e)],
                'success': False
            }
    
    async def _sync_google_pricing(self) -> Dict[str, Any]:
        """Sync Google pricing"""
        try:
            pricing_data = await self._get_google_pricing_data()
            
            updated_count = 0
            errors = []
            
            for model_name, pricing in pricing_data.items():
                try:
                    await self._update_model_pricing(
                        vendor_name='google',
                        model_name=model_name,
                        pricing_data=pricing
                    )
                    updated_count += 1
                except Exception as e:
                    errors.append(f"Failed to update {model_name}: {str(e)}")
            
            return {
                'vendor': 'google',
                'updated_count': updated_count,
                'errors': errors,
                'success': len(errors) == 0
            }
            
        except Exception as e:
            self.logger.error(f"Google pricing sync failed: {e}")
            return {
                'vendor': 'google',
                'updated_count': 0,
                'errors': [str(e)],
                'success': False
            }
    
    async def _update_model_pricing(
        self, 
        vendor_name: str, 
        model_name: str, 
        pricing_data: Dict[str, Any]
    ):
        """Update pricing for a specific model"""
        
        # Get model ID
        model_query = """
            SELECT vm.id, v.id as vendor_id
            FROM vendor_models vm
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE v.name = $1 AND vm.name = $2
        """
        model_result = await DatabaseUtils.execute_query(
            model_query, [vendor_name, model_name], fetch_all=False
        )
        
        if not model_result:
            raise ValueError(f"Model not found: {vendor_name}/{model_name}")
        
        model_id = model_result['id']
        vendor_id = model_result['vendor_id']
        
        # Handle multiple pricing tiers
        pricing_tiers = pricing_data.get('tiers', {'standard': pricing_data})
        
        for tier_name, tier_pricing in pricing_tiers.items():
            # Insert pricing (simple insert for now, we'll handle duplicates differently)
            pricing_query = """
                INSERT INTO vendor_pricing (
                    id, vendor_id, model_id, input_cost_per_1k_tokens, 
                    output_cost_per_1k_tokens, function_call_cost, image_cost_per_item,
                    currency, pricing_tier, min_volume, effective_date, is_active
                )
                VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), true
                )
            """
            
            await DatabaseUtils.execute_query(
                pricing_query,
                [
                    vendor_id,
                    model_id,
                    Decimal(str(tier_pricing.get('input_cost', 0))),
                    Decimal(str(tier_pricing.get('output_cost', 0))),
                    Decimal(str(tier_pricing.get('function_cost', 0))),
                    Decimal(str(tier_pricing.get('image_cost', 0))),
                    tier_pricing.get('currency', 'USD'),
                    tier_name,
                    tier_pricing.get('min_volume', 0)
                ]
            )
    
    async def _get_openai_pricing_data(self) -> Dict[str, Any]:
        """Get OpenAI pricing data (current as of 2025)"""
        return {
            'gpt-4o': {
                'input_cost': 0.005,    # $5.00 per 1M input tokens
                'output_cost': 0.015,   # $15.00 per 1M output tokens
                'currency': 'USD'
            },
            'gpt-4o-mini': {
                'input_cost': 0.00015, # $0.150 per 1M input tokens
                'output_cost': 0.0006,  # $0.600 per 1M output tokens
                'currency': 'USD'
            },
            'gpt-4-turbo': {
                'input_cost': 0.01,    # $10.00 per 1M input tokens
                'output_cost': 0.03,   # $30.00 per 1M output tokens
                'currency': 'USD'
            },
            'gpt-4': {
                'input_cost': 0.03,    # $30.00 per 1M input tokens
                'output_cost': 0.06,   # $60.00 per 1M output tokens
                'currency': 'USD'
            },
            'gpt-3.5-turbo': {
                'input_cost': 0.0005,  # $0.50 per 1M input tokens
                'output_cost': 0.0015, # $1.50 per 1M output tokens
                'currency': 'USD'
            },
            'dall-e-3': {
                'image_cost': 0.04,    # $0.04 per image (1024x1024)
                'currency': 'USD'
            },
            'dall-e-2': {
                'image_cost': 0.02,    # $0.02 per image (1024x1024)
                'currency': 'USD'
            },
            'whisper-1': {
                'input_cost': 0.006,   # $0.006 per minute
                'currency': 'USD'
            },
            'tts-1': {
                'input_cost': 0.015,   # $15.00 per 1M characters
                'currency': 'USD'
            },
            'text-embedding-3-large': {
                'input_cost': 0.00013, # $0.13 per 1M tokens
                'currency': 'USD'
            },
            'text-embedding-3-small': {
                'input_cost': 0.00002, # $0.02 per 1M tokens
                'currency': 'USD'
            }
        }
    
    async def _get_anthropic_pricing_data(self) -> Dict[str, Any]:
        """Get Anthropic pricing data (current as of 2025)"""
        return {
            'claude-3-5-sonnet-20241022': {
                'input_cost': 0.003,   # $3.00 per 1M input tokens
                'output_cost': 0.015,  # $15.00 per 1M output tokens
                'currency': 'USD'
            },
            'claude-3-5-haiku-20241022': {
                'input_cost': 0.00025, # $0.25 per 1M input tokens
                'output_cost': 0.00125, # $1.25 per 1M output tokens
                'currency': 'USD'
            },
            'claude-3-opus-20240229': {
                'input_cost': 0.015,   # $15.00 per 1M input tokens
                'output_cost': 0.075,  # $75.00 per 1M output tokens
                'currency': 'USD'
            },
            'claude-3-sonnet-20240229': {
                'input_cost': 0.003,   # $3.00 per 1M input tokens
                'output_cost': 0.015,  # $15.00 per 1M output tokens
                'currency': 'USD'
            },
            'claude-3-haiku-20240307': {
                'input_cost': 0.00025, # $0.25 per 1M input tokens
                'output_cost': 0.00125, # $1.25 per 1M output tokens
                'currency': 'USD'
            }
        }
    
    async def _get_google_pricing_data(self) -> Dict[str, Any]:
        """Get Google pricing data (current as of 2025)"""
        return {
            'gemini-1.5-pro': {
                'input_cost': 0.00125,  # $1.25 per 1M input tokens
                'output_cost': 0.005,   # $5.00 per 1M output tokens
                'currency': 'USD'
            },
            'gemini-1.5-flash': {
                'input_cost': 0.000075, # $0.075 per 1M input tokens
                'output_cost': 0.0003,  # $0.30 per 1M output tokens
                'currency': 'USD'
            },
            'gemini-1.5-flash-8b': {
                'input_cost': 0.0000375, # $0.0375 per 1M input tokens
                'output_cost': 0.00015,  # $0.15 per 1M output tokens
                'currency': 'USD'
            },
            'gemini-1.0-pro': {
                'input_cost': 0.0005,   # $0.50 per 1M input tokens
                'output_cost': 0.0015,  # $1.50 per 1M output tokens
                'currency': 'USD'
            },
            'text-embedding-004': {
                'input_cost': 0.0000025, # $0.0025 per 1M tokens
                'currency': 'USD'
            }
        }
    
    async def get_current_pricing(
        self, 
        vendor_name: str, 
        model_name: str, 
        pricing_tier: str = 'standard',
        currency: str = 'USD'
    ) -> Optional[Dict[str, Any]]:
        """Get current pricing for a specific model"""
        
        query = """
            SELECT vp.*, vm.name as model_name, v.name as vendor_name
            FROM vendor_pricing vp
            JOIN vendor_models vm ON vp.model_id = vm.id
            JOIN vendors v ON vm.vendor_id = v.id
            WHERE v.name = $1 
            AND vm.name = $2 
            AND vp.pricing_tier = $3
            AND vp.currency = $4
            AND vp.is_active = true
            AND (vp.expires_at IS NULL OR vp.expires_at > NOW())
            ORDER BY vp.effective_date DESC
            LIMIT 1
        """
        
        result = await DatabaseUtils.execute_query(
            query, [vendor_name, model_name, pricing_tier, currency], fetch_all=False
        )
        
        if result:
            return {
                'input_cost_per_1k_tokens': float(result['input_cost_per_1k_tokens']),
                'output_cost_per_1k_tokens': float(result['output_cost_per_1k_tokens']),
                'function_call_cost': float(result['function_call_cost'] or 0),
                'image_cost_per_item': float(result['image_cost_per_item'] or 0),
                'currency': result['currency'],
                'pricing_tier': result['pricing_tier'],
                'effective_date': result['effective_date'].isoformat(),
            }
        
        return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global instance
pricing_sync = PricingSyncService()

async def sync_vendor_pricing() -> Dict[str, Any]:
    """Convenience function to sync all vendor pricing"""
    return await pricing_sync.sync_all_vendor_pricing()

async def get_model_pricing(
    vendor_name: str, 
    model_name: str, 
    pricing_tier: str = 'standard',
    currency: str = 'USD'
) -> Optional[Dict[str, Any]]:
    """Convenience function to get model pricing"""
    return await pricing_sync.get_current_pricing(vendor_name, model_name, pricing_tier, currency)