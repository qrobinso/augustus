"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    usage: dict
    raw_response: Optional[dict] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
        briefing_id: Optional[str] = None,
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

