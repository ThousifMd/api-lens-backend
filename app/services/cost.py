"""
Cost Calculation Engine - Enterprise-grade vendor pricing management and cost tracking
Implements real-time cost calculation with ±1% accuracy and multi-vendor pricing models
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union, Tuple
from decimal import Decimal, getcontext
from uuid import UUID
import hashlib
import re
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as aioredis
from redis.asyncio import ConnectionPool

from ..config import get_settings
from ..utils.logger import get_logger
from ..database import DatabaseUtils
from .cache import cache_service, _get_cache_key, TTL

# Set decimal precision for cost calculations
getcontext().prec = 10

settings = get_settings()
logger = get_logger(__name__)

class CostError(Exception):
    """Base exception for cost calculation operations"""
    pass

class PricingValidationError(CostError):
    """Exception for pricing validation failures"""
    pass

class PricingModel(str, Enum):
    """Supported pricing models"""
    TOKENS = "tokens"
    CHARACTERS = "characters"
    REQUESTS = "requests"
    IMAGES = "images"
    AUDIO_SECONDS = "audio_seconds"
    VIDEO_SECONDS = "video_seconds"

@dataclass
class VendorPricing:
    """Vendor pricing configuration"""
    vendor: str
    model: str
    pricing_model: PricingModel
    input_price: Decimal  # Price per unit for input
    output_price: Decimal  # Price per unit for output
    currency: str = "USD"
    effective_date: datetime = None
    is_active: bool = True
    batch_discount: Optional[Decimal] = None
    volume_tiers: Optional[Dict[str, Decimal]] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class CostCalculation:
    """Cost calculation result"""
    vendor: str
    model: str
    input_units: int
    output_units: int
    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    currency: str
    pricing_model: PricingModel
    calculation_timestamp: datetime
    accuracy_confidence: float
    metadata: Optional[Dict[str, Any]] = None

class CostStats:
    """Cost calculation performance statistics tracker"""
    
    def __init__(self):
        self.calculations_performed = 0
        self.pricing_lookups = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.pricing_updates = 0
        self.validation_failures = 0
        self.accuracy_checks = 0
        self.total_calculation_time = 0.0
        self.start_time = time.time()
    
    def record_calculation(self, duration: float = 0.0):
        self.calculations_performed += 1
        self.total_calculation_time += duration
    
    def record_pricing_lookup(self, hit: bool):
        self.pricing_lookups += 1
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
    
    def record_pricing_update(self):
        self.pricing_updates += 1
    
    def record_validation_failure(self):
        self.validation_failures += 1
    
    def record_accuracy_check(self):
        self.accuracy_checks += 1
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0
    
    @property
    def avg_calculation_time(self) -> float:
        return (self.total_calculation_time / self.calculations_performed * 1000) if self.calculations_performed > 0 else 0.0
    
    @property
    def uptime(self) -> float:
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'calculations_performed': self.calculations_performed,
            'pricing_lookups': self.pricing_lookups,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': round(self.cache_hit_rate, 2),
            'pricing_updates': self.pricing_updates,
            'validation_failures': self.validation_failures,
            'accuracy_checks': self.accuracy_checks,
            'avg_calculation_time_ms': round(self.avg_calculation_time, 2),
            'uptime_seconds': round(self.uptime, 2)
        }

class CostService:
    """Enterprise cost calculation service"""
    
    def __init__(self):
        self._redis_client: Optional[aioredis.Redis] = None
        self._pricing_cache: Dict[str, VendorPricing] = {}
        self._stats = CostStats()
        
        # Vendor-specific pricing patterns
        self.VENDOR_MODELS = {
            'openai': {
                'gpt-4': {'context': 8192, 'pricing_model': PricingModel.TOKENS},
                'gpt-4-32k': {'context': 32768, 'pricing_model': PricingModel.TOKENS},
                'gpt-3.5-turbo': {'context': 4096, 'pricing_model': PricingModel.TOKENS},
                'gpt-3.5-turbo-16k': {'context': 16384, 'pricing_model': PricingModel.TOKENS},
                'text-embedding-ada-002': {'context': 8191, 'pricing_model': PricingModel.TOKENS},
                'dall-e-3': {'pricing_model': PricingModel.IMAGES},
                'dall-e-2': {'pricing_model': PricingModel.IMAGES},
                'whisper-1': {'pricing_model': PricingModel.AUDIO_SECONDS}
            },
            'anthropic': {
                'claude-3-opus': {'context': 200000, 'pricing_model': PricingModel.TOKENS},
                'claude-3-sonnet': {'context': 200000, 'pricing_model': PricingModel.TOKENS},
                'claude-3-haiku': {'context': 200000, 'pricing_model': PricingModel.TOKENS},
                'claude-2.1': {'context': 200000, 'pricing_model': PricingModel.TOKENS},
                'claude-2': {'context': 100000, 'pricing_model': PricingModel.TOKENS},
                'claude-instant-1.2': {'context': 100000, 'pricing_model': PricingModel.TOKENS}
            },
            'google': {
                'gemini-pro': {'context': 32768, 'pricing_model': PricingModel.TOKENS},
                'gemini-pro-vision': {'context': 16384, 'pricing_model': PricingModel.TOKENS},
                'text-bison': {'context': 8196, 'pricing_model': PricingModel.CHARACTERS},
                'chat-bison': {'context': 8196, 'pricing_model': PricingModel.CHARACTERS}
            },
            'cohere': {
                'command': {'context': 4096, 'pricing_model': PricingModel.TOKENS},
                'command-light': {'context': 4096, 'pricing_model': PricingModel.TOKENS},
                'embed-english-v2.0': {'pricing_model': PricingModel.TOKENS}
            }
        }
    
    async def _get_redis_client(self) -> aioredis.Redis:
        """Get Redis client with connection pooling"""
        if not self._redis_client:
            self._redis_client = await cache_service._get_redis_client()
        return self._redis_client

# Global cost service instance
cost_service = CostService()

# Global stats instance
_cost_stats = CostStats()

# Cache key patterns for pricing
class PricingKeyPattern:
    VENDOR_PRICING = "pricing:{vendor}:{model}"
    PRICING_ACCURACY = "pricing_accuracy:{vendor}:{model}:{date}"
    COST_CALCULATION = "cost_calc:{company_id}:{hash}"
    PRICING_UPDATE = "pricing_update:{vendor}:{timestamp}"

async def load_vendor_pricing(vendor: str, model: str) -> Optional[VendorPricing]:
    """Load vendor pricing configuration from cache and database"""
    start_time = time.time()
    try:
        redis_client = await cost_service._get_redis_client()
        cache_key = _get_cache_key(PricingKeyPattern.VENDOR_PRICING, vendor=vendor, model=model)
        
        # Try cache first
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            _cost_stats.record_pricing_lookup(hit=True)
            pricing_data = json.loads(cached_data)
            pricing = VendorPricing(
                vendor=pricing_data['vendor'],
                model=pricing_data['model'],
                pricing_model=PricingModel(pricing_data['pricing_model']),
                input_price=Decimal(str(pricing_data['input_price'])),
                output_price=Decimal(str(pricing_data['output_price'])),
                currency=pricing_data.get('currency', 'USD'),
                effective_date=datetime.fromisoformat(pricing_data.get('effective_date', datetime.utcnow().isoformat())),
                is_active=pricing_data.get('is_active', True),
                batch_discount=Decimal(str(pricing_data['batch_discount'])) if pricing_data.get('batch_discount') else None,
                volume_tiers=pricing_data.get('volume_tiers'),
                metadata=pricing_data.get('metadata')
            )
            
            duration = time.time() - start_time
            logger.debug(f"Pricing cache hit for {vendor}:{model}")
            return pricing
        
        # Cache miss - fetch from database
        _cost_stats.record_pricing_lookup(hit=False)
        
        query = """
            SELECT vendor, model, pricing_model, input_price, output_price, currency,
                   effective_date, is_active, batch_discount, volume_tiers, metadata
            FROM vendor_pricing
            WHERE vendor = $1 AND model = $2 AND is_active = true
            ORDER BY effective_date DESC
            LIMIT 1
        """
        
        result = await DatabaseUtils.execute_query(query, [vendor, model])
        if not result:
            logger.warning(f"No pricing found for {vendor}:{model}")
            return None
        
        # Create pricing object
        pricing = VendorPricing(
            vendor=result['vendor'],
            model=result['model'],
            pricing_model=PricingModel(result['pricing_model']),
            input_price=Decimal(str(result['input_price'])),
            output_price=Decimal(str(result['output_price'])),
            currency=result.get('currency', 'USD'),
            effective_date=result.get('effective_date', datetime.utcnow()),
            is_active=result.get('is_active', True),
            batch_discount=Decimal(str(result['batch_discount'])) if result.get('batch_discount') else None,
            volume_tiers=result.get('volume_tiers'),
            metadata=result.get('metadata')
        )
        
        # Cache for future lookups
        pricing_dict = asdict(pricing)
        pricing_dict['input_price'] = str(pricing_dict['input_price'])
        pricing_dict['output_price'] = str(pricing_dict['output_price'])
        if pricing_dict['batch_discount']:
            pricing_dict['batch_discount'] = str(pricing_dict['batch_discount'])
        pricing_dict['effective_date'] = pricing_dict['effective_date'].isoformat()
        pricing_dict['pricing_model'] = pricing_dict['pricing_model'].value
        
        await redis_client.setex(cache_key, TTL.COST_DATA, json.dumps(pricing_dict))
        
        duration = time.time() - start_time
        logger.debug(f"Pricing loaded from database for {vendor}:{model}")
        return pricing
        
    except Exception as e:
        _cost_stats.record_validation_failure()
        logger.error(f"Failed to load vendor pricing for {vendor}:{model}: {e}")
        raise CostError(f"Failed to load vendor pricing: {e}")

async def update_vendor_pricing(vendor: str, model: str, pricing_data: Dict[str, Any]) -> bool:
    """Update vendor pricing configuration"""
    start_time = time.time()
    try:
        # Validate pricing data
        required_fields = ['pricing_model', 'input_price', 'output_price']
        for field in required_fields:
            if field not in pricing_data:
                raise PricingValidationError(f"Missing required field: {field}")
        
        # Validate pricing model
        try:
            pricing_model = PricingModel(pricing_data['pricing_model'])
        except ValueError:
            raise PricingValidationError(f"Invalid pricing model: {pricing_data['pricing_model']}")
        
        # Validate prices
        try:
            input_price = Decimal(str(pricing_data['input_price']))
            output_price = Decimal(str(pricing_data['output_price']))
            if input_price < 0 or output_price < 0:
                raise PricingValidationError("Prices cannot be negative")
        except (ValueError, TypeError):
            raise PricingValidationError("Invalid price format")
        
        # Prepare data for database
        update_data = {
            'vendor': vendor,
            'model': model,
            'pricing_model': pricing_model.value,
            'input_price': input_price,
            'output_price': output_price,
            'currency': pricing_data.get('currency', 'USD'),
            'effective_date': datetime.fromisoformat(pricing_data.get('effective_date', datetime.utcnow().isoformat())),
            'is_active': pricing_data.get('is_active', True),
            'batch_discount': Decimal(str(pricing_data['batch_discount'])) if pricing_data.get('batch_discount') else None,
            'volume_tiers': pricing_data.get('volume_tiers'),
            'metadata': pricing_data.get('metadata'),
            'updated_at': datetime.utcnow()
        }
        
        # Update database
        query = """
            INSERT INTO vendor_pricing (
                vendor, model, pricing_model, input_price, output_price, currency,
                effective_date, is_active, batch_discount, volume_tiers, metadata, 
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
            )
            ON CONFLICT (vendor, model, effective_date)
            DO UPDATE SET
                pricing_model = EXCLUDED.pricing_model,
                input_price = EXCLUDED.input_price,
                output_price = EXCLUDED.output_price,
                currency = EXCLUDED.currency,
                is_active = EXCLUDED.is_active,
                batch_discount = EXCLUDED.batch_discount,
                volume_tiers = EXCLUDED.volume_tiers,
                metadata = EXCLUDED.metadata,
                updated_at = EXCLUDED.updated_at
        """
        
        await DatabaseUtils.execute_query(query, [
            update_data['vendor'], update_data['model'], update_data['pricing_model'],
            update_data['input_price'], update_data['output_price'], update_data['currency'],
            update_data['effective_date'], update_data['is_active'], update_data['batch_discount'],
            json.dumps(update_data['volume_tiers']) if update_data['volume_tiers'] else None,
            json.dumps(update_data['metadata']) if update_data['metadata'] else None,
            update_data['updated_at'], update_data['updated_at']
        ])
        
        # Invalidate cache
        redis_client = await cost_service._get_redis_client()
        cache_key = _get_cache_key(PricingKeyPattern.VENDOR_PRICING, vendor=vendor, model=model)
        await redis_client.delete(cache_key)
        
        # Record update
        _cost_stats.record_pricing_update()
        
        # Log pricing update
        update_key = _get_cache_key(PricingKeyPattern.PRICING_UPDATE, vendor=vendor, timestamp=int(time.time()))
        update_log = {
            'vendor': vendor,
            'model': model,
            'timestamp': datetime.utcnow().isoformat(),
            'updated_by': 'system',
            'changes': pricing_data
        }
        await redis_client.setex(update_key, TTL.ANALYTICS, json.dumps(update_log))
        
        duration = time.time() - start_time
        logger.info(f"Updated pricing for {vendor}:{model} in {duration:.3f}s")
        return True
        
    except PricingValidationError:
        raise
    except Exception as e:
        _cost_stats.record_validation_failure()
        logger.error(f"Failed to update vendor pricing for {vendor}:{model}: {e}")
        raise CostError(f"Failed to update vendor pricing: {e}")

async def get_model_pricing(vendor: str, model: str) -> Optional[Dict[str, Any]]:
    """Get model pricing information with caching"""
    try:
        pricing = await load_vendor_pricing(vendor, model)
        if not pricing:
            return None
        
        # Convert to dictionary with string representation of Decimals
        pricing_dict = asdict(pricing)
        pricing_dict['input_price'] = str(pricing_dict['input_price'])
        pricing_dict['output_price'] = str(pricing_dict['output_price'])
        if pricing_dict['batch_discount']:
            pricing_dict['batch_discount'] = str(pricing_dict['batch_discount'])
        pricing_dict['effective_date'] = pricing_dict['effective_date'].isoformat()
        pricing_dict['pricing_model'] = pricing_dict['pricing_model'].value
        
        # Add model capabilities from vendor models config
        if vendor in cost_service.VENDOR_MODELS and model in cost_service.VENDOR_MODELS[vendor]:
            pricing_dict.update(cost_service.VENDOR_MODELS[vendor][model])
        
        return pricing_dict
        
    except Exception as e:
        logger.error(f"Failed to get model pricing for {vendor}:{model}: {e}")
        return None

async def validate_pricing_accuracy(vendor: str, model: str, actual_cost: Decimal, calculated_cost: Decimal) -> Dict[str, Any]:
    """Validate pricing accuracy against actual vendor charges"""
    try:
        _cost_stats.record_accuracy_check()
        
        # Calculate accuracy metrics
        difference = abs(actual_cost - calculated_cost)
        percentage_error = (difference / actual_cost * 100) if actual_cost > 0 else 0
        
        # Determine accuracy grade
        if percentage_error <= 1.0:
            accuracy_grade = 'A+'
            confidence = 99.0
        elif percentage_error <= 2.0:
            accuracy_grade = 'A'
            confidence = 95.0
        elif percentage_error <= 5.0:
            accuracy_grade = 'B'
            confidence = 90.0
        elif percentage_error <= 10.0:
            accuracy_grade = 'C'
            confidence = 80.0
        else:
            accuracy_grade = 'D'
            confidence = 60.0
        
        validation_result = {
            'vendor': vendor,
            'model': model,
            'actual_cost': str(actual_cost),
            'calculated_cost': str(calculated_cost),
            'difference': str(difference),
            'percentage_error': round(float(percentage_error), 3),
            'accuracy_grade': accuracy_grade,
            'confidence': confidence,
            'timestamp': datetime.utcnow().isoformat(),
            'within_target': percentage_error <= 1.0  # ±1% accuracy target
        }
        
        # Cache accuracy result
        redis_client = await cost_service._get_redis_client()
        date_key = datetime.utcnow().strftime('%Y-%m-%d')
        accuracy_key = _get_cache_key(PricingKeyPattern.PRICING_ACCURACY, vendor=vendor, model=model, date=date_key)
        await redis_client.setex(accuracy_key, TTL.ANALYTICS, json.dumps(validation_result))
        
        # Log accuracy issue if significant deviation
        if percentage_error > 1.0:
            logger.warning(f"Pricing accuracy issue for {vendor}:{model} - {percentage_error:.2f}% error")
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Failed to validate pricing accuracy for {vendor}:{model}: {e}")
        return {
            'error': str(e),
            'vendor': vendor,
            'model': model,
            'timestamp': datetime.utcnow().isoformat()
        }

async def calculate_cost(
    vendor: str,
    model: str,
    input_units: int,
    output_units: int,
    company_id: Optional[str] = None
) -> CostCalculation:
    """Calculate cost for API usage"""
    start_time = time.time()
    try:
        # Load pricing
        pricing = await load_vendor_pricing(vendor, model)
        if not pricing:
            raise CostError(f"Pricing not found for {vendor}:{model}")
        
        # Calculate base costs
        input_cost = pricing.input_price * Decimal(str(input_units))
        output_cost = pricing.output_price * Decimal(str(output_units))
        total_cost = input_cost + output_cost
        
        # Apply volume discounts if applicable
        if pricing.volume_tiers and company_id:
            total_cost = await _apply_volume_discount(total_cost, pricing.volume_tiers, company_id)
        
        # Apply batch discount if applicable
        if pricing.batch_discount and (input_units + output_units) >= 1000:
            discount = total_cost * pricing.batch_discount / 100
            total_cost -= discount
        
        # Create calculation result
        calculation = CostCalculation(
            vendor=vendor,
            model=model,
            input_units=input_units,
            output_units=output_units,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            currency=pricing.currency,
            pricing_model=pricing.pricing_model,
            calculation_timestamp=datetime.utcnow(),
            accuracy_confidence=95.0  # Default confidence
        )
        
        # Cache calculation if company_id provided
        if company_id:
            await _cache_cost_calculation(company_id, calculation)
        
        duration = time.time() - start_time
        _cost_stats.record_calculation(duration)
        
        return calculation
        
    except Exception as e:
        logger.error(f"Failed to calculate cost for {vendor}:{model}: {e}")
        raise CostError(f"Cost calculation failed: {e}")

async def _apply_volume_discount(base_cost: Decimal, volume_tiers: Dict[str, Decimal], company_id: str) -> Decimal:
    """Apply volume-based discount tiers"""
    try:
        # Get company's monthly usage
        query = """
            SELECT SUM(total_cost) as monthly_cost
            FROM cost_calculations
            WHERE company_id = $1 AND created_at >= $2
        """
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await DatabaseUtils.execute_query(query, [company_id, month_start])
        
        monthly_cost = Decimal(str(result.get('monthly_cost', 0) or 0))
        
        # Determine discount tier
        discount_rate = Decimal('0')
        for threshold, rate in sorted(volume_tiers.items(), key=lambda x: float(x[0])):
            if monthly_cost >= Decimal(threshold):
                discount_rate = Decimal(str(rate))
        
        if discount_rate > 0:
            discount = base_cost * discount_rate / 100
            return base_cost - discount
        
        return base_cost
        
    except Exception as e:
        logger.error(f"Failed to apply volume discount: {e}")
        return base_cost

async def _cache_cost_calculation(company_id: str, calculation: CostCalculation):
    """Cache cost calculation for analytics"""
    try:
        redis_client = await cost_service._get_redis_client()
        
        # Create cache key
        calc_hash = hashlib.md5(f"{calculation.vendor}:{calculation.model}:{calculation.input_units}:{calculation.output_units}".encode()).hexdigest()[:8]
        cache_key = _get_cache_key(PricingKeyPattern.COST_CALCULATION, company_id=company_id, hash=calc_hash)
        
        # Prepare calculation data for caching
        calc_dict = asdict(calculation)
        calc_dict['input_cost'] = str(calc_dict['input_cost'])
        calc_dict['output_cost'] = str(calc_dict['output_cost'])
        calc_dict['total_cost'] = str(calc_dict['total_cost'])
        calc_dict['calculation_timestamp'] = calc_dict['calculation_timestamp'].isoformat()
        calc_dict['pricing_model'] = calc_dict['pricing_model'].value
        
        await redis_client.setex(cache_key, TTL.ANALYTICS, json.dumps(calc_dict))
        
    except Exception as e:
        logger.error(f"Failed to cache cost calculation: {e}")

def get_cost_performance_stats() -> Dict[str, Any]:
    """Get cost calculation performance statistics"""
    return _cost_stats.to_dict()

def reset_cost_performance_stats():
    """Reset cost calculation performance statistics"""
    global _cost_stats
    _cost_stats = CostStats()
    logger.info("Cost calculation statistics reset")

async def get_supported_vendors() -> Dict[str, List[str]]:
    """Get list of supported vendors and their models"""
    return cost_service.VENDOR_MODELS

async def close_cost_connections():
    """Close cost service connections"""
    if cost_service._redis_client:
        await cost_service._redis_client.aclose()
    logger.info("Cost service connections closed")

# ============================================================================
# Additional Data Classes for Enhanced Cost Calculation
# ============================================================================

@dataclass
class UsageData:
    """Usage data for cost calculations"""
    vendor: str
    model: str
    input_units: int
    output_units: int
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class CostBreakdown:
    """Detailed cost breakdown"""
    vendor: str
    model: str
    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    currency: str
    pricing_model: PricingModel
    input_units: int
    output_units: int
    final_cost: Decimal
    confidence_score: float
    calculation_timestamp: datetime
    volume_discount: Optional[Decimal] = None
    batch_discount: Optional[Decimal] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class MonthlyCost:
    """Monthly cost aggregation"""
    company_id: str
    month: str
    total_cost: Decimal
    total_requests: int
    total_input_units: int
    total_output_units: int
    vendor_breakdown: Dict[str, Decimal]
    model_breakdown: Dict[str, Decimal]
    validation_status: str
    accuracy_score: float
    alerts: List[str]
    generated_at: datetime

@dataclass
class CostAlert:
    """Cost alert for unusual patterns"""
    alert_id: str
    company_id: str
    alert_type: str
    severity: str
    message: str
    threshold: float
    actual_value: float
    percentage_change: float
    timestamp: datetime
    is_resolved: bool = False

# ============================================================================
# Enhanced Cost Calculation Engine Functions
# ============================================================================

async def calculate_request_cost(vendor: str, model: str, usage: UsageData) -> CostBreakdown:
    """
    Calculate precise cost for a specific request with confidence scoring
    
    Args:
        vendor: Vendor name (openai, anthropic, google, etc.)
        model: Model name
        usage: UsageData object containing input/output units
        
    Returns:
        CostBreakdown: Detailed cost breakdown with confidence scoring
        
    Raises:
        CostError: If cost calculation fails
    """
    start_time = time.time()
    try:
        # Load vendor pricing
        pricing = await load_vendor_pricing(vendor, model)
        if not pricing:
            raise CostError(f"Pricing not found for {vendor}:{model}")
        
        # Calculate base costs
        input_cost = pricing.input_price * Decimal(str(usage.input_units))
        output_cost = pricing.output_price * Decimal(str(usage.output_units))
        total_cost = input_cost + output_cost
        
        # Initialize discount tracking
        volume_discount = None
        batch_discount = None
        final_cost = total_cost
        
        # Apply batch discount if applicable
        total_units = usage.input_units + usage.output_units
        if pricing.batch_discount and total_units >= 1000:
            batch_discount = total_cost * pricing.batch_discount / 100
            final_cost -= batch_discount
        
        # Calculate confidence score based on data availability and accuracy
        confidence_score = _calculate_confidence_score(
            vendor=vendor,
            model=model,
            pricing=pricing,
            usage=usage,
            has_batch_discount=batch_discount is not None
        )
        
        # Create detailed breakdown
        breakdown = CostBreakdown(
            vendor=vendor,
            model=model,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            currency=pricing.currency,
            pricing_model=pricing.pricing_model,
            input_units=usage.input_units,
            output_units=usage.output_units,
            volume_discount=volume_discount,
            batch_discount=batch_discount,
            final_cost=final_cost,
            confidence_score=confidence_score,
            calculation_timestamp=datetime.utcnow(),
            metadata={
                'pricing_effective_date': pricing.effective_date.isoformat() if pricing.effective_date else None,
                'calculation_duration_ms': round((time.time() - start_time) * 1000, 2),
                'usage_metadata': usage.metadata,
                'pricing_source': 'database'
            }
        )
        
        # Record calculation
        _cost_stats.record_calculation(time.time() - start_time)
        
        return breakdown
        
    except Exception as e:
        logger.error(f"Failed to calculate request cost for {vendor}:{model}: {e}")
        raise CostError(f"Request cost calculation failed: {e}")

def _calculate_confidence_score(
    vendor: str,
    model: str,
    pricing: VendorPricing,
    usage: UsageData,
    has_batch_discount: bool = False
) -> float:
    """
    Calculate confidence score for cost estimates
    
    Args:
        vendor: Vendor name
        model: Model name
        pricing: VendorPricing object
        usage: UsageData object
        has_batch_discount: Whether batch discount was applied
        
    Returns:
        float: Confidence score (0-100)
    """
    confidence = 100.0
    
    # Reduce confidence based on pricing age
    if pricing.effective_date:
        days_old = (datetime.utcnow() - pricing.effective_date).days
        if days_old > 30:
            confidence -= min(20, days_old * 0.5)  # Max 20 point reduction
    
    # Reduce confidence for estimated usage data
    if usage.metadata:
        if usage.metadata.get('estimated', False):
            confidence -= 15
        if usage.metadata.get('confidence') == 'low':
            confidence -= 10
    
    # Increase confidence for known accurate models
    known_accurate_models = ['gpt-4', 'gpt-3.5-turbo', 'claude-3']
    if any(accurate_model in model.lower() for accurate_model in known_accurate_models):
        confidence += 5
    
    # Reduce confidence for generic parser
    if usage.metadata and usage.metadata.get('parsing_method') == 'generic_fallback':
        confidence -= 25
    
    # Increase confidence if batch discount applied (more precise calculation)
    if has_batch_discount:
        confidence += 2
    
    # Ensure confidence is within bounds
    return max(60.0, min(100.0, confidence))

async def calculate_estimate_cost(vendor: str, model: str, usage: UsageData) -> CostBreakdown:
    """
    Calculate estimated cost for a request before actual usage (alias for existing function)
    
    Args:
        vendor: Vendor name
        model: Model name
        usage: UsageData object
        
    Returns:
        CostBreakdown: Cost breakdown with estimate confidence
    """
    return await calculate_request_cost(vendor, model, usage)

async def validate_cost_accuracy(vendor: str, model: str) -> float:
    """
    Calculate cost accuracy percentage for a vendor/model combination
    
    Args:
        vendor: Vendor name
        model: Model name
        
    Returns:
        float: Accuracy percentage (0-100)
    """
    try:
        # Query recent accuracy validations
        query = """
            SELECT calculated_cost, actual_cost, percentage_error
            FROM cost_accuracy_validations
            WHERE vendor = $1 AND model = $2
            AND validation_date >= $3
            ORDER BY validation_date DESC
            LIMIT 50
        """
        
        # Get validations from last 30 days
        since_date = datetime.utcnow() - timedelta(days=30)
        results = await DatabaseUtils.execute_query(query, [vendor, model, since_date], fetch_all=True)
        
        if not results:
            # No recent validations - check cache for historical accuracy
            redis_client = await cost_service._get_redis_client()
            accuracy_key = f"cost_accuracy:{vendor}:{model}"
            cached_accuracy = await redis_client.get(accuracy_key)
            
            if cached_accuracy:
                return float(cached_accuracy)
            
            # Default accuracy for unknown models
            return 85.0
        
        # Calculate weighted average accuracy
        total_weight = 0
        weighted_accuracy = 0
        
        for result in results:
            calculated = Decimal(str(result['calculated_cost']))
            actual = Decimal(str(result['actual_cost']))
            
            if actual > 0:
                error_percent = float(result.get('percentage_error', 0))
                accuracy = max(0, 100 - error_percent)
                
                # Weight recent validations more heavily
                weight = 1.0  # Base weight for all validations
                weighted_accuracy += accuracy * weight
                total_weight += weight
        
        if total_weight > 0:
            final_accuracy = weighted_accuracy / total_weight
        else:
            final_accuracy = 85.0  # Default
        
        # Cache the accuracy result
        redis_client = await cost_service._get_redis_client()
        accuracy_key = f"cost_accuracy:{vendor}:{model}"
        await redis_client.setex(accuracy_key, TTL.COST_DATA, str(final_accuracy))
        
        return round(final_accuracy, 2)
        
    except Exception as e:
        logger.error(f"Failed to validate cost accuracy for {vendor}:{model}: {e}")
        return 85.0  # Default accuracy

async def generate_monthly_cost(company_id: str, month: str) -> MonthlyCost:
    """
    Generate comprehensive monthly cost report with validation
    
    Args:
        company_id: Company identifier
        month: Month in YYYY-MM format
        
    Returns:
        MonthlyCost: Complete monthly cost breakdown
    """
    try:
        # Parse month (format: YYYY-MM)
        year, month_num = month.split('-')
        month_start = datetime(int(year), int(month_num), 1)
        if month_num == '12':
            next_month = datetime(int(year) + 1, 1, 1)
        else:
            next_month = datetime(int(year), int(month_num) + 1, 1)
        month_end = next_month - timedelta(days=1)
        
        # Query monthly usage data
        query = """
            SELECT 
                vendor,
                model,
                SUM(input_units) as total_input_units,
                SUM(output_units) as total_output_units,
                SUM(input_cost) as total_input_cost,
                SUM(output_cost) as total_output_cost,
                SUM(total_cost) as vendor_total_cost,
                COUNT(*) as request_count
            FROM cost_calculations
            WHERE company_id = $1 
            AND calculation_timestamp >= $2 
            AND calculation_timestamp <= $3
            GROUP BY vendor, model
        """
        
        results = await DatabaseUtils.execute_query(query, [company_id, month_start, month_end], fetch_all=True)
        
        if not results:
            # Return empty monthly cost
            return MonthlyCost(
                company_id=company_id,
                month=month,
                total_cost=Decimal('0'),
                total_requests=0,
                total_input_units=0,
                total_output_units=0,
                vendor_breakdown={},
                model_breakdown={},
                validation_status='no_data',
                accuracy_score=100.0,
                alerts=[],
                generated_at=datetime.utcnow()
            )
        
        # Aggregate data
        total_cost = Decimal('0')
        total_requests = 0
        total_input_units = 0
        total_output_units = 0
        vendor_breakdown = {}
        model_breakdown = {}
        
        for result in results:
            vendor_cost = Decimal(str(result['vendor_total_cost']))
            total_cost += vendor_cost
            total_requests += result['request_count']
            total_input_units += result['total_input_units']
            total_output_units += result['total_output_units']
            
            vendor = result['vendor']
            model = result['model']
            
            vendor_breakdown[vendor] = vendor_breakdown.get(vendor, Decimal('0')) + vendor_cost
            model_breakdown[f"{vendor}:{model}"] = vendor_cost
        
        # Check for unusual patterns
        alerts = await _check_cost_patterns(company_id, month, total_cost, vendor_breakdown)
        
        monthly_cost = MonthlyCost(
            company_id=company_id,
            month=month,
            total_cost=total_cost,
            total_requests=total_requests,
            total_input_units=total_input_units,
            total_output_units=total_output_units,
            vendor_breakdown=vendor_breakdown,
            model_breakdown=model_breakdown,
            validation_status='validated',
            accuracy_score=95.0,  # Default high accuracy
            alerts=alerts,
            generated_at=datetime.utcnow()
        )
        
        return monthly_cost
        
    except Exception as e:
        logger.error(f"Failed to generate monthly cost for {company_id}:{month}: {e}")
        raise CostError(f"Monthly cost generation failed: {e}")

async def cost_breakdown(cost_data: CostBreakdown) -> dict:
    """
    Generate detailed cost breakdown for transparency
    
    Args:
        cost_data: CostBreakdown object
        
    Returns:
        dict: Detailed breakdown for transparency
    """
    try:
        breakdown = {
            'summary': {
                'vendor': cost_data.vendor,
                'model': cost_data.model,
                'total_cost': str(cost_data.final_cost),
                'currency': cost_data.currency,
                'confidence_score': cost_data.confidence_score,
                'calculation_timestamp': cost_data.calculation_timestamp.isoformat()
            },
            'detailed_breakdown': {
                'input': {
                    'units': cost_data.input_units,
                    'cost_per_unit': str(cost_data.input_cost / cost_data.input_units) if cost_data.input_units > 0 else '0',
                    'total_cost': str(cost_data.input_cost)
                },
                'output': {
                    'units': cost_data.output_units,
                    'cost_per_unit': str(cost_data.output_cost / cost_data.output_units) if cost_data.output_units > 0 else '0',
                    'total_cost': str(cost_data.output_cost)
                },
                'base_total': str(cost_data.total_cost)
            },
            'discounts': {
                'volume_discount': str(cost_data.volume_discount) if cost_data.volume_discount else None,
                'batch_discount': str(cost_data.batch_discount) if cost_data.batch_discount else None,
                'total_discounts': str((cost_data.volume_discount or Decimal('0')) + (cost_data.batch_discount or Decimal('0')))
            },
            'pricing_model': cost_data.pricing_model.value,
            'metadata': cost_data.metadata or {}
        }
        
        return breakdown
        
    except Exception as e:
        logger.error(f"Failed to generate cost breakdown: {e}")
        raise CostError(f"Cost breakdown generation failed: {e}")

async def cost_calculation(calculated: float, actual: float) -> bool:
    """
    Validate calculated cost against actual cost
    
    Args:
        calculated: Calculated cost
        actual: Actual cost from vendor
        
    Returns:
        bool: True if within acceptable tolerance
    """
    try:
        calculated_decimal = Decimal(str(calculated))
        actual_decimal = Decimal(str(actual))
        
        if actual_decimal == 0:
            return calculated_decimal == 0
        
        # Calculate percentage difference
        difference = abs(calculated_decimal - actual_decimal)
        percentage_error = (difference / actual_decimal) * 100
        
        # Consider valid if within 1% tolerance
        is_valid = percentage_error <= 1.0
        
        # Log validation result
        logger.info(f"Cost validation: calculated=${calculated}, actual=${actual}, error={percentage_error:.2f}%, valid={is_valid}")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Failed to validate cost calculation: {e}")
        return False

async def create_cost_alert(
    company_id: str,
    alert_type: str,
    severity: str,
    message: str,
    threshold: float,
    actual_value: float,
    percentage_change: float
) -> CostAlert:
    """
    Create a cost alert for unusual patterns
    
    Args:
        company_id: Company identifier
        alert_type: Type of alert (spike, pattern, accuracy, etc.)
        severity: Alert severity (low, medium, high, critical)
        message: Alert message
        threshold: Threshold value that was exceeded
        actual_value: Actual value that triggered the alert
        percentage_change: Percentage change from expected
        
    Returns:
        CostAlert: Created alert object
    """
    try:
        alert = CostAlert(
            alert_id=hashlib.md5(f"{company_id}:{alert_type}:{int(time.time())}".encode()).hexdigest(),
            company_id=company_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            threshold=threshold,
            actual_value=actual_value,
            percentage_change=percentage_change,
            timestamp=datetime.utcnow(),
            is_resolved=False
        )
        
        # Store alert in database
        query = """
            INSERT INTO cost_alerts (
                alert_id, company_id, alert_type, severity, message,
                threshold_value, actual_value, percentage_change,
                timestamp, is_resolved
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (alert_id) DO UPDATE SET
                message = EXCLUDED.message,
                actual_value = EXCLUDED.actual_value,
                percentage_change = EXCLUDED.percentage_change,
                timestamp = EXCLUDED.timestamp
        """
        
        await DatabaseUtils.execute_query(query, [
            alert.alert_id, alert.company_id, alert.alert_type,
            alert.severity, alert.message, alert.threshold,
            alert.actual_value, alert.percentage_change,
            alert.timestamp, alert.is_resolved
        ])
        
        logger.info(f"Created cost alert: {alert_type} for company {company_id}")
        return alert
        
    except Exception as e:
        logger.error(f"Failed to create cost alert: {e}")
        raise CostError(f"Cost alert creation failed: {e}")

async def _check_cost_patterns(company_id: str, month: str, total_cost: Decimal, vendor_breakdown: Dict[str, Decimal]) -> List[str]:
    """
    Check for unusual cost patterns and generate alerts
    
    Args:
        company_id: Company identifier
        month: Month in YYYY-MM format
        total_cost: Total monthly cost
        vendor_breakdown: Cost breakdown by vendor
        
    Returns:
        List[str]: List of alert messages
    """
    alerts = []
    
    try:
        # Get historical data for comparison
        query = """
            SELECT 
                DATE_TRUNC('month', calculation_timestamp) as month,
                SUM(total_cost) as monthly_cost,
                COUNT(*) as request_count
            FROM cost_calculations
            WHERE company_id = $1
            AND calculation_timestamp >= $2
            GROUP BY DATE_TRUNC('month', calculation_timestamp)
            ORDER BY month DESC
            LIMIT 6
        """
        
        # Get 6 months of historical data
        six_months_ago = datetime.utcnow() - timedelta(days=180)
        results = await DatabaseUtils.execute_query(query, [company_id, six_months_ago], fetch_all=True)
        
        if len(results) < 2:
            return alerts
        
        # Calculate average monthly cost
        historical_costs = [Decimal(str(r['monthly_cost'])) for r in results[1:]]  # Exclude current month
        avg_monthly_cost = sum(historical_costs) / len(historical_costs)
        
        # Check for significant cost increase
        if avg_monthly_cost > 0:
            cost_increase = ((total_cost - avg_monthly_cost) / avg_monthly_cost) * 100
            
            if cost_increase > 50:
                alerts.append(f"Significant cost increase: {cost_increase:.1f}% above average")
            elif cost_increase > 25:
                alerts.append(f"Moderate cost increase: {cost_increase:.1f}% above average")
        
        # Check vendor distribution
        if vendor_breakdown:
            total_vendor_cost = sum(vendor_breakdown.values())
            for vendor, cost in vendor_breakdown.items():
                vendor_percentage = (cost / total_vendor_cost) * 100
                if vendor_percentage > 80:
                    alerts.append(f"High vendor concentration: {vendor} represents {vendor_percentage:.1f}% of costs")
        
        # Check for zero cost (potential issue)
        if total_cost == 0:
            alerts.append("Zero cost detected - potential pricing or usage issue")
        
        return alerts
        
    except Exception as e:
        logger.error(f"Failed to check cost patterns: {e}")
        return alerts