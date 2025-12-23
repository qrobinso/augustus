"""Story Analyzer Agent - analyzes and ranks news stories by importance and topic relevance."""

import json
from typing import Optional

from app.services.llm.base import LLMProvider


class StoryAnalyzerAgent:
    """Agent responsible for analyzing and ranking news stories."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the story analyzer agent.
        
        Args:
            llm: LLM provider instance
        """
        self.llm = llm
    
    def _build_system_prompt(self, topics: list[str]) -> str:
        """Build story analysis system prompt with topic-specific instructions.
        
        Args:
            topics: List of topics the user has chosen to focus on
            
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
        
        prompt = f"""You are a senior news editor with expertise in identifying the most important and newsworthy stories.

Your task is to analyze a collection of news articles and narrow them down to 3-5 top stories, stack-ranked in priority order.

USER'S CHOSEN TOPICS: {topics_str}

CRITICAL FILTERING AND PRIORITY RULES:
1. **WEATHER STORIES ARE ALWAYS TOP PRIORITY** - Any article about weather, storms, natural disasters, or climate-related events must be ranked #1, regardless of other factors. Weather affects everyone's daily life and safety.

2. **TOPIC RELEVANCE FILTERING IS MANDATORY** - The user has specifically chosen to focus on: {topics_str}
   - **FIRST STEP: FILTER OUT** articles that are clearly unrelated to these topics
   - **EXCLUDE** articles that have no meaningful connection to the user's chosen topics
   - **EXCLUDE** articles that are only tangentially related (weak connection, not directly relevant)
   - **ONLY INCLUDE** articles that are directly related to the chosen topics OR weather-related
   - Articles that don't align with the user's chosen topics should be EXCLUDED entirely unless they are weather-related

3. **AFTER FILTERING**, rank the remaining articles using these factors:
   a. TOPIC RELEVANCE: How directly does this article relate to the user's chosen topics ({topics_str})? This is the primary factor.
   b. IMPACT: How many people does this affect? What are the consequences?
   c. TIMELINESS: Is this breaking news or a developing story?
   d. SIGNIFICANCE: Does this represent a major shift, breakthrough, or turning point?
   e. UNIQUENESS: Is this a fresh story or just rehashing known information?
   f. STORY QUALITY: Does the article have enough substance to discuss meaningfully?
   g. TOPIC BALANCE: When multiple topics are requested, ensure the final selection includes important stories from EACH topic. Don't let one dominant topic crowd out others.

Be ruthless in your filtering and ranking - not all stories are equal. Exclude articles that don't relate to the user's topics. Your goal is to select ONLY the 3-5 most important stories that are DIRECTLY related to the user's chosen topics."""
        
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
        
        prompt = f"""Analyze the following news articles and narrow them down to 3-5 top stories, stack-ranked in priority order.

Topics of interest: {topics_str}
Number of topics: {topic_count}

ARTICLES TO ANALYZE:
{"---".join(articles_text)}

INSTRUCTIONS:
1. **FIRST STEP - FILTER BY TOPIC RELEVANCE**: Review all {len(articles)} articles and EXCLUDE articles that are:
   - Clearly unrelated to the topics listed above ({topics_str})
   - Only tangentially connected (weak or indirect connection)
   - Not directly relevant to the user's chosen topics
   - EXCEPTION: Keep weather-related articles regardless of topic relevance

2. **SECOND STEP - IDENTIFY WEATHER STORIES**: From the filtered articles, identify any weather-related stories (storms, natural disasters, weather warnings, climate events). These MUST be ranked #1.

3. **THIRD STEP - SELECT AND RANK**: From the remaining articles (after filtering), select ONLY the TOP 3-5 most important/newsworthy stories that are DIRECTLY related to the topics ({topics_str}). Rank them in strict priority order (1 = highest priority, 2 = second priority, etc.)

4. **TOPIC BALANCE**: If multiple topics are listed above, ensure your selection includes important stories from EACH topic when possible. Don't let one topic dominate the selection - the user wants coverage across all their chosen topics.

5. For each selected story, provide:
   - The article number (from the list above)
   - A priority score (1-10, where 10 is highest priority)
   - A brief reason why this story matters and how it relates to the chosen topics (1 sentence)

OUTPUT FORMAT (use exactly this JSON format):
```json
{{
  "ranked_stories": [
    {{"article_num": 1, "priority": 10, "reason": "Weather story - always top priority"}},
    {{"article_num": 5, "priority": 9, "reason": "Major breakthrough with significant implications"}},
    {{"article_num": 3, "priority": 8, "reason": "Breaking development affecting millions"}},
    ...
  ],
  "summary": "Brief overview of today's news landscape and key themes"
}}
```

CRITICAL FILTERING REQUIREMENTS: 
- EXCLUDE articles that don't relate to the chosen topics ({topics_str})
- EXCLUDE articles with only weak/tangential connections
- ONLY include articles that are directly relevant to the topics OR weather-related
- If there aren't enough quality stories related to the topics, select fewer (3-4 is acceptable)
- Weather stories MUST be ranked #1 if present
- Return ONLY the JSON output, no other text."""
        
        return prompt
    
    async def analyze_and_rank(
        self,
        articles: list[dict],
        topics: list[str],
        max_stories: int = 5,
    ) -> tuple[list[dict], Optional[str], str]:
        """Analyze and rank news stories by importance and topic relevance.
        
        Args:
            articles: List of article dictionaries with title, summary, source, category
            topics: List of topics to focus on
            max_stories: Maximum number of stories to select
            
        Returns:
            Tuple of (ranked_stories, analysis_summary, raw_response)
            ranked_stories: List of story dicts with article_num, priority, reason
            analysis_summary: Optional summary string
            raw_response: Raw LLM response content
        """
        system_prompt = self._build_system_prompt(topics)
        user_prompt = self._build_user_prompt(articles, topics, max_stories)
        
        # Call LLM to analyze and rank stories
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=2048,
            temperature=0.3,  # Lower temperature for more consistent analysis
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
            
            return ranked_stories, summary, raw_response
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse story analysis JSON: {e}")

