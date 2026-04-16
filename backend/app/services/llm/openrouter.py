"""OpenRouter LLM provider implementation."""

import os
import httpx
from typing import Optional

from app.config import get_settings
from app.services.llm.base import LLMProvider, LLMResponse


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
        # Store explicit values if provided, otherwise None to read dynamically
        self._explicit_api_key = api_key
        self._explicit_model = model
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
        self._cached_api_key: Optional[str] = None
    
    @property
    def api_key(self) -> str:
        """Get API key from explicit value or current settings."""
        if self._explicit_api_key:
            return self._explicit_api_key
        # Read directly from environment (which is updated immediately) or fall back to settings
        # This ensures we get the latest value without relying on cached Settings
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            # Fall back to settings if not in environment
            get_settings.cache_clear()  # Clear cache to get fresh settings
            current_settings = get_settings()
            api_key = current_settings.openrouter_api_key
        if not api_key:
            raise ValueError("OpenRouter API key is required")
        return api_key
    
    @property
    def model(self) -> str:
        """Get model from explicit value or current settings."""
        if self._explicit_model:
            return self._explicit_model
        # Read directly from environment (which is updated immediately) or fall back to settings
        # This ensures we get the latest value without relying on cached Settings
        model = os.environ.get("OPENROUTER_MODEL")
        if not model:
            # Fall back to settings if not in environment
            get_settings.cache_clear()  # Clear cache to get fresh settings
            current_settings = get_settings()
            model = current_settings.openrouter_model
        return model or "anthropic/claude-3.5-sonnet"  # Default fallback
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client, recreating if API key changed."""
        current_api_key = self.api_key
        
        # Recreate client if API key changed
        if self._client is None or self._cached_api_key != current_api_key:
            # Close old client if it exists
            if self._client is not None:
                # Note: We can't await here, but the client will be closed when garbage collected
                # or we can schedule it to close. For now, we'll just recreate it.
                pass
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {current_api_key}",
                    "HTTP-Referer": "https://github.com/augustus",
                    "X-Title": "Augustus",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
            self._cached_api_key = current_api_key
        
        return self._client
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        briefing_id: Optional[str] = None,
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
            briefing_id=briefing_id,
        )
    
    async def generate_conversation(
        self,
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0.7,
        briefing_id: Optional[str] = None,
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

        # Use cancellable_await to allow immediate abort on cancellation
        if briefing_id:
            from app.services.cancellation import cancellable_await
            response = await cancellable_await(
                self.client.post("/chat/completions", json=payload),
                briefing_id,
            )
        else:
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


def reset_llm_provider():
    """Reset the LLM provider singleton to force recreation with new settings."""
    global _provider
    if _provider is not None:
        # Clear cached API key so client will be recreated with new settings
        _provider._cached_api_key = None
        # Close the existing client if it exists
        if _provider._client is not None:
            # Schedule client close (can't await in sync function)
            # The client will be properly closed when the provider is garbage collected
            _provider._client = None
        _provider = None

