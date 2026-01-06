"""Base personality class."""

from abc import ABC, abstractmethod
from typing import Optional


class Personality(ABC):
    """Base class for cast member personalities."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of this personality."""
        pass
    
    @property
    @abstractmethod
    def core_trait(self) -> str:
        """The core trait that defines this personality."""
        pass
    
    @property
    @abstractmethod
    def voice(self) -> str:
        """How this personality speaks."""
        pass
    
    @property
    @abstractmethod
    def role(self) -> str:
        """The role this personality plays in the briefing."""
        pass
    
    @property
    @abstractmethod
    def personality_params(self) -> str:
        """Personality parameters (confidence, empathy, etc.)."""
        pass
    
    def get_description(self) -> dict[str, str]:
        """Get the full personality description as a dictionary.
        
        Returns:
            Dictionary with core_trait, voice, role, and personality_params
        """
        return {
            "core_trait": self.core_trait,
            "voice": self.voice,
            "role": self.role,
            "personality_params": self.personality_params,
        }
    
    def get_system_prompt_addition(self, cast_member_name: str, position: int, total_hosts: int) -> str:
        """Get additional system prompt instructions specific to this personality.
        
        This allows personalities to have a greater impact on how cast members act.
        Override this method to add personality-specific instructions.
        
        Args:
            cast_member_name: The name of the cast member
            position: Position in the cast (0-based)
            total_hosts: Total number of hosts in the cast
            
        Returns:
            Additional prompt text to append to the system prompt
        """
        return ""
    
    def get_behavioral_guidelines(self) -> list[str]:
        """Get behavioral guidelines specific to this personality.
        
        Returns:
            List of behavioral guideline strings
        """
        return []


















