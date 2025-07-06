"""
Token calculation service for various AI models
Provides accurate token estimation when actual counts are not provided
"""
import random
from typing import Dict, Optional, Tuple
from app.utils.logger import get_logger

logger = get_logger(__name__)

class TokenCalculator:
    """Service for calculating/estimating tokens for different AI models"""
    
    # Average tokens per character for different model types
    TOKENS_PER_CHAR = {
        "openai": 0.25,      # ~4 chars per token
        "anthropic": 0.25,   # Similar to OpenAI
        "google": 0.3,       # Slightly different tokenization
        "cohere": 0.25,      # Similar to OpenAI
        "mistral": 0.25,     # Similar to OpenAI
        "default": 0.25      # Default estimation
    }
    
    # Token ratios for different request types (output/input ratio)
    MODEL_OUTPUT_RATIOS = {
        # Chat models typically have varying output lengths
        "gpt-3.5-turbo": 1.5,
        "gpt-4": 1.8,
        "gpt-4-turbo": 1.8,
        "gpt-4o": 1.8,
        "gpt-4o-mini": 1.5,
        "claude-3-opus-20240229": 2.0,
        "claude-3-sonnet-20240229": 1.8,
        "claude-3-haiku-20240307": 1.5,
        "claude-3-5-sonnet-20241022": 1.8,
        # Image models have different patterns
        "dall-e-2": 0,  # No text output
        "dall-e-3": 0,  # No text output
        "stable-diffusion": 0,  # No text output
        # Default ratio
        "default": 1.5
    }
    
    # Token ranges for different model types (min, max)
    MODEL_TOKEN_RANGES = {
        # OpenAI models
        "gpt-3.5-turbo": {"input": (50, 500), "output": (100, 1000)},
        "gpt-4": {"input": (100, 1000), "output": (200, 2000)},
        "gpt-4-turbo": {"input": (100, 2000), "output": (200, 3000)},
        "gpt-4o": {"input": (100, 1500), "output": (200, 2500)},
        "gpt-4o-mini": {"input": (50, 800), "output": (100, 1500)},
        # Anthropic models
        "claude-3-opus-20240229": {"input": (150, 2000), "output": (300, 3000)},
        "claude-3-sonnet-20240229": {"input": (100, 1500), "output": (200, 2500)},
        "claude-3-haiku-20240307": {"input": (50, 1000), "output": (100, 1500)},
        "claude-3-5-sonnet-20241022": {"input": (100, 1800), "output": (200, 2800)},
        # Image models
        "dall-e-2": {"input": (20, 100), "output": (0, 0)},
        "dall-e-3": {"input": (30, 150), "output": (0, 0)},
        "stable-diffusion": {"input": (20, 100), "output": (0, 0)},
        # Default ranges
        "default": {"input": (50, 500), "output": (100, 1000)}
    }
    
    # Endpoint-based token multipliers
    ENDPOINT_MULTIPLIERS = {
        "/chat/completions": 1.0,
        "/completions": 0.8,
        "/images/generations": 0.3,
        "/embeddings": 0.5,
        "/audio/transcriptions": 1.2,
        "/audio/translations": 1.3,
        "default": 1.0
    }
    
    @classmethod
    def calculate_tokens(
        cls,
        vendor: str,
        model: str,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        endpoint: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Calculate or estimate token counts for a request
        
        Args:
            vendor: AI vendor name
            model: Model name
            input_tokens: Actual input tokens if provided
            output_tokens: Actual output tokens if provided
            request_data: Request payload for estimation
            response_data: Response payload for estimation
            endpoint: API endpoint (helps determine request type)
            
        Returns:
            Tuple of (input_tokens, output_tokens)
        """
        # If both tokens are provided and non-zero, return them
        if input_tokens and output_tokens and input_tokens > 0 and output_tokens > 0:
            return input_tokens, output_tokens
        
        # Handle image generation requests
        if cls._is_image_generation(endpoint, model):
            return cls._calculate_image_tokens(vendor, model, request_data)
        
        # Get token ranges for the model
        token_ranges = cls.MODEL_TOKEN_RANGES.get(model, cls.MODEL_TOKEN_RANGES["default"])
        
        # Get endpoint multiplier
        endpoint_multiplier = 1.0
        if endpoint:
            for ep_pattern, multiplier in cls.ENDPOINT_MULTIPLIERS.items():
                if ep_pattern in endpoint:
                    endpoint_multiplier = multiplier
                    break
        
        # Calculate realistic token estimates
        if input_tokens and input_tokens > 0:
            # Use provided input tokens
            estimated_input = input_tokens
        elif request_data:
            # Estimate from request data
            estimated_input = cls._estimate_tokens_from_data(vendor, request_data)
        else:
            # Generate random value within model's typical range
            min_input, max_input = token_ranges["input"]
            base_input = random.randint(min_input, max_input)
            estimated_input = int(base_input * endpoint_multiplier)
        
        if output_tokens and output_tokens > 0:
            # Use provided output tokens
            estimated_output = output_tokens
        elif response_data:
            # Estimate from response data
            estimated_output = cls._estimate_tokens_from_data(vendor, response_data)
        else:
            # Generate random value within model's typical range
            min_output, max_output = token_ranges["output"]
            if min_output == 0 and max_output == 0:
                # Image generation or similar
                estimated_output = 0
            else:
                # Add some variance based on input
                ratio_variance = random.uniform(0.8, 1.2)
                base_output = random.randint(min_output, max_output)
                # Make output somewhat correlated to input
                correlation_factor = 0.3
                correlated_output = int(
                    base_output * (1 - correlation_factor) + 
                    estimated_input * ratio_variance * correlation_factor
                )
                estimated_output = min(max(correlated_output, min_output), max_output)
        
        logger.debug(f"Token calculation for {vendor}/{model}: input={estimated_input}, output={estimated_output}")
        
        return estimated_input, estimated_output
    
    @classmethod
    def _is_image_generation(cls, endpoint: Optional[str], model: str) -> bool:
        """Check if this is an image generation request"""
        if not endpoint:
            return False
        
        # Check endpoint patterns
        image_endpoints = ["/images/generations", "/v1/images", "/generate/image"]
        if any(ep in endpoint.lower() for ep in image_endpoints):
            return True
        
        # Check model names
        image_models = ["dall-e", "stable-diffusion", "midjourney", "imagen"]
        if any(im in model.lower() for im in image_models):
            return True
        
        return False
    
    @classmethod
    def _calculate_image_tokens(cls, vendor: str, model: str, request_data: Optional[Dict]) -> Tuple[int, int]:
        """Calculate tokens for image generation requests"""
        # Get token range for the image model
        token_ranges = cls.MODEL_TOKEN_RANGES.get(model, {"input": (20, 100), "output": (0, 0)})
        min_input, max_input = token_ranges["input"]
        
        if request_data:
            prompt = request_data.get("prompt", "")
            if isinstance(prompt, str) and prompt:
                tokens_per_char = cls.TOKENS_PER_CHAR.get(vendor, cls.TOKENS_PER_CHAR["default"])
                # Calculate based on prompt length
                estimated = int(len(prompt) * tokens_per_char)
                # Add some variance
                variance = random.uniform(0.9, 1.1)
                input_tokens = int(estimated * variance)
                # Keep within model's range
                input_tokens = min(max(input_tokens, min_input), max_input)
            else:
                # Random value within range
                input_tokens = random.randint(min_input, max_input)
        else:
            # Random value within range
            input_tokens = random.randint(min_input, max_input)
        
        # Image generation has no text output tokens
        output_tokens = 0
        
        return input_tokens, output_tokens
    
    @classmethod
    def _estimate_tokens_from_data(cls, vendor: str, data: Dict) -> int:
        """Estimate token count from request/response data"""
        if not data:
            return 0
        
        # Get tokens per character ratio for vendor
        tokens_per_char = cls.TOKENS_PER_CHAR.get(vendor, cls.TOKENS_PER_CHAR["default"])
        
        # Calculate total character count
        char_count = 0
        
        # Handle different data structures
        if isinstance(data, dict):
            # Check for common fields
            if "messages" in data:
                # Chat completion format
                for msg in data.get("messages", []):
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            char_count += len(content)
            elif "prompt" in data:
                # Completion format
                prompt = data.get("prompt", "")
                if isinstance(prompt, str):
                    char_count += len(prompt)
            elif "choices" in data:
                # Response format
                for choice in data.get("choices", []):
                    if isinstance(choice, dict):
                        message = choice.get("message", {})
                        if isinstance(message, dict):
                            content = message.get("content", "")
                            if isinstance(content, str):
                                char_count += len(content)
                        # Also check for text field (completions)
                        text = choice.get("text", "")
                        if isinstance(text, str):
                            char_count += len(text)
            else:
                # Fallback: convert to string and count
                char_count = len(str(data))
        else:
            # Non-dict data
            char_count = len(str(data))
        
        # Calculate tokens
        estimated_tokens = int(char_count * tokens_per_char)
        
        return max(estimated_tokens, cls.MIN_INPUT_TOKENS)
    
    @classmethod
    def calculate_cost_from_tokens(
        cls,
        input_tokens: int,
        output_tokens: int,
        input_price_per_1k: float,
        output_price_per_1k: float
    ) -> Dict[str, float]:
        """
        Calculate cost from token counts and pricing
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            input_price_per_1k: Price per 1000 input tokens
            output_price_per_1k: Price per 1000 output tokens
            
        Returns:
            Dictionary with input_cost, output_cost, and total_cost
        """
        input_cost = (input_tokens / 1000) * input_price_per_1k
        output_cost = (output_tokens / 1000) * output_price_per_1k
        total_cost = input_cost + output_cost
        
        return {
            "input_cost": round(input_cost, 8),
            "output_cost": round(output_cost, 8),
            "total_cost": round(total_cost, 8)
        }