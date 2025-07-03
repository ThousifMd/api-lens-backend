import httpx
import os
import logging
from app.services.pricing import PricingService

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        self.base_url = "https://api.openai.com/v1/chat/completions"

    async def generate(self, model: str, prompt: str, extra_params: dict = None):
        try:
            # Set default parameters
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }
            if extra_params:
                params.update(extra_params)

            # Build headers with auth
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Make the API call using httpx.AsyncClient
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=params, headers=headers)
                response.raise_for_status()
                data = response.json()

            # Extract tokens and calculate cost using dynamic pricing
            prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
            completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
            
            # Use PricingService for accurate cost calculation
            cost_result = await PricingService.calculate_cost(
                vendor="openai",
                model=model,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens
            )
            cost = cost_result.get("total_cost", 0.0)

            logger.info(f"OpenAI API call successful. Prompt tokens: {prompt_tokens}, Completion tokens: {completion_tokens}, Cost: {cost}")

            return {
                "content": data["choices"][0]["message"]["content"],
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost
            }
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise Exception(f"OpenAI API error: {str(e)}")
    
    async def chat_completion(self, messages: list, model: str, temperature: float = 0.7, max_tokens: int = None, stream: bool = False):
        """Chat completion method for proxy API"""
        try:
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            if stream:
                params["stream"] = stream

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=params, headers=headers)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"OpenAI chat completion error: {str(e)}")
            raise Exception(f"OpenAI chat completion error: {str(e)}")
    
    async def generate_image(self, prompt: str, model: str = "dall-e-3", size: str = "1024x1024", quality: str = "standard", style: str = "vivid", n: int = 1):
        """Generate images using DALL-E"""
        try:
            # Validate input parameters
            if not prompt or not prompt.strip():
                raise ValueError("Prompt cannot be empty")
            
            params = {
                "prompt": prompt.strip(),
                "model": model,
                "size": size,
                "quality": quality,
                "style": style,
                "n": n
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            image_url = "https://api.openai.com/v1/images/generations"
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(image_url, json=params, headers=headers)
                
                # Better error handling
                if response.status_code != 200:
                    error_detail = response.text
                    logger.error(f"OpenAI API returned {response.status_code}: {error_detail}")
                    raise Exception(f"OpenAI API error {response.status_code}: {error_detail}")
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"OpenAI image generation successful: {len(result.get('data', []))} images generated")
                return result

        except httpx.TimeoutException:
            logger.error("OpenAI image generation timeout")
            raise Exception("OpenAI image generation timeout - request took too long")
        except httpx.RequestError as e:
            logger.error(f"OpenAI image generation request error: {str(e)}")
            raise Exception(f"OpenAI image generation request error: {str(e)}")
        except Exception as e:
            logger.error(f"OpenAI image generation error: {str(e)}")
            raise Exception(f"OpenAI image generation error: {str(e)}") 