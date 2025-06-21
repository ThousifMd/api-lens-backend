"""
API Lens Python SDK - Vendor Clients

This module provides vendor-specific clients that maintain compatibility
with existing AI provider SDKs while routing through API Lens.
"""

from typing import Optional, Dict, Any, List, Union, AsyncIterator, Iterator
from datetime import datetime
import json
import httpx

from .exceptions import APILensError, VendorError


class BaseVendorClient:
    """Base class for vendor-specific clients"""
    
    def __init__(self, parent_client, vendor: str, async_mode: bool = False):
        self.parent_client = parent_client
        self.vendor = vendor
        self.async_mode = async_mode
        self.base_path = f"/proxy/{vendor}"
    
    def _build_url(self, path: str) -> str:
        """Build vendor-specific URL"""
        return self.parent_client._build_url(f"{self.base_path}{path}")
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make request through parent client"""
        if self.async_mode:
            raise RuntimeError("Use async methods with AsyncClient")
        return self.parent_client._request(method, f"{self.base_path}{path}", **kwargs)
    
    async def _arequest(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make async request through parent client"""
        if not self.async_mode:
            raise RuntimeError("Use sync methods with Client")
        return await self.parent_client._request(method, f"{self.base_path}{path}", **kwargs)


class OpenAIClient(BaseVendorClient):
    """OpenAI-compatible client that routes through API Lens"""
    
    def __init__(self, parent_client, async_mode: bool = False):
        super().__init__(parent_client, "openai", async_mode)
        
        # Initialize sub-clients
        self.chat = OpenAIChatClient(self)
        self.completions = OpenAICompletionsClient(self)
        self.embeddings = OpenAIEmbeddingsClient(self)
        self.images = OpenAIImagesClient(self)
        self.models = OpenAIModelsClient(self)
    
    def create_chat_completion(self, **kwargs) -> Dict[str, Any]:
        """Create chat completion (legacy method)"""
        return self.chat.completions.create(**kwargs)
    
    async def acreate_chat_completion(self, **kwargs) -> Dict[str, Any]:
        """Async create chat completion (legacy method)"""
        return await self.chat.completions.acreate(**kwargs)


