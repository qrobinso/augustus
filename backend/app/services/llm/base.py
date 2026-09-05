"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    usage: dict
    raw_response: Optional[dict] = None
    finish_reason: Optional[str] = None  # "length" means output hit max_tokens
    annotations: list = field(default_factory=list)  # e.g. url_citation entries from web search plugins


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    supports_web_search_plugin = False

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
        briefing_id: Optional[str] = None,
        plugins: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Generate text from prompt.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def generate_conversation(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
        briefing_id: Optional[str] = None,
        plugins: Optional[list[dict]] = None,
    ) -> LLMResponse:
        """Generate response for a conversation.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            LLMResponse with generated content
        """
        pass
    
    @abstractmethod
    async def close(self):
        """Close any open connections."""
        pass

