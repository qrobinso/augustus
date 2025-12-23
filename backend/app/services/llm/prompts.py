"""Shared prompt utilities for content generation.

This module contains shared constants and utilities used by the LLM agents.
Individual agent-specific prompts are now in their respective agent files.
"""

# Complexity level descriptions for prompts
COMPLEXITY_LEVELS = {
    1: {
        "name": "Casual",
        "description": "High school level",
        "style": """
- Use simple, everyday language that anyone can understand
- Avoid jargon and technical terms - if you must use them, explain them simply
- Use relatable analogies and examples from daily life
- Keep sentences short and punchy
- Think "explaining to a smart teenager"
- Be conversational and fun - like friends chatting over coffee
- Focus on the "so what" - why should someone care about this?""",
    },
    2: {
        "name": "Accessible",
        "description": "General audience",
        "style": """
- Use clear, straightforward language
- Minimize jargon - explain technical terms when needed
- Use helpful analogies to make concepts relatable
- Balance information with accessibility
- Think "quality journalism for a general audience"
- Keep it engaging and conversational""",
    },
    3: {
        "name": "Standard",
        "description": "Early college level",
        "style": """
- Use clear language with appropriate technical vocabulary
- Assume some familiarity with current events and basic concepts
- Balance depth with accessibility
- Include context and nuance
- Think "informed discussion between knowledgeable friends"
- Conversational but substantive""",
    },
    4: {
        "name": "Advanced",
        "description": "Professional/Graduate level",
        "style": """
- Use precise, technical language appropriate to the subject
- Assume background knowledge in relevant fields
- Dive deeper into nuances and implications
- Reference relevant frameworks, theories, or precedents
- Think "industry experts having a substantive discussion"
- More analytical and detailed""",
    },
    5: {
        "name": "Expert",
        "description": "PhD/Specialist level",
        "style": """
- Use specialized terminology and academic language
- Assume expert-level background knowledge
- Explore complex nuances, edge cases, and implications
- Reference academic research, methodologies, and debates
- Think "two professors discussing their field"
- Highly analytical with deep technical depth""",
    },
}


def get_complexity_instruction(complexity: int) -> str:
    """Get the complexity instruction for prompts."""
    level = COMPLEXITY_LEVELS.get(complexity, COMPLEXITY_LEVELS[3])
    return f"""
LANGUAGE & COMPLEXITY LEVEL: {level['name']} ({level['description']})
{level['style']}
"""


# Personality descriptions are now in app.services.llm.personalities
# Import the registry for backward compatibility
from app.services.llm.personalities import get_personality, PERSONALITY_REGISTRY


def get_personality_description(personality_name: str) -> dict[str, str]:
    """Get personality description as a dictionary (for backward compatibility).
    
    Args:
        personality_name: Name of the personality
        
    Returns:
        Dictionary with core_trait, voice, role, and personality_params
    """
    personality = get_personality(personality_name)
    return personality.get_description()


# Backward compatibility: maintain PERSONALITY_DESCRIPTIONS as a dict
PERSONALITY_DESCRIPTIONS = {
    name: get_personality(name).get_description()
    for name in PERSONALITY_REGISTRY.keys()
}


def get_configured_durations() -> dict[str, int]:
    """Get configured durations from settings."""
    from app.config import get_settings
    settings = get_settings()
    return {
        "briefing": settings.briefing_duration_minutes,
    }