class OpenAIChatClient:
    """OpenAI Chat API client"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
        self.completions = OpenAIChatCompletionsClient(openai_client)


class OpenAIChatCompletionsClient:
    """OpenAI Chat Completions API"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
    
    def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        stop: Optional[Union[str, List[str]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create chat completion"""
        if stream:
            return self._create_stream(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                frequency_penalty=frequency_penalty,
                presence_penalty=presence_penalty,
                stop=stop,
                **kwargs
            )
        
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        # Add optional parameters
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if stop is not None:
            payload["stop"] = stop
        
        return self.openai_client._request("POST", "/chat/completions", json=payload)
    
    async def acreate(self, **kwargs) -> Dict[str, Any]:
        """Async create chat completion"""
        if kwargs.get("stream"):
            return self._acreate_stream(**kwargs)
        
        # Remove stream parameter and handle normally
        stream = kwargs.pop("stream", False)
        payload = dict(kwargs)
        
        return await self.openai_client._arequest("POST", "/chat/completions", json=payload)
    
    def _create_stream(self, **kwargs) -> Iterator[Dict[str, Any]]:
        """Create streaming chat completion"""
        if self.openai_client.async_mode:
            raise RuntimeError("Use async streaming methods with AsyncClient")
        
        # Remove stream parameter for API call
        payload = dict(kwargs)
        payload["stream"] = True
        
        # Make streaming request
        url = self.openai_client._build_url("/chat/completions")
        
        with httpx.stream(
            "POST",
            url,
            json=payload,
            headers=self.openai_client.parent_client.headers,
            timeout=self.openai_client.parent_client.timeout
        ) as response:
            if response.status_code != 200:
                raise VendorError(f"OpenAI streaming error: {response.status_code}")
            
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data.strip() == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue
    
    async def _acreate_stream(self, **kwargs) -> AsyncIterator[Dict[str, Any]]:
        """Create async streaming chat completion"""
        if not self.openai_client.async_mode:
            raise RuntimeError("Use sync streaming methods with Client")
        
        payload = dict(kwargs)
        payload["stream"] = True
        
        url = self.openai_client._build_url("/chat/completions")
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                headers=self.openai_client.parent_client.headers,
                timeout=self.openai_client.parent_client.timeout
            ) as response:
                if response.status_code != 200:
                    raise VendorError(f"OpenAI streaming error: {response.status_code}")
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue


class OpenAICompletionsClient:
    """OpenAI Text Completions API"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
    
    def create(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Create text completion"""
        payload = {"model": model, "prompt": prompt, **kwargs}
        return self.openai_client._request("POST", "/completions", json=payload)
    
    async def acreate(self, model: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Async create text completion"""
        payload = {"model": model, "prompt": prompt, **kwargs}
        return await self.openai_client._arequest("POST", "/completions", json=payload)


class OpenAIEmbeddingsClient:
    """OpenAI Embeddings API"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
    
    def create(self, model: str, input: Union[str, List[str]], **kwargs) -> Dict[str, Any]:
        """Create embeddings"""
        payload = {"model": model, "input": input, **kwargs}
        return self.openai_client._request("POST", "/embeddings", json=payload)
    
    async def acreate(self, model: str, input: Union[str, List[str]], **kwargs) -> Dict[str, Any]:
        """Async create embeddings"""
        payload = {"model": model, "input": input, **kwargs}
        return await self.openai_client._arequest("POST", "/embeddings", json=payload)


class OpenAIImagesClient:
    """OpenAI Images API"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
    
    def generate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate images"""
        payload = {"prompt": prompt, **kwargs}
        return self.openai_client._request("POST", "/images/generations", json=payload)
    
    async def agenerate(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Async generate images"""
        payload = {"prompt": prompt, **kwargs}
        return await self.openai_client._arequest("POST", "/images/generations", json=payload)


class OpenAIModelsClient:
    """OpenAI Models API"""
    
    def __init__(self, openai_client):
        self.openai_client = openai_client
    
    def list(self) -> Dict[str, Any]:
        """List available models"""
        return self.openai_client._request("GET", "/models")
    
    async def alist(self) -> Dict[str, Any]:
        """Async list available models"""
        return await self.openai_client._arequest("GET", "/models")
    
    def retrieve(self, model_id: str) -> Dict[str, Any]:
        """Retrieve model details"""
        return self.openai_client._request("GET", f"/models/{model_id}")
    
    async def aretrieve(self, model_id: str) -> Dict[str, Any]:
        """Async retrieve model details"""
        return await self.openai_client._arequest("GET", f"/models/{model_id}")


class AnthropicClient(BaseVendorClient):
    """Anthropic-compatible client that routes through API Lens"""
    
    def __init__(self, parent_client, async_mode: bool = False):
        super().__init__(parent_client, "anthropic", async_mode)
        self.messages = AnthropicMessagesClient(self)
    
    def create_message(self, **kwargs) -> Dict[str, Any]:
        """Create message (legacy method)"""
        return self.messages.create(**kwargs)
    
    async def acreate_message(self, **kwargs) -> Dict[str, Any]:
        """Async create message (legacy method)"""
        return await self.messages.acreate(**kwargs)


class AnthropicMessagesClient:
    """Anthropic Messages API"""
    
    def __init__(self, anthropic_client):
        self.anthropic_client = anthropic_client
    
    def create(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """Create message"""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if stop_sequences is not None:
            payload["stop_sequences"] = stop_sequences
        if stream:
            payload["stream"] = stream
        
        return self.anthropic_client._request("POST", "/messages", json=payload)
    
    async def acreate(self, **kwargs) -> Dict[str, Any]:
        """Async create message"""
        return await self.anthropic_client._arequest("POST", "/messages", json=kwargs)


class GoogleClient(BaseVendorClient):
    """Google AI-compatible client that routes through API Lens"""
    
    def __init__(self, parent_client, async_mode: bool = False):
        super().__init__(parent_client, "google", async_mode)
    
    def generate_content(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        generation_config: Optional[Dict[str, Any]] = None,
        safety_settings: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate content"""
        payload = {
            "contents": contents,
            **kwargs
        }
        
        if generation_config:
            payload["generationConfig"] = generation_config
        if safety_settings:
            payload["safetySettings"] = safety_settings
        
        # Google API expects model in URL path
        return self._request("POST", f"/v1/models/{model}:generateContent", json=payload)
    
    async def agenerate_content(
        self,
        model: str,
        contents: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """Async generate content"""
        payload = {"contents": contents, **kwargs}
        return await self._arequest("POST", f"/v1/models/{model}:generateContent", json=payload)
    
    def list_models(self) -> Dict[str, Any]:
        """List available models"""
        return self._request("GET", "/v1/models")
    
    async def alist_models(self) -> Dict[str, Any]:
        """Async list available models"""
        return await self._arequest("GET", "/v1/models")


# Legacy compatibility classes for drop-in replacement
class OpenAI:
    """Legacy OpenAI compatibility class"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        from .client import Client
        self.client = Client(api_key=api_key, base_url=base_url or "https://api.apilens.dev")
        
    @property
    def chat(self):
        return self.client.openai.chat
    
    @property
    def completions(self):
        return self.client.openai.completions
    
    @property 
    def embeddings(self):
        return self.client.openai.embeddings
    
    @property
    def images(self):
        return self.client.openai.images
    
    @property
    def models(self):
        return self.client.openai.models


class Anthropic:
    """Legacy Anthropic compatibility class"""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        from .client import Client
        self.client = Client(api_key=api_key, base_url=base_url or "https://api.apilens.dev")
    
    @property
    def messages(self):
        return self.client.anthropic.messages


# Convenience functions for quick setup
def setup_openai_proxy(api_key: str, base_url: str = "https://api.apilens.dev") -> OpenAI:
    """Set up OpenAI proxy through API Lens"""
    return OpenAI(api_key=api_key, base_url=base_url)


def setup_anthropic_proxy(api_key: str, base_url: str = "https://api.apilens.dev") -> Anthropic:
    """Set up Anthropic proxy through API Lens"""
    return Anthropic(api_key=api_key, base_url=base_url)