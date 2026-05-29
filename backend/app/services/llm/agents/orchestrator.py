"""Briefing Orchestrator - coordinates all agents for briefing generation."""

import asyncio
import os
from typing import Optional

from app.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.openrouter import OpenRouterProvider
from app.services.llm.agents.story_analyzer import StoryAnalyzerAgent
from app.services.llm.agents.facts_gatherer import FactsGathererAgent
from app.services.llm.agents.briefing_writer import BriefingWriterAgent
from app.services.llm.agents.host_research import HostResearchAgent, HostResearch
from app.services.web_research import combine_host_sources


class BriefingOrchestrator:
    """Master orchestrator that coordinates all briefing generation agents."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the briefing orchestrator.
        
        Args:
            llm: LLM provider instance (used for story analysis and facts gathering)
        """
        self.llm = llm
        
        # Create a separate LLM provider for briefing writing if writer model is configured
        # Otherwise, use the same LLM provider
        # Check environment first (for immediate updates), then fall back to settings
        writer_model = os.environ.get("OPENROUTER_WRITER_MODEL")
        if not writer_model:
            settings = get_settings()
            writer_model = settings.openrouter_writer_model
        
        if writer_model:
            # Create a separate provider with the writer model
            writer_llm = OpenRouterProvider(model=writer_model)
        else:
            # Use the same provider (will use the standard model)
            writer_llm = llm
        
        self.story_analyzer = StoryAnalyzerAgent(llm)
        self.facts_gatherer = FactsGathererAgent(llm)
        self.briefing_writer = BriefingWriterAgent(writer_llm)
    
    async def analyze_and_rank_stories(
        self,
        articles: list[dict],
        topics: list[str],
        max_stories: int = 5,
        briefing_id: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str], str, dict]:
        """Analyze and rank news stories.

        Args:
            articles: List of article dictionaries
            topics: List of topics to focus on
            max_stories: Maximum number of stories to select
            briefing_id: Optional briefing ID for cancellation support

        Returns:
            Tuple of (ranked_stories, analysis_summary, raw_response, usage)
        """
        return await self.story_analyzer.analyze_and_rank(
            articles=articles,
            topics=topics,
            max_stories=max_stories,
            briefing_id=briefing_id,
        )
    
    async def gather_additional_facts(
        self,
        stories: list[dict],
        briefing_id: Optional[str] = None,
    ) -> tuple[dict[int, list[str]], str, dict]:
        """Gather additional facts for stories.

        Args:
            stories: List of story dictionaries with full content
            briefing_id: Optional briefing ID for cancellation support

        Returns:
            Tuple of (facts_dict, raw_response, usage)
            facts_dict: Dictionary mapping article index to lists of facts
            raw_response: Raw LLM response content
            usage: LLM usage data including cost information
        """
        return await self.facts_gatherer.gather_facts(
            stories=stories,
            briefing_id=briefing_id,
        )
    
    def _make_host_agent(self) -> HostResearchAgent:
        return HostResearchAgent(self.llm)

    async def gather_host_research(
        self,
        stories: list[dict],
        cast_members: list[dict],
        briefing_id: Optional[str] = None,
    ) -> tuple[list[HostResearch], list[dict]]:
        """Run one persona-driven research pass per host, concurrently."""
        ordered = sorted(cast_members, key=lambda m: m.get("order", 0))

        async def _one(member: dict) -> HostResearch:
            agent = self._make_host_agent()
            return await agent.research(
                stories=stories,
                host_name=member.get("name", "Host"),
                personality_name=member.get("personality", "Casual"),
                briefing_id=briefing_id,
            )

        research_list = await asyncio.gather(*[_one(m) for m in ordered])
        combined_sources = combine_host_sources([r.sources for r in research_list])
        return list(research_list), combined_sources

    async def write_briefing_script(
        self,
        content: str,
        topics: list[str],
        cast_members: list[dict],
        duration: int = 10,
        user_name: Optional[str] = None,
        complexity: int = 3,
        additional_facts: Optional[dict[int, list[str]]] = None,
        ranked_items: Optional[list] = None,
        cast_name: Optional[str] = None,
        cast_description: Optional[str] = None,
        briefing_title: Optional[str] = None,
        recent_articles: Optional[list[dict]] = None,
        last_script: Optional[str] = None,
        prior_titles: Optional[list[str]] = None,
        host_research: Optional[list] = None,
        enable_non_speech_sounds: bool = False,
        briefing_id: Optional[str] = None,
    ):
        """Generate the podcast script for a briefing.

        Args:
            content: News content to discuss
            topics: List of topics to focus on
            cast_members: List of cast member dicts
            duration: Target duration in minutes
            user_name: Optional user name
            complexity: Conversation complexity level 1-5
            additional_facts: Dictionary mapping article index to facts
            ranked_items: List of ranked news items
            cast_name: Optional name of the cast
            cast_description: Optional description of how the cast works
            briefing_title: Optional briefing title
            recent_articles: List of recent articles for continuity
            last_script: Transcript from last briefing for continuity
            prior_titles: Story titles from the last matching briefing (preferred continuity signal)
            enable_non_speech_sounds: Whether to include non-speech sounds markup
            briefing_id: Optional briefing ID for cancellation support

        Returns:
            LLMResponse object with generated content, model, and usage info
        """
        return await self.briefing_writer.write_briefing(
            content=content,
            topics=topics,
            cast_members=cast_members,
            duration=duration,
            user_name=user_name,
            complexity=complexity,
            additional_facts=additional_facts,
            ranked_items=ranked_items,
            cast_name=cast_name,
            cast_description=cast_description,
            briefing_title=briefing_title,
            recent_articles=recent_articles,
            last_script=last_script,
            prior_titles=prior_titles,
            host_research=host_research,
            enable_non_speech_sounds=enable_non_speech_sounds,
            briefing_id=briefing_id,
        )

