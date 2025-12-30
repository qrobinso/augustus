"""Topic Generator Agent - converts natural language prompts to topics."""

from typing import Optional
from app.services.llm.base import LLMProvider


class TopicGeneratorAgent:
    """Agent responsible for converting user prompts into well-defined topics."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the topic generator agent.
        
        Args:
            llm: LLM provider instance
        """
        self.llm = llm
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for topic generation.
        
        Returns:
            System prompt string
        """
        return """You are an expert at understanding user intent and creating well-defined news topics.

Your task is to take a user's natural language description of what they want to follow and convert it into:
1. A concise, general topic name (2-5 words) that will work well across multiple news sources
2. A brief description explaining what the topic covers
3. A recommendation on whether to enable NewsAPI (a general news aggregator)
4. A list of 5-10 recommended websites/news sources for this topic

Guidelines for the topic name:
- Keep it general enough to match articles from various sources
- Avoid overly specific or niche terms that won't match news headlines
- Use common industry/field terminology
- Think about what search terms would find relevant articles

Guidelines for NewsAPI recommendation:
- Enable NewsAPI if the topic is broad, mainstream, or commonly covered in general news
- Disable NewsAPI if the topic is very niche, technical, or requires specialized sources
- Consider: Would major news outlets (CNN, BBC, Reuters) cover this regularly?

Guidelines for site recommendations:
- Include reputable, well-established sources
- Mix of mainstream and specialized sources relevant to the topic
- Include up to 2-3 relevant Reddit subreddits if applicable
- Focus on sources that publish regularly

Return your response as a JSON object only, no additional text."""
    
    def _build_user_prompt(self, user_prompt: str) -> str:
        """Build user prompt for topic generation.
        
        Args:
            user_prompt: The user's natural language description
            
        Returns:
            User prompt string
        """
        return f"""The user wants to create a news topic to follow. Here's what they said:

"{user_prompt}"

Analyze this request and create a topic. Return your response as a JSON object with this exact format:
{{
  "name": "Topic Name Here",
  "description": "Brief description of what this topic covers",
  "use_newsapi": true,
  "reasoning": "Brief explanation of why NewsAPI is recommended or not",
  "sites": [
    {{
      "name": "Source Name",
      "url": "https://example.com"
    }}
  ]
}}

Remember:
- The topic name should be general enough to work across multiple news sources
- Only return the JSON object, no other text"""
    
    async def generate_topic(
        self,
        user_prompt: str,
    ) -> str:
        """Generate a topic from a natural language prompt.
        
        Args:
            user_prompt: The user's natural language description of what they want to follow
            
        Returns:
            LLM response content (should be JSON)
        """
        system_prompt = self._build_system_prompt()
        prompt = self._build_user_prompt(user_prompt)
        
        response = await self.llm.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.7,
        )
        
        return response.content.strip()



