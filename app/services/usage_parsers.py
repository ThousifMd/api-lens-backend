"""
Usage Data Parsers - Vendor-specific usage data parsing and normalization
Implements standardized parsing for OpenAI, Anthropic, Google/Gemini, and generic fallback parsers
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal

from ..utils.logger import get_logger
from .cost import UsageData, PricingModel

logger = get_logger(__name__)

@dataclass
class NormalizedUsageData:
    """Normalized usage data across all vendors"""
    vendor: str
    model: str
    input_units: int
    output_units: int
    pricing_model: PricingModel
    timestamp: datetime
    raw_usage: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class UsageParserError(Exception):
    """Base exception for usage parsing operations"""
    pass

def parse_openai_usage(response: dict) -> UsageData:
    """
    Parse OpenAI response to extract usage data
    OpenAI uses token-based pricing model
    
    Args:
        response: OpenAI API response dictionary
        
    Returns:
        UsageData: Parsed usage data
        
    Raises:
        UsageParserError: If parsing fails
    """
    try:
        usage = response.get('usage', {})
        
        if not usage:
            logger.warning("No usage data found in OpenAI response")
            return UsageData(
                vendor='openai',
                model=response.get('model', 'unknown'),
                input_units=0,
                output_units=0,
                timestamp=datetime.utcnow(),
                metadata={'raw_response': response}
            )
        
        # Extract token counts
        prompt_tokens = usage.get('prompt_tokens', 0)
        completion_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', prompt_tokens + completion_tokens)
        
        # Get model from response
        model = response.get('model', 'unknown')
        
        # Create metadata
        metadata = {
            'total_tokens': total_tokens,
            'raw_usage': usage,
            'pricing_model': 'tokens'
        }
        
        return UsageData(
            vendor='openai',
            model=model,
            input_units=prompt_tokens,
            output_units=completion_tokens,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to parse OpenAI usage: {e}")
        raise UsageParserError(f"OpenAI usage parsing failed: {e}")

def parse_anthropic_usage(response: dict) -> UsageData:
    """
    Parse Anthropic response to extract usage data
    Anthropic uses character-based pricing with token conversion
    
    Args:
        response: Anthropic API response dictionary
        
    Returns:
        UsageData: Parsed usage data with token conversion
        
    Raises:
        UsageParserError: If parsing fails
    """
    try:
        usage = response.get('usage', {})
        
        if not usage:
            logger.warning("No usage data found in Anthropic response")
            return UsageData(
                vendor='anthropic',
                model=response.get('model', 'unknown'),
                input_units=0,
                output_units=0,
                timestamp=datetime.utcnow(),
                metadata={'raw_response': response}
            )
        
        # Extract token counts (Anthropic provides tokens directly)
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        
        # Get model from response
        model = response.get('model', 'unknown')
        
        # Create metadata with character estimation
        metadata = {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'estimated_input_characters': input_tokens * 4,  # Rough estimation
            'estimated_output_characters': output_tokens * 4,
            'raw_usage': usage,
            'pricing_model': 'tokens'
        }
        
        return UsageData(
            vendor='anthropic',
            model=model,
            input_units=input_tokens,
            output_units=output_tokens,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to parse Anthropic usage: {e}")
        raise UsageParserError(f"Anthropic usage parsing failed: {e}")

def parse_google_usage(response: dict) -> UsageData:
    """
    Parse Google/Gemini response to extract usage data
    Google uses mixed pricing model (tokens for some models, characters for others)
    
    Args:
        response: Google/Gemini API response dictionary
        
    Returns:
        UsageData: Parsed usage data
        
    Raises:
        UsageParserError: If parsing fails
    """
    try:
        # Google/Gemini might not always provide usage data in the same format
        usage = response.get('usage', {})
        model = response.get('model', 'unknown')
        
        # Try to extract usage data from different possible locations
        input_units = 0
        output_units = 0
        
        if usage:
            # Standard usage format
            input_units = usage.get('prompt_tokens', usage.get('input_tokens', 0))
            output_units = usage.get('completion_tokens', usage.get('output_tokens', 0))
        else:
            # Fallback: estimate from content if available
            if 'candidates' in response and response['candidates']:
                content = response['candidates'][0].get('content', {})
                if 'parts' in content and content['parts']:
                    text = content['parts'][0].get('text', '')
                    output_units = int(len(text.split()) * 1.3)  # Rough token estimation
            
            # Estimate input tokens from metadata if available
            if 'prompt_feedback' in response:
                # This is a rough estimation - adjust based on actual Google API behavior
                input_units = response.get('estimated_input_tokens', 0)
        
        # Determine pricing model based on model name
        pricing_model = 'tokens'
        if any(x in model.lower() for x in ['text-bison', 'chat-bison']):
            pricing_model = 'characters'
            # Convert tokens to characters for character-based models
            if input_units > 0:
                input_units = input_units * 4  # Rough conversion
            if output_units > 0:
                output_units = output_units * 4
        
        # Create metadata
        metadata = {
            'raw_usage': usage,
            'pricing_model': pricing_model,
            'estimated': usage == {},
            'model_family': 'gemini' if 'gemini' in model.lower() else 'palm'
        }
        
        return UsageData(
            vendor='google',
            model=model,
            input_units=input_units,
            output_units=output_units,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to parse Google usage: {e}")
        raise UsageParserError(f"Google usage parsing failed: {e}")

def convert_characters_to_tokens(characters: int) -> int:
    """
    Convert character count to approximate token count
    Uses industry standard estimation of ~4 characters per token
    
    Args:
        characters: Number of characters
        
    Returns:
        int: Estimated token count
    """
    if characters <= 0:
        return 0
    
    # Standard conversion: approximately 4 characters per token
    tokens = max(1, int(characters / 4))
    return tokens

def convert_tokens_to_characters(tokens: int) -> int:
    """
    Convert token count to approximate character count
    Uses industry standard estimation of ~4 characters per token
    
    Args:
        tokens: Number of tokens
        
    Returns:
        int: Estimated character count
    """
    if tokens <= 0:
        return 0
    
    # Standard conversion: approximately 4 characters per token
    characters = tokens * 4
    return characters

def parse_generic_usage(response: dict, vendor: str) -> UsageData:
    """
    Generic fallback parser for unknown vendors
    Attempts to extract usage data using common patterns
    
    Args:
        response: API response dictionary
        vendor: Vendor name
        
    Returns:
        UsageData: Parsed usage data (may contain estimates)
        
    Raises:
        UsageParserError: If parsing fails completely
    """
    try:
        # Common usage field patterns
        usage_fields = ['usage', 'token_usage', 'consumption', 'billing']
        usage_data = None
        
        for field in usage_fields:
            if field in response:
                usage_data = response[field]
                break
        
        input_units = 0
        output_units = 0
        model = response.get('model', 'unknown')
        
        if usage_data:
            # Try common input token field names
            input_fields = ['prompt_tokens', 'input_tokens', 'input_units', 'request_tokens']
            output_fields = ['completion_tokens', 'output_tokens', 'output_units', 'response_tokens']
            
            for field in input_fields:
                if field in usage_data:
                    input_units = usage_data[field]
                    break
            
            for field in output_fields:
                if field in usage_data:
                    output_units = usage_data[field]
                    break
        
        # If no usage data found, try to estimate from content
        if input_units == 0 and output_units == 0:
            # Try to find response content
            content_fields = ['content', 'text', 'response', 'completion', 'answer']
            for field in content_fields:
                if field in response:
                    content = str(response[field])
                    output_units = int(len(content.split()) * 1.3)  # Rough token estimation
                    break
        
        # Create metadata
        metadata = {
            'vendor': vendor,
            'raw_usage': usage_data or {},
            'raw_response_keys': list(response.keys()),
            'parsing_method': 'generic_fallback',
            'estimated': True,
            'confidence': 'low'
        }
        
        logger.warning(f"Using generic parser for vendor '{vendor}' - results may be inaccurate")
        
        return UsageData(
            vendor=vendor,
            model=model,
            input_units=input_units,
            output_units=output_units,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        
    except Exception as e:
        logger.error(f"Failed to parse generic usage for vendor '{vendor}': {e}")
        raise UsageParserError(f"Generic usage parsing failed: {e}")

def normalize_usage_data(vendor: str, raw_usage: dict) -> NormalizedUsageData:
    """
    Normalize usage data across different vendors to a common format
    
    Args:
        vendor: Vendor name (openai, anthropic, google, etc.)
        raw_usage: Raw usage data from vendor API
        
    Returns:
        NormalizedUsageData: Normalized usage data
        
    Raises:
        UsageParserError: If normalization fails
    """
    try:
        vendor_lower = vendor.lower()
        
        # Parse vendor-specific usage data
        if vendor_lower == 'openai':
            usage_data = parse_openai_usage(raw_usage)
            pricing_model = PricingModel.TOKENS
        elif vendor_lower == 'anthropic':
            usage_data = parse_anthropic_usage(raw_usage)
            pricing_model = PricingModel.TOKENS
        elif vendor_lower in ['google', 'gemini']:
            usage_data = parse_google_usage(raw_usage)
            # Determine pricing model from model name
            model = raw_usage.get('model', '')
            if any(x in model.lower() for x in ['text-bison', 'chat-bison']):
                pricing_model = PricingModel.CHARACTERS
            else:
                pricing_model = PricingModel.TOKENS
        else:
            usage_data = parse_generic_usage(raw_usage, vendor)
            pricing_model = PricingModel.TOKENS  # Default assumption
        
        # Create normalized data
        normalized = NormalizedUsageData(
            vendor=usage_data.vendor,
            model=usage_data.model,
            input_units=usage_data.input_units,
            output_units=usage_data.output_units,
            pricing_model=pricing_model,
            timestamp=usage_data.timestamp,
            raw_usage=raw_usage,
            metadata=usage_data.metadata
        )
        
        logger.debug(f"Normalized usage data for {vendor}: {normalized.input_units} input, {normalized.output_units} output")
        
        return normalized
        
    except Exception as e:
        logger.error(f"Failed to normalize usage data for vendor '{vendor}': {e}")
        raise UsageParserError(f"Usage data normalization failed: {e}")

# Vendor parser registry for easy access
VENDOR_PARSERS = {
    'openai': parse_openai_usage,
    'anthropic': parse_anthropic_usage,
    'google': parse_google_usage,
    'gemini': parse_google_usage,  # Alias for Google
    'generic': parse_generic_usage
}

def get_parser_for_vendor(vendor: str):
    """
    Get the appropriate parser function for a vendor
    
    Args:
        vendor: Vendor name
        
    Returns:
        callable: Parser function for the vendor
    """
    vendor_lower = vendor.lower()
    return VENDOR_PARSERS.get(vendor_lower, parse_generic_usage)

def parse_usage_data(vendor: str, response: dict) -> UsageData:
    """
    Parse usage data using the appropriate vendor parser
    
    Args:
        vendor: Vendor name
        response: API response dictionary
        
    Returns:
        UsageData: Parsed usage data
    """
    parser = get_parser_for_vendor(vendor)
    if parser == parse_generic_usage:
        return parser(response, vendor)
    else:
        return parser(response)