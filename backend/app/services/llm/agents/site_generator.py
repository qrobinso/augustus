"""Site Generator Agent - suggests news sources for topics."""

from app.services.llm.base import LLMProvider


class SiteGeneratorAgent:
    """Agent responsible for generating news source suggestions."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the site generator agent.
        
        Args:
            llm: LLM provider instance
        """
        self.llm = llm
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for site generation.
        
        Returns:
            System prompt string
        """
        return """You are an expert news source curator. Your task is to identify reputable, high-quality news sources, blogs, RSS feeds, websites, and relevant Reddit subreddits that regularly publish content about specific topics.

When suggesting sources, prioritize:
1. Reputable, well-established sources with good editorial standards
2. Sources that publish regularly and consistently
3. A variety of sources (not all from the same publisher or network)
4. Main page URLs or RSS feed URLs (prefer main pages over specific article URLs)
5. Sources that are accessible and commonly used
6. Include up to 3 relevant Reddit subreddits (format: https://www.reddit.com/r/subredditname/) that are active and relevant to the topic

Return your suggestions in the exact JSON format specified."""
    
    def _build_user_prompt(self, topic_name: str, count: int = 10) -> str:
        """Build user prompt for site generation.
        
        Args:
            topic_name: The name of the topic to generate sites for
            count: Number of sites to generate
            
        Returns:
            User prompt string
        """
        return f"""Generate a list of {count} reputable news sources, blogs, RSS feeds, websites, and Reddit subreddits that regularly publish content about: "{topic_name}"

Focus on:
- Reputable sources with good editorial standards
- Sources that publish regularly (daily, weekly, or multiple times per week)
- A variety of sources from different publishers/networks
- Main page URLs or RSS feed URLs (not specific article URLs)
- Well-known, accessible sources
- Include up to 3 relevant Reddit subreddits (format URLs as: https://www.reddit.com/r/subredditname/) that are active and directly related to the topic

Return your response as a JSON object with this exact format:
{{
  "sites": [
    {{
      "name": "Source Name",
      "url": "https://example.com"
    }},
    {{
      "name": "r/subredditname",
      "url": "https://www.reddit.com/r/subredditname/"
    }},
    ...
  ]
}}

Only include the JSON object in your response, no additional text or explanation."""
    
    async def generate_sites(
        self,
        topic_name: str,
        count: int = 10,
    ) -> str:
        """Generate news source suggestions for a topic.
        
        Args:
            topic_name: The name of the topic to generate sites for
            count: Number of sites to generate (default: 10)
            
        Returns:
            LLM response content (should be JSON)
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(topic_name, count)
        
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.5,
        )
        
        return response.content.strip()











