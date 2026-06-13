"""Story Analyzer Agent - analyzes and ranks news stories by importance and topic relevance."""

import json
from typing import Optional

from app.config import get_settings
from app.services.llm.base import LLMProvider

RANKING_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "story_ranking",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ranked_stories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "article_num": {"type": "integer"},
                            "priority": {"type": "integer"},
                            "reason": {"type": "string"},
                        },
                        "required": ["article_num", "priority", "reason"],
                    },
                },
                "summary": {"type": "string"},
            },
            "required": ["ranked_stories", "summary"],
        },
    },
}


class StoryAnalyzerAgent:
    """Agent responsible for analyzing and ranking news stories."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the story analyzer agent.
        
        Args:
            llm: LLM provider instance
        """
        self.llm = llm
    
    def _build_system_prompt(self, topics: list[str], max_stories: int = 5) -> str:
        """Build story analysis system prompt with topic-specific instructions.

        Args:
            topics: List of topics the user has chosen to focus on
            max_stories: Ceiling on how many stories to select

        Returns:
            System prompt string with topic-specific guidance
        """
        # Format topics for display
        if topics:
            if len(topics) == 1:
                topics_str = topics[0]
            elif len(topics) == 2:
                topics_str = f"{topics[0]} and {topics[1]}"
            else:
                topics_str = ", ".join(topics[:-1]) + f", and {topics[-1]}"
        else:
            topics_str = "general news"

        prompt = f"""You are a senior news editor selecting stories for a short podcast briefing.

USER'S CHOSEN TOPICS: {topics_str}

Selection rules:
- Only stories directly relevant to the chosen topics qualify. Discard everything else, including stories with merely tangential connections.
- Select up to {max_stories} stories, but only stories that genuinely merit discussion: directly on-topic, substantial enough to talk about for two minutes, and newsworthy today. If only one or two qualify, return only those. Never include a marginal story just to fill a slot — a short briefing about real news beats a long one padded with filler.
- Rank the selected stories by relevance to the chosen topics, impact, timeliness, and substance.
- When several topics are requested, prefer a selection that spans them — but never at the cost of including a weak story."""

        return prompt
    
    def _build_user_prompt(
        self,
        articles: list[dict],
        topics: list[str],
        max_stories: int,
    ) -> str:
        """Build user prompt for story analysis.
        
        Args:
            articles: List of article dictionaries with title, summary, source, category
            topics: List of topics to focus on
            max_stories: Maximum number of stories to select
            
        Returns:
            User prompt string
        """
        # Format articles for the prompt
        articles_text = []
        for i, article in enumerate(articles, 1):
            article_text = f"""
ARTICLE {i}:
Title: {article.get('title', 'Untitled')}
Source: {article.get('source', 'Unknown')}
Category: {article.get('category', 'general')}
Summary: {article.get('summary', 'No summary available')[:300]}
"""
            articles_text.append(article_text)
        
        topics_str = ", ".join(topics) if topics else "general news"
        topic_count = len(topics) if topics else 1
        
        prompt = f"""Select and rank the briefing stories from the articles below.

Topics of interest: {topics_str}
Number of topics: {topic_count}

ARTICLES TO ANALYZE:
{"---".join(articles_text)}

INSTRUCTIONS:
1. Discard articles unrelated (or only tangentially related) to the topics above.
2. From what remains, select up to {max_stories} stories that genuinely merit discussion, ranked in strict priority order. Selecting fewer than {max_stories} is the right call whenever the remaining articles are weak — never pad the list.
3. For each selected story provide the article number, a priority score (1-10), and one sentence on why it matters to the chosen topics.

OUTPUT FORMAT (use exactly this JSON format):
```json
{{
  "ranked_stories": [
    {{"article_num": 5, "priority": 9, "reason": "Major breakthrough with significant implications"}},
    {{"article_num": 3, "priority": 8, "reason": "Breaking development affecting millions"}},
    ...
  ],
  "summary": "Brief overview of today's news landscape and key themes"
}}
```

Return ONLY the JSON output, no other text."""

        return prompt
    
    async def analyze_and_rank(
        self,
        articles: list[dict],
        topics: list[str],
        max_stories: int = 5,
        briefing_id: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str], str, dict]:
        """Analyze and rank news stories by importance and topic relevance.

        Args:
            articles: List of article dictionaries with title, summary, source, category
            topics: List of topics to focus on
            max_stories: Maximum number of stories to select
            briefing_id: Optional briefing ID for cancellation support

        Returns:
            Tuple of (ranked_stories, analysis_summary, raw_response, usage)
            ranked_stories: List of story dicts with article_num, priority, reason
            analysis_summary: Optional summary string
            raw_response: Raw LLM response content
            usage: LLM usage data including cost information
        """
        system_prompt = self._build_system_prompt(topics, max_stories)
        user_prompt = self._build_user_prompt(articles, topics, max_stories)

        # Call LLM to analyze and rank stories
        response_format = RANKING_SCHEMA if get_settings().llm_structured_outputs else None
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,  # Lower temperature for more consistent analysis
            response_format=response_format,
            briefing_id=briefing_id,
        )
        
        # Store raw response content before parsing
        raw_response = response.content.strip()
        
        # Parse the JSON response
        content = raw_response
        
        # Extract JSON from the response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        try:
            analysis = json.loads(content)
            ranked_stories = analysis.get("ranked_stories", [])
            summary = analysis.get("summary", None)
            
            # Return usage data from response
            usage = response.usage if hasattr(response, 'usage') else {}
            
            return ranked_stories, summary, raw_response, usage
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse story analysis JSON: {e}")

