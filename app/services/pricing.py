"""
Fixed Pricing Service - Works with actual database schema
Uses correct column names: pricing_tier, input_cost_per_1k_tokens, output_cost_per_1k_tokens
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID
from decimal import Decimal

from ..database import DatabaseUtils
from ..utils.logger import get_logger

logger = get_logger(__name__)

class FixedPricingService:
    """Service for dynamic cost calculations using correct database schema"""
    
    # Fallback pricing when database lookup fails (in USD per 1K tokens)
    FALLBACK_PRICING = {
        "openai": {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "dall-e-3": {"per_image": 0.040},
            "dall-e-2": {"per_image": 0.020},
            "whisper-1": {"per_minute": 0.006},
            "tts-1": {"per_1k_chars": 0.015},
            "text-embedding-3-large": {"input": 0.00013, "output": 0},
            "text-embedding-3-small": {"input": 0.00002, "output": 0},
        },
        "anthropic": {
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-5-haiku-20241022": {"input": 0.00025, "output": 0.00125},
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        },
        "google": {
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-1.5-flash-8b": {"input": 0.0000375, "output": 0.00015},
            "gemini-1.0-pro": {"input": 0.0005, "output": 0.0015},
            "text-embedding-004": {"input": 0.0000025, "output": 0},
        }
    }
    
    @staticmethod
    async def calculate_cost(
        vendor: str, 
        model: str, 
        input_tokens: int = 0, 
        output_tokens: int = 0,
        image_count: int = 0,
        pricing_tier: str = "standard",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Calculate cost for a request using database pricing with fallback
        
        Args:
            vendor: AI vendor name (openai, anthropic, google)
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            image_count: Number of images (for image models)
            pricing_tier: Pricing tier (standard, premium, enterprise, etc.)
            
        Returns:
            Dict with cost breakdown and details
        """
        try:
            # Try to get pricing from database first
            pricing_data = await FixedPricingService._get_pricing_from_db(
                vendor, model, pricing_tier
            )
            
            if pricing_data:
                return FixedPricingService._calculate_cost_from_pricing(
                    pricing_data, input_tokens, output_tokens, image_count, "database"
                )
            
            # Fall back to hardcoded pricing
            fallback_data = FixedPricingService._get_fallback_pricing(vendor, model)
            if fallback_data:
                return FixedPricingService._calculate_cost_from_pricing(
                    fallback_data, input_tokens, output_tokens, image_count, "fallback"
                )
            
            # Last resort - basic estimation
            logger.warning(f"No pricing found for {vendor}/{model}, using basic estimation")
            return FixedPricingService._basic_cost_estimation(
                input_tokens, output_tokens, image_count
            )
            
        except Exception as e:
            logger.error(f"Cost calculation failed for {vendor}/{model}: {e}")
            return FixedPricingService._basic_cost_estimation(
                input_tokens, output_tokens, image_count
            )
    
    @staticmethod
    async def _get_pricing_from_db(
        vendor: str, 
        model: str, 
        pricing_tier: str = "standard"
    ) -> Optional[Dict[str, Any]]:
        """Get pricing data from database using correct column names"""
        try:
            pricing_query = """
                SELECT 
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens,
                    vp.function_call_cost,
                    vp.image_cost_per_item,
                    vp.currency,
                    vp.pricing_tier,
                    vp.effective_date
                FROM vendor_pricing vp
                JOIN vendor_models vm ON vp.model_id = vm.id
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name ILIKE $1 
                  AND vm.name ILIKE $2 
                  AND vp.pricing_tier = $3
                  AND vp.is_active = true
                  AND (vp.expires_at IS NULL OR vp.expires_at > NOW())
                ORDER BY vp.effective_date DESC
                LIMIT 1
            """
            
            result = await DatabaseUtils.execute_query(
                pricing_query,
                [vendor, model, pricing_tier],
                fetch_all=False
            )
            
            if result:
                return {
                    "input": float(result['input_cost_per_1k_tokens']),
                    "output": float(result['output_cost_per_1k_tokens']),
                    "function_call": float(result['function_call_cost'] or 0),
                    "per_image": float(result['image_cost_per_item'] or 0),
                    "currency": result['currency'],
                    "pricing_tier": result['pricing_tier'],
                    "effective_date": result['effective_date']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Database pricing lookup failed for {vendor}/{model}: {e}")
            return None
    
    @staticmethod
    def _get_fallback_pricing(vendor: str, model: str) -> Optional[Dict[str, Any]]:
        """Get fallback pricing from hardcoded values"""
        vendor_lower = vendor.lower()
        model_lower = model.lower()
        
        if vendor_lower not in FixedPricingService.FALLBACK_PRICING:
            return None
            
        vendor_pricing = FixedPricingService.FALLBACK_PRICING[vendor_lower]
        
        if model_lower not in vendor_pricing:
            return None
            
        pricing = vendor_pricing[model_lower]
        
        return {
            "input": pricing.get("input", 0),
            "output": pricing.get("output", 0),
            "function_call": pricing.get("function_call", 0),
            "per_image": pricing.get("per_image", 0),
            "per_minute": pricing.get("per_minute", 0),
            "per_1k_chars": pricing.get("per_1k_chars", 0),
            "currency": "USD",
            "pricing_tier": "standard"
        }
    
    @staticmethod
    def _calculate_cost_from_pricing(
        pricing_data: Dict[str, Any],
        input_tokens: int,
        output_tokens: int, 
        image_count: int,
        source: str
    ) -> Dict[str, Any]:
        """Calculate cost from pricing data"""
        
        # Token-based costs
        input_cost = (input_tokens / 1000) * pricing_data.get("input", 0)
        output_cost = (output_tokens / 1000) * pricing_data.get("output", 0)
        
        # Image-based costs
        image_cost = image_count * pricing_data.get("per_image", 0)
        
        # Function call costs (if applicable)
        function_cost = pricing_data.get("function_call", 0)
        
        total_cost = input_cost + output_cost + image_cost + function_cost
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "image_count": image_count,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "image_cost": round(image_cost, 6),
            "function_cost": round(function_cost, 6),
            "total_cost": round(total_cost, 6),
            "currency": pricing_data.get("currency", "USD"),
            "pricing_tier": pricing_data.get("pricing_tier", "standard"),
            "cost_source": source,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _basic_cost_estimation(
        input_tokens: int, 
        output_tokens: int, 
        image_count: int
    ) -> Dict[str, Any]:
        """Basic cost estimation when no pricing data available"""
        # Very basic estimation - $0.001 per 1K input tokens, $0.002 per 1K output tokens
        input_cost = (input_tokens / 1000) * 0.001
        output_cost = (output_tokens / 1000) * 0.002
        image_cost = image_count * 0.02  # $0.02 per image
        
        total_cost = input_cost + output_cost + image_cost
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "image_count": image_count,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "image_cost": round(image_cost, 6),
            "function_cost": 0.0,
            "total_cost": round(total_cost, 6),
            "currency": "USD",
            "pricing_tier": "estimated",
            "cost_source": "basic_estimation",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    async def get_model_pricing(
        vendor: str, 
        model: str, 
        pricing_tier: str = "standard"
    ) -> Optional[Dict[str, Any]]:
        """Get pricing information for a specific model"""
        return await FixedPricingService._get_pricing_from_db(vendor, model, pricing_tier)
    
    @staticmethod
    async def list_pricing_tiers(vendor: str, model: str) -> List[Dict[str, Any]]:
        """List all available pricing tiers for a model"""
        try:
            tiers_query = """
                SELECT 
                    vp.pricing_tier,
                    vp.input_cost_per_1k_tokens,
                    vp.output_cost_per_1k_tokens,
                    vp.currency,
                    vp.min_volume,
                    vp.effective_date
                FROM vendor_pricing vp
                JOIN vendor_models vm ON vp.model_id = vm.id
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name ILIKE $1 
                  AND vm.name ILIKE $2 
                  AND vp.is_active = true
                  AND (vp.expires_at IS NULL OR vp.expires_at > NOW())
                ORDER BY vp.min_volume ASC, vp.effective_date DESC
            """
            
            results = await DatabaseUtils.execute_query(
                tiers_query,
                [vendor, model],
                fetch_all=True
            )
            
            return [
                {
                    "pricing_tier": result['pricing_tier'],
                    "input_cost_per_1k_tokens": float(result['input_cost_per_1k_tokens']),
                    "output_cost_per_1k_tokens": float(result['output_cost_per_1k_tokens']),
                    "currency": result['currency'],
                    "min_volume": result['min_volume'],
                    "effective_date": result['effective_date']
                }
                for result in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to list pricing tiers for {vendor}/{model}: {e}")
            return []

# Backwards compatibility - create instance that can be imported
pricing_service = FixedPricingService()

# Helper functions for easy import
async def calculate_request_cost(
    vendor: str,
    model: str, 
    input_tokens: int = 0,
    output_tokens: int = 0,
    **kwargs
) -> Dict[str, Any]:
    """Calculate cost for an API request"""
    return await FixedPricingService.calculate_cost(
        vendor, model, input_tokens, output_tokens, **kwargs
    )

async def get_model_pricing_info(
    vendor: str,
    model: str,
    pricing_tier: str = "standard"
) -> Optional[Dict[str, Any]]:
    """Get pricing information for a model"""
    return await FixedPricingService.get_model_pricing(vendor, model, pricing_tier)