import anthropic
import os
from ..config import get_settings
from ..services.pricing import PricingService

class AnthropicClient:
    def __init__(self):
        # Try getting from settings first, then environment
        settings = get_settings()
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', None) or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables or settings")
        
        # Validate API key format
        if not self.api_key.startswith('sk-ant-'):
            raise ValueError("Invalid Anthropic API key format - must start with 'sk-ant-'")
        
        # Initialize with just the API key - no extra params that might cause issues
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            # Remove any problematic parameters
        )
        
        # Flag to track if API key has been validated
        self._key_validated = False

    async def generate(self, model: str, prompt: str, extra_params: dict = None):
        try:
            # Set default parameters
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.7,
            }
            
            # Update with any extra parameters
            if extra_params:
                params.update(extra_params)

            # Make the API call
            response = await self.client.messages.create(**params)
            
            # Calculate tokens and cost using dynamic pricing
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            
            # Use PricingService for accurate cost calculation
            cost_result = await PricingService.calculate_cost(
                vendor="anthropic",
                model=model,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens
            )
            cost = cost_result.get("total_cost", 0.0)
            
            return {
                "content": response.content[0].text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost
            }
            
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")
    
    async def chat_completion(self, messages: list, model: str, temperature: float = 0.7, max_tokens: int = None, stream: bool = False):
        """Chat completion method for proxy API"""
        try:
            params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens or 1000,
                "temperature": temperature,
            }
            
            if stream:
                params["stream"] = stream

            response = await self.client.messages.create(**params)
            
            # Convert to OpenAI-compatible format
            return {
                "choices": [{
                    "message": {
                        "content": response.content[0].text,
                        "role": "assistant"
                    }
                }],
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            }

        except Exception as e:
            raise Exception(f"Anthropic chat completion error: {str(e)}")
    
    async def generate_image(self, prompt: str, model: str = "claude-3-5-sonnet-20241022", **kwargs):
        """Anthropic doesn't generate images, but can provide detailed descriptions"""
        try:
            # Validate input
            if not prompt or not prompt.strip():
                raise ValueError("Prompt cannot be empty")
            
            # Generate a detailed description of what the image would look like
            description_prompt = f"Provide a detailed visual description of: {prompt.strip()}. Describe it as if you were creating instructions for an artist to paint this scene. Include colors, composition, lighting, mood, and artistic style details."
            
            params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt}],
                "max_tokens": 500,
                "temperature": 0.7,
            }

            # Verify client is properly initialized
            if not self.client:
                raise Exception("Anthropic client not properly initialized")
            
            if not self.api_key:
                raise Exception("Anthropic API key not available")

            response = await self.client.messages.create(**params)
            
            # Return in a format similar to image generation APIs
            return {
                "data": [{
                    "description": response.content[0].text,
                    "prompt": prompt,
                    "model": model,
                    "type": "text_description"
                }],
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                }
            }

        except anthropic.AuthenticationError as e:
            error_msg = f"Anthropic API authentication failed. Please verify your API key is valid and active. Error: {str(e)}"
            raise Exception(error_msg)
        except anthropic.RateLimitError as e:
            raise Exception(f"Anthropic API rate limit exceeded: {str(e)}")
        except anthropic.APIError as e:
            raise Exception(f"Anthropic API error: {str(e)}")
        except Exception as e:
            raise Exception(f"Anthropic image description error: {str(e)}") 