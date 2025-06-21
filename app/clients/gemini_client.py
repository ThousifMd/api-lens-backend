import google.generativeai as genai
import os

class GeminiClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")
        genai.configure(api_key=self.api_key)

    async def generate(self, model: str, prompt: str, extra_params: dict = None):
        try:
            # Set default parameters
            params = {
                "model": model,
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generation_config": {
                    "temperature": 0.7,
                    "max_output_tokens": 1000,
                }
            }
            
            # Update with any extra parameters
            if extra_params:
                if "generation_config" in extra_params:
                    params["generation_config"].update(extra_params["generation_config"])
                else:
                    params["generation_config"].update(extra_params)

            # Make the API call
            model = genai.GenerativeModel(model_name=params["model"])
            response = await model.generate_content_async(
                contents=params["contents"],
                generation_config=params["generation_config"]
            )
            
            # Estimate tokens (Gemini doesn't provide exact token counts)
            # This is a rough estimation
            prompt_tokens = len(prompt.split()) * 1.3  # Approximate tokens per word
            completion_tokens = len(response.text.split()) * 1.3
            
            # Basic cost calculation (you might want to make this more sophisticated)
            cost = (prompt_tokens * 0.00001) + (completion_tokens * 0.00002)  # Example rates
            
            return {
                "content": response.text,
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "cost": cost
            }
            
        except Exception as e:
            raise Exception(f"Error generating content with Gemini: {str(e)}")
    
    async def chat_completion(self, messages: list, model: str, temperature: float = 0.7, max_tokens: int = None, stream: bool = False):
        """Chat completion method for proxy API"""
        try:
            # Convert OpenAI format messages to Gemini format
            contents = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })

            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens or 1000,
            }

            # Make the API call
            gemini_model = genai.GenerativeModel(model_name=model)
            response = await gemini_model.generate_content_async(
                contents=contents,
                generation_config=generation_config
            )
            
            # Estimate tokens
            total_input_text = " ".join([msg["content"] for msg in messages])
            prompt_tokens = int(len(total_input_text.split()) * 1.3)
            completion_tokens = int(len(response.text.split()) * 1.3)
            
            # Convert to OpenAI-compatible format
            return {
                "choices": [{
                    "message": {
                        "content": response.text,
                        "role": "assistant"
                    }
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            }

        except Exception as e:
            raise Exception(f"Gemini chat completion error: {str(e)}") 