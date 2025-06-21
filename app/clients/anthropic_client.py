import anthropic
import os

class AnthropicClient:
    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)

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
            
            # Calculate tokens and cost
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            
            # Basic cost calculation (you might want to make this more sophisticated)
            cost = (prompt_tokens * 0.000015) + (completion_tokens * 0.000075)  # Example rates
            
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