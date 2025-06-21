import os
from openai import OpenAI
from openai.types.chat import ChatCompletion
from typing import List, Dict, Any, Optional, Tuple
import json
import time
# --- Gemini (Google Generative AI) ---
import google.generativeai as genai
# --- Anthropic Claude ---
import anthropic

class OpenAIWrapper:
    def __init__(self, model: str, logger=None):
        self.model = model
        self.logger = logger
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        self.client = OpenAI(api_key=api_key)

    def chat_completion(self, messages: List[Dict[str, str]]) -> Tuple[Dict[str, Any], list]:
        start_time = time.time()
        # Prepare log data for 'before' call
        before_log = {
            'user_api_key': None,
            'vendor': 'openai',
            'model': self.model,
            'request_payload': messages,
            'response_payload': None,
            'log_type': 'before',
            'start_time': None
        }
        try:
            print(f"Debug - Messages: {json.dumps(messages)}")  # Debug print
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,  # Add some creativity to responses
                max_tokens=1000,  # Limit response length
            )
            print("Debug - Successfully received response from OpenAI API")  # Debug print
            # --- Cost Calculation ---
            # Pricing for GPT-4-0613 as of June 2024
            prompt_price_per_1k = 0.03  # USD per 1K prompt tokens
            completion_price_per_1k = 0.06  # USD per 1K completion tokens
            usage = response.usage
            prompt_tokens = usage.prompt_tokens or 0
            completion_tokens = usage.completion_tokens or 0
            total_tokens = usage.total_tokens or 0
            cost = ((prompt_tokens / 1000) * prompt_price_per_1k) + ((completion_tokens / 1000) * completion_price_per_1k)
            # Prepare log data for 'after' call
            after_log = {
                'user_api_key': None,
                'vendor': 'openai',
                'model': self.model,
                'request_payload': None,
                'response_payload': response.model_dump(),
                'log_type': 'after',
                'start_time': start_time,
                'cost': cost
            }
            return {
                "vendor": "openai",
                "model": self.model,
                "messages": messages,
                "response": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "cost_usd": cost
            }, [before_log, after_log]
        except Exception as e:
            error_msg = f"Error in OpenAI API call: {str(e)}"
            error_log = {
                'user_api_key': None,
                'vendor': 'openai',
                'model': self.model,
                'request_payload': None,
                'response_payload': error_msg,
                'log_type': 'after',
                'start_time': start_time
            }
            return {"error": error_msg}, [before_log, error_log]

class ClaudeWrapper:
    def __init__(self, model: str, logger=None):
        self.model = model
        self.logger = logger
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat_completion(self, messages):
        start_time = time.time()
        print(f"Debug - Using Claude model: {self.model}")  # Debug print
        before_log = {
            'user_api_key': None,
            'vendor': 'claude',
            'model': self.model,
            'request_payload': messages,
            'response_payload': None,
            'log_type': 'before',
            'start_time': None
        }
        try:
            # Convert OpenAI-style messages to Anthropic format
            system_prompt = None
            user_content = ""
            for msg in messages:
                if msg.get("role") == "system":
                    system_prompt = msg.get("content")
                elif msg.get("role") == "user":
                    user_content += msg.get("content", "") + "\n"
            # Create the message with or without system prompt
            message_params = {
                "model": self.model,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": user_content.strip()}]
            }
            print(f"Debug - Message params: {message_params}")  # Debug print
            if system_prompt and system_prompt.strip():
                message_params["system"] = system_prompt.strip()
            if "system" in message_params and not message_params["system"]:
                del message_params["system"]
            response = self.client.messages.create(**message_params)
            print("Claude API response.usage:", getattr(response, 'usage', None))
            print("Claude API response (raw):", response)
            prompt_price_per_1k = 15.00 / 1_000_000  # $15 per 1M tokens
            completion_price_per_1k = 75.00 / 1_000_000  # $75 per 1M tokens
            usage = response.usage
            prompt_tokens = usage.input_tokens if hasattr(usage, 'input_tokens') else None
            completion_tokens = usage.output_tokens if hasattr(usage, 'output_tokens') else None
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
            cost = ((prompt_tokens or 0) / 1000 * prompt_price_per_1k) + ((completion_tokens or 0) / 1000 * completion_price_per_1k)
            after_log = {
                'user_api_key': None,
                'vendor': 'claude',
                'model': self.model,
                'request_payload': None,
                'response_payload': {
                    "response": (
                        [tb.text for tb in response.content] if hasattr(response, 'content') and isinstance(response.content, list)
                        else str(response.content) if hasattr(response, 'content')
                        else str(response)
                    ),
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }
                },
                'log_type': 'after',
                'start_time': start_time,
                'cost': cost
            }
            print("Claude after_log:", after_log)
            return {
                "vendor": "claude",
                "model": self.model,
                "messages": messages,
                "response": response.content if hasattr(response, 'content') else str(response),
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "cost_usd": cost
            }, [before_log, after_log]
        except Exception as e:
            error_msg = f"Error in Claude API call: {str(e)}"
            error_log = {
                'user_api_key': None,
                'vendor': 'claude',
                'model': self.model,
                'request_payload': None,
                'response_payload': error_msg,
                'log_type': 'after',
                'start_time': start_time
            }
            return {"error": error_msg}, [before_log, error_log]

class GeminiWrapper:
    def __init__(self, model: str, logger=None):
        self.model = model
        self.logger = logger
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(self.model)

    def chat_completion(self, messages):
        start_time = time.time()
        before_log = {
            'user_api_key': None,
            'vendor': 'gemini',
            'model': self.model,
            'request_payload': messages,
            'response_payload': None,
            'log_type': 'before',
            'start_time': None
        }
        try:
            prompt = "\n".join([msg["content"] for msg in messages if msg["role"] == "user"])
            response = self.client.generate_content(prompt)
            prompt_price_per_1k = 0.0025  # $0.0025 per 1K input tokens
            completion_price_per_1k = 0.007  # $0.007 per 1K output tokens
            usage = response.usage_metadata if hasattr(response, 'usage_metadata') else None
            prompt_tokens = usage.prompt_token_count if usage and hasattr(usage, 'prompt_token_count') else None
            completion_tokens = usage.candidates_token_count if usage and hasattr(usage, 'candidates_token_count') else None
            total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
            cost = ((prompt_tokens or 0) / 1000 * prompt_price_per_1k) + ((completion_tokens or 0) / 1000 * completion_price_per_1k)
            after_log = {
                'user_api_key': None,
                'vendor': 'gemini',
                'model': self.model,
                'request_payload': None,
                'response_payload': {
                    "response": response.text if hasattr(response, 'text') else str(response),
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens
                    }
                },
                'log_type': 'after',
                'start_time': start_time,
                'cost': cost
            }
            return {
                "vendor": "gemini",
                "model": self.model,
                "messages": messages,
                "response": response.text if hasattr(response, 'text') else str(response),
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens
                },
                "cost_usd": cost
            }, [before_log, after_log]
        except Exception as e:
            error_msg = f"Error in Gemini API call: {str(e)}"
            error_log = {
                'user_api_key': None,
                'vendor': 'gemini',
                'model': self.model,
                'request_payload': None,
                'response_payload': error_msg,
                'log_type': 'after',
                'start_time': start_time
            }
            return {"error": error_msg}, [before_log, error_log] 