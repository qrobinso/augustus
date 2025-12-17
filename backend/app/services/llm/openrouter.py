"""OpenRouter LLM provider implementation."""

import httpx
from typing import Optional

from app.config import get_settings
from app.services.llm.base import LLMProvider, LLMResponse

settings = get_settings()


def _log_separator(title: str):
    """Print a separator line for console logging."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


class OpenRouterProvider(LLMProvider):
    """OpenRouter API provider for multi-model access."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        self.api_key = api_key or settings.openrouter_api_key
        self.model = model or settings.openrouter_model
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        
        if not self.api_key:
            raise ValueError("OpenRouter API key is required")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/augustus",
                    "X-Title": "Augustus",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate text from prompt using OpenRouter."""
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        return await self.generate_conversation(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    
    async def generate_conversation(
        self,
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate response for a conversation."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Log the request
        _log_separator(f"LLM REQUEST to {self.model}")
        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            # Truncate long content for readability
            if len(content) > 2000:
                content = content[:2000] + f"\n... [truncated, {len(msg['content'])} chars total]"
            print(f"\n[{role}]:\n{content}")
        print(f"\nSettings: max_tokens={max_tokens}, temperature={temperature}")
        
        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        result_content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        # Log the response
        _log_separator("LLM RESPONSE")
        # Truncate long responses for readability
        display_content = result_content
        if len(display_content) > 3000:
            display_content = display_content[:3000] + f"\n... [truncated, {len(result_content)} chars total]"
        print(f"\n{display_content}")
        print(f"\nUsage: {usage}")
        print(f"{'='*60}\n")
        
        return LLMResponse(
            content=result_content,
            model=data.get("model", self.model),
            usage=usage,
            raw_response=data,
        )
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_provider: Optional[OpenRouterProvider] = None


def get_llm_provider() -> OpenRouterProvider:
    """Get or create LLM provider instance."""
    global _provider
    if _provider is None:
        _provider = OpenRouterProvider()
    return _provider

