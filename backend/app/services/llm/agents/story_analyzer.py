"""Story Analyzer Agent - analyzes and ranks news stories by importance and topic relevance."""

import json
from datetime import datetime, timezone
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
    
    @staticmethod
    def _join_topics(topics: list[str]) -> str:
        if not topics:
            return "general news"
        if len(topics) == 1:
            return topics[0]
        if len(topics) == 2:
            return f"{topics[0]} and {topics[1]}"
        return ", ".join(topics[:-1]) + f", and {topics[-1]}"

    def _build_system_prompt(
        self,
        topics: list[str],
        topic_descriptions: Optional[dict[str, str]] = None,
        max_stories: int = 3,
    ) -> str:
        """Build the editor's system prompt.

        Args:
            topics: Topic names the listener chose
            topic_descriptions: Optional per-topic description (what the listener
                means by the topic, and what they do not want)
            max_stories: Upper bound on selected stories; fewer is always fine
        """
        topics_str = self._join_topics(topics)

        topic_lines = []
        for t in topics or []:
            desc = (topic_descriptions or {}).get(t)
            topic_lines.append(f"- {t}: {desc.strip()}" if desc and desc.strip() else f"- {t}")
        topic_block = "\n".join(topic_lines) if topic_lines else "- general news"

        return f"""You are the editor of a short daily podcast. From a pile of candidate articles you pick the few stories worth the listener's time.

THE LISTENER'S TOPICS:
{topic_block}

HOW TO CHOOSE:
1. Relevance is a hard filter. Keep only articles squarely about the topics above. Tangential or one-keyword matches are out.
2. Freshness matters. Today's date is given with the articles. An article published more than a few days ago, or with no date at all, needs a strong reason to be included; otherwise leave it out.
3. Reject anything that is not an actual article: section or tag index pages, live blogs, listicles, press-release reposts, and pages whose title is just a topic name.
4. Do not re-select a story the listener already heard. A genuine new development is fine; a rehash under a new headline is not.
5. Among what remains, prefer stories with real consequence, a clear development, and enough substance to talk about for a couple of minutes. If two articles cover the same event, keep the better one.
6. When several topics are listed, cover more than one when the material supports it, but never pick a weak story just for balance.

Select at most {max_stories} stories, stack-ranked. Fewer is better than padding with a weak pick. Selecting zero is acceptable when nothing qualifies."""

    def _build_user_prompt(
        self,
        articles: list[dict],
        topics: list[str],
        max_stories: int,
        today: Optional[datetime] = None,
        prior_titles: Optional[list[str]] = None,
    ) -> str:
        """Build the user prompt listing candidate articles.

        Each article shows its URL and publish date so the editor can judge
        freshness and spot non-article pages.
        """
        today = today or datetime.now(timezone.utc)
        today_str = today.strftime("%B %d, %Y")

        articles_text = []
        for i, article in enumerate(articles, 1):
            published = article.get("published")
            if isinstance(published, datetime):
                published = published.strftime("%Y-%m-%d %H:%M UTC")
            elif isinstance(published, str) and published:
                published = published[:16].replace("T", " ")
            else:
                published = "unknown"
            articles_text.append(f"""
ARTICLE {i}:
Title: {article.get('title', 'Untitled')}
Source: {article.get('source', 'Unknown')}
URL: {article.get('url') or 'unknown'}
Published: {published}
Category: {article.get('category', 'general')}
Summary: {(article.get('summary') or 'No summary available')[:400]}
""")

        prior_block = ""
        titles = [t for t in (prior_titles or []) if t]
        if titles:
            prior_block = "\nALREADY COVERED IN THE LAST BRIEFING (do not re-select unless there is a real new development):\n" + "\n".join(f"- {t}" for t in titles) + "\n"

        return f"""Today is {today_str}. Topics: {self._join_topics(topics)}.
{prior_block}
CANDIDATE ARTICLES ({len(articles)}):
{"---".join(articles_text)}

Pick at most {max_stories} stories following the rules in your instructions. For each, give the article number, a priority from 1 to 10, and one sentence on why it earns a slot.

OUTPUT FORMAT (JSON only, no other text):
{{
  "ranked_stories": [
    {{"article_num": 4, "priority": 9, "reason": "..."}}
  ],
  "summary": "One or two sentences on today's picture for these topics"
}}"""

    async def analyze_and_rank(
        self,
        articles: list[dict],
        topics: list[str],
        max_stories: int = 3,
        briefing_id: Optional[str] = None,
        topic_descriptions: Optional[dict[str, str]] = None,
        prior_titles: Optional[list[str]] = None,
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
        system_prompt = self._build_system_prompt(topics, topic_descriptions, max_stories)
        user_prompt = self._build_user_prompt(articles, topics, max_stories, prior_titles=prior_titles)

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

