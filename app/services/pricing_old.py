"""
Pricing Service - Dynamic cost calculations using vendor_pricing table
Provides accurate, up-to-date pricing for all AI vendors and models
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from uuid import UUID
import json

from ..database import DatabaseUtils
from ..utils.logger import get_logger
from ..utils.db_errors import handle_database_error

logger = get_logger(__name__)

class PricingService:
    """Service for dynamic cost calculations using database pricing"""
    
    # Fallback pricing when database lookup fails (in USD per 1K tokens)
    FALLBACK_PRICING = {
        "openai": {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4-turbo": {"input": 0.01, "output": 0.03},
            "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
            "dall-e-3": {"per_image": 0.040},  # Standard 1024x1024
            "dall-e-2": {"per_image": 0.020},
        },
        "anthropic": {
            "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
            "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
            "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
            "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
            "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        },
        "google": {
            "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
            "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
            "gemini-pro": {"input": 0.0005, "output": 0.0015},
        }
    }
    
    @staticmethod
    async def calculate_cost(vendor: str, model: str, input_tokens: int, output_tokens: int, 
                           company_id: Optional[UUID] = None, **kwargs) -> Dict[str, Any]:
        """
        Calculate cost for a request using dynamic pricing
        
        Args:
            vendor: Vendor name (e.g., 'openai', 'anthropic')
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens  
            company_id: Optional company ID for company-specific pricing
            **kwargs: Additional parameters (e.g., image_count for DALL-E)
            
        Returns:
            Dictionary with cost breakdown
        """
        try:
            # Get pricing from database
            pricing_data = await PricingService._get_pricing_from_db(vendor, model, company_id)
            
            if not pricing_data:
                # Fall back to hardcoded pricing
                logger.warning(f"No database pricing found for {vendor}/{model}, using fallback")
                pricing_data = PricingService._get_fallback_pricing(vendor, model)
            
            if not pricing_data:
                logger.error(f"No pricing data available for {vendor}/{model}")
                return {
                    "input_cost": 0.0,
                    "output_cost": 0.0,
                    "total_cost": 0.0,
                    "pricing_source": "error",
                    "error": f"No pricing data available for {vendor}/{model}"
                }
            
            # Calculate costs based on pricing type
            cost_result = PricingService._calculate_costs(
                pricing_data, input_tokens, output_tokens, **kwargs
            )
            
            logger.debug(f"Calculated cost for {vendor}/{model}: ${cost_result['total_cost']:.6f}")
            
            return cost_result
            
        except Exception as e:
            logger.error(f"Error calculating cost for {vendor}/{model}: {e}")
            return {
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0,
                "pricing_source": "error",
                "error": str(e)
            }
    
    @staticmethod
    async def _get_pricing_from_db(vendor: str, model: str, company_id: Optional[UUID] = None) -> Optional[Dict[str, Any]]:
        """Get pricing data from database"""
        try:
            # First try company-specific pricing if company_id provided
            if company_id:
                company_pricing_query = """
                    SELECT vp.pricing_tier, vp.input_cost_per_1k_tokens, vp.output_cost_per_1k_tokens,
                           vp.function_call_cost, vp.image_cost_per_item, vp.currency, vp.effective_date
                    FROM vendor_pricing vp
                    JOIN vendor_models vm ON vp.model_id = vm.id
                    JOIN vendors v ON vm.vendor_id = v.id
                    WHERE v.name ILIKE $1 AND vm.name ILIKE $2 
                      AND vp.company_id = $3 AND vp.is_active = true
                      AND vp.effective_date <= NOW()
                    ORDER BY vp.effective_date DESC
                    LIMIT 1
                """
                
                company_result = await DatabaseUtils.execute_query(
                    company_pricing_query,
                    [vendor, model, company_id],
                    fetch_all=False
                )
                
                if company_result:
                    return PricingService._format_pricing_data(company_result, "company_specific")
            
            # Fall back to default pricing
            default_pricing_query = """
                SELECT vp.pricing_tier, vp.input_cost_per_1k_tokens, vp.output_cost_per_1k_tokens,
                       vp.function_call_cost, vp.image_cost_per_item, vp.currency, vp.effective_date
                FROM vendor_pricing vp
                JOIN vendor_models vm ON vp.model_id = vm.id
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name ILIKE $1 AND vm.name ILIKE $2 
                  AND vp.company_id IS NULL AND vp.is_active = true
                  AND vp.effective_date <= NOW()
                ORDER BY vp.effective_date DESC
                LIMIT 1
            """
            
            default_result = await DatabaseUtils.execute_query(
                default_pricing_query,
                [vendor, model],
                fetch_all=False
            )
            
            if default_result:
                return PricingService._format_pricing_data(default_result, "database_default")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get pricing from database for {vendor}/{model}: {e}")
            return None
    
    @staticmethod
    def _format_pricing_data(db_result: Dict[str, Any], source: str) -> Dict[str, Any]:
        """Format database pricing result"""
        return {
            "pricing_tier": db_result['pricing_tier'],
            "input_price_per_1k": float(db_result['input_cost_per_1k_tokens'] or 0),
            "output_price_per_1k": float(db_result['output_cost_per_1k_tokens'] or 0),
            "function_call_cost": float(db_result['function_call_cost'] or 0),
            "per_image_price": float(db_result['image_cost_per_item'] or 0),
            "currency": db_result['currency'] or 'USD',
            "effective_date": db_result['effective_date'],
            "source": source
        }
    
    @staticmethod
    def _get_fallback_pricing(vendor: str, model: str) -> Optional[Dict[str, Any]]:
        """Get fallback pricing from hardcoded values"""
        vendor_lower = vendor.lower()
        model_lower = model.lower()
        
        if vendor_lower not in PricingService.FALLBACK_PRICING:
            return None
        
        vendor_pricing = PricingService.FALLBACK_PRICING[vendor_lower]
        
        # Try exact model match first
        if model_lower in vendor_pricing:
            pricing = vendor_pricing[model_lower]
            return {
                "pricing_type": "per_image" if "per_image" in pricing else "per_token",
                "input_price_per_1k": pricing.get("input", 0),
                "output_price_per_1k": pricing.get("output", 0),
                "per_request_price": 0,
                "per_image_price": pricing.get("per_image", 0),
                "currency": "USD",
                "source": "fallback_exact"
            }
        
        # Try partial matches for model families
        for fallback_model, pricing in vendor_pricing.items():
            if fallback_model in model_lower or any(part in model_lower for part in fallback_model.split('-')):
                return {
                    "pricing_type": "per_image" if "per_image" in pricing else "per_token",
                    "input_price_per_1k": pricing.get("input", 0),
                    "output_price_per_1k": pricing.get("output", 0),
                    "per_request_price": 0,
                    "per_image_price": pricing.get("per_image", 0),
                    "currency": "USD",
                    "source": "fallback_partial"
                }
        
        return None
    
    @staticmethod
    def _calculate_costs(pricing_data: Dict[str, Any], input_tokens: int, output_tokens: int, **kwargs) -> Dict[str, Any]:
        """Calculate actual costs based on pricing data"""
        
        pricing_type = pricing_data.get("pricing_type", "per_token")
        
        if pricing_type == "per_image":
            # Image generation pricing
            image_count = kwargs.get("image_count", 1)
            per_image_price = pricing_data.get("per_image_price", 0)
            total_cost = image_count * per_image_price
            
            return {
                "input_cost": 0.0,
                "output_cost": total_cost,
                "total_cost": total_cost,
                "pricing_type": pricing_type,
                "pricing_source": pricing_data.get("source", "database_default"),
                "image_count": image_count,
                "per_image_price": per_image_price,
                "currency": pricing_data.get("currency", "USD")
            }
        
        elif pricing_type == "per_request":
            # Flat per-request pricing
            per_request_price = pricing_data.get("per_request_price", 0)
            
            return {
                "input_cost": 0.0,
                "output_cost": per_request_price,
                "total_cost": per_request_price,
                "pricing_type": pricing_type,
                "pricing_source": pricing_data.get("source", "database_default"),
                "per_request_price": per_request_price,
                "currency": pricing_data.get("currency", "USD")
            }
        
        else:
            # Default per-token pricing
            input_price_per_1k = pricing_data.get("input_price_per_1k", 0)
            output_price_per_1k = pricing_data.get("output_price_per_1k", 0)
            
            input_cost = (input_tokens / 1000.0) * input_price_per_1k
            output_cost = (output_tokens / 1000.0) * output_price_per_1k
            total_cost = input_cost + output_cost
            
            return {
                "input_cost": round(input_cost, 6),
                "output_cost": round(output_cost, 6),
                "total_cost": round(total_cost, 6),
                "pricing_type": pricing_type,
                "pricing_source": pricing_data.get("source", "database_default"),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_price_per_1k": input_price_per_1k,
                "output_price_per_1k": output_price_per_1k,
                "currency": pricing_data.get("currency", "USD")
            }
    
    @staticmethod
    async def get_model_pricing(vendor: str, model: str, company_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get pricing information for a specific model
        
        Args:
            vendor: Vendor name
            model: Model name
            company_id: Optional company ID for company-specific pricing
            
        Returns:
            Dictionary with pricing information
        """
        try:
            pricing_data = await PricingService._get_pricing_from_db(vendor, model, company_id)
            
            if not pricing_data:
                pricing_data = PricingService._get_fallback_pricing(vendor, model)
            
            if not pricing_data:
                return {
                    "status": "not_found",
                    "vendor": vendor,
                    "model": model,
                    "error": "No pricing data available"
                }
            
            return {
                "status": "success",
                "vendor": vendor,
                "model": model,
                "pricing": pricing_data,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to get model pricing for {vendor}/{model}: {error_info['user_message']}")
            return {
                "status": "error",
                "vendor": vendor,
                "model": model,
                "error": error_info['user_message']
            }
    
    @staticmethod
    async def update_pricing(vendor: str, model: str, pricing_config: Dict[str, Any], 
                           company_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Update or create pricing for a vendor/model
        
        Args:
            vendor: Vendor name
            model: Model name
            pricing_config: Pricing configuration
            company_id: Optional company ID for company-specific pricing
            
        Returns:
            Dictionary with update results
        """
        try:
            # Validate pricing configuration
            is_valid, error_msg = PricingService._validate_pricing_config(pricing_config)
            if not is_valid:
                return {"status": "error", "error": error_msg}
            
            # Get vendor_model_id
            vendor_model_query = """
                SELECT vm.id
                FROM vendor_models vm
                JOIN vendors v ON vm.vendor_id = v.id
                WHERE v.name ILIKE $1 AND vm.name ILIKE $2
            """
            
            vendor_model_result = await DatabaseUtils.execute_query(
                vendor_model_query,
                [vendor, model],
                fetch_all=False
            )
            
            if not vendor_model_result:
                return {
                    "status": "error",
                    "error": f"Vendor model {vendor}/{model} not found"
                }
            
            vendor_model_id = vendor_model_result['id']
            
            # Insert or update pricing
            upsert_query = """
                INSERT INTO vendor_pricing (
                    model_id, company_id, pricing_type, 
                    input_price_per_1k_tokens, output_price_per_1k_tokens,
                    per_request_price, per_image_price, currency,
                    effective_date, metadata, is_active, created_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, true, NOW())
                ON CONFLICT (model_id, company_id, effective_date)
                DO UPDATE SET
                    pricing_type = EXCLUDED.pricing_type,
                    input_price_per_1k_tokens = EXCLUDED.input_price_per_1k_tokens,
                    output_price_per_1k_tokens = EXCLUDED.output_price_per_1k_tokens,
                    per_request_price = EXCLUDED.per_request_price,
                    per_image_price = EXCLUDED.per_image_price,
                    currency = EXCLUDED.currency,
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING id, effective_date
            """
            
            effective_date = pricing_config.get('effective_date', datetime.now(timezone.utc))
            if isinstance(effective_date, str):
                effective_date = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
            
            result = await DatabaseUtils.execute_query(
                upsert_query,
                [
                    vendor_model_id,
                    company_id,
                    pricing_config['pricing_type'],
                    pricing_config.get('input_price_per_1k_tokens'),
                    pricing_config.get('output_price_per_1k_tokens'),
                    pricing_config.get('per_request_price'),
                    pricing_config.get('per_image_price'),
                    pricing_config.get('currency', 'USD'),
                    effective_date,
                    json.dumps(pricing_config.get('metadata', {}))
                ],
                fetch_all=False
            )
            
            if result:
                logger.info(f"Updated pricing for {vendor}/{model} (company: {company_id})")
                return {
                    "status": "success",
                    "vendor": vendor,
                    "model": model,
                    "pricing_id": str(result['id']),
                    "effective_date": result['effective_date'].isoformat(),
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return {"status": "error", "error": "Failed to update pricing"}
                
        except Exception as e:
            error_info = handle_database_error(e)
            logger.error(f"Failed to update pricing for {vendor}/{model}: {error_info['user_message']}")
            return {"status": "error", "error": error_info['user_message']}
    
    @staticmethod
    def _validate_pricing_config(config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate pricing configuration"""
        
        if 'pricing_type' not in config:
            return False, "pricing_type is required"
        
        pricing_type = config['pricing_type']
        valid_types = ['per_token', 'per_request', 'per_image']
        
        if pricing_type not in valid_types:
            return False, f"pricing_type must be one of: {valid_types}"
        
        if pricing_type == 'per_token':
            if not config.get('input_price_per_1k_tokens') and not config.get('output_price_per_1k_tokens'):
                return False, "per_token pricing requires input_price_per_1k_tokens or output_price_per_1k_tokens"
        
        elif pricing_type == 'per_request':
            if not config.get('per_request_price'):
                return False, "per_request pricing requires per_request_price"
        
        elif pricing_type == 'per_image':
            if not config.get('per_image_price'):
                return False, "per_image pricing requires per_image_price"
        
        # Validate numeric values
        numeric_fields = [
            'input_price_per_1k_tokens', 'output_price_per_1k_tokens',
            'per_request_price', 'per_image_price'
        ]
        
        for field in numeric_fields:
            if field in config and config[field] is not None:
                try:
                    float(config[field])
                    if config[field] < 0:
                        return False, f"{field} cannot be negative"
                except (ValueError, TypeError):
                    return False, f"{field} must be a valid number"
        
        return True, None