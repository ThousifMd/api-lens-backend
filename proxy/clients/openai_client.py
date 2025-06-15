import httpx
import os
import logging

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
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

            # Extract tokens and calculate cost
            prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
            completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
            # Basic cost calculation (you might want to make this more sophisticated)
            cost = (prompt_tokens * 0.00001) + (completion_tokens * 0.00002)

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