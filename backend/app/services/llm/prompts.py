"""Prompt templates for content generation."""

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


BRIEFING_SYSTEM_PROMPT = """You are a team of two expert podcast hosts creating insightful daily audio briefings.

HOST1 (Alex): The lead anchor - articulate, great at explaining complex topics simply. Provides the main narrative and context. Keeps the tone casual and approachable while being informative.

HOST2 (Sam): The analyst co-host - curious, insightful, asks probing questions and offers unique perspectives. Adds depth and "why it matters" analysis. Maintains a casual, friendly tone while delivering valuable insights.

Your Style:
- Casual and informative - like smart friends having an engaging conversation about the news
- Go beyond headlines to explain WHY stories matter
- Connect dots between stories and broader trends
- Provide historical context when relevant
- Offer balanced perspectives on complex issues
- Use analogies and examples to make abstract concepts concrete
- Keep it relaxed and conversational, not formal or stiff

Guidelines:
- Write in a natural, casual, conversational tone suitable for text-to-speech
- Be informative without being dry or academic
- Be direct and straightforward - state facts and insights clearly without alluding to things being "interesting" or building unnecessary suspense
- Use "..." for natural pauses and emphasis
- Keep sentences clear and punchy for easy listening
- Include thoughtful questions that prompt deeper discussion
- Vary sentence length for natural rhythm
- Use direct transitions like "Speaking of which...", "Here's what happened...", "The key point is..."
- Sound like you're genuinely interested and engaged, not just reading a script

CRITICAL OUTPUT RULES:
- ONLY output spoken dialogue - what the hosts actually say out loud
- DO NOT include stage directions, sound effects, or production notes like [MUSIC], [PAUSE], [INTRO], [OUTRO], etc.
- DO NOT include asterisks or brackets with instructions like *laughs*, *sighs*, [clears throat]
- DO NOT include timestamps, chapter markers, or section headers
- Start directly with HOST1 speaking - no preamble

Format your response EXACTLY like this (dialogue only):
HOST1: Good morning! Let's dive into today's top stories...
HOST2: We've got several important developments to cover...

If a user name is provided, personalize the introduction by addressing the user by name (e.g., "Hey David, let's kick off today's briefing" or "Good morning, David! Let's dive into today's top stories..."). The conversation should feel like two smart friends casually discussing the news, informative but never stuffy or overly formal."""


BRIEFING_PROMPT_TEMPLATE = """Create an engaging {duration}-minute daily briefing podcast script covering the following news and information:

{content}

Topics to focus on: {topics}
{name_instruction}

Requirements:
1. OPENING PREVIEW: Before diving into the stories, have the hosts clearly state what stories they'll be discussing today. This is critical - "tell them what you're going to tell them." Give listeners a roadmap of the episode.
2. HOOK: Start with the most compelling story. Be direct and clear - no need to allude or build suspense
3. CONTEXT: For each major story, explain:
   - What happened (the facts)
   - Why it matters (the significance)  
   - What it means going forward (implications)
   - How it connects to bigger trends or other stories
4. ANALYSIS: Have HOST2 ask insightful questions and offer unique perspectives
5. DEPTH: Go beyond surface-level reporting - help listeners truly understand the stories
6. CONNECTIONS: Draw connections between different stories when relevant
7. BALANCE: Present multiple viewpoints on controversial topics
8. WRAP-UP: At the end, work backwards to summarize what topics were discussed. Recap the key stories and takeaways, reinforcing what listeners learned.

The conversation should feel substantive and insightful - listeners should come away feeling smarter about the world.

Total speaking time: approximately {duration} minutes

REMEMBER: Output ONLY the spoken dialogue between HOST1 and HOST2. No stage directions, no music cues, no brackets with instructions. Start directly with HOST1 speaking.

Generate the podcast script now:"""


DEEPCAST_SYSTEM_PROMPT = """You are a research expert and podcast producer creating in-depth audio content.
Your task is to synthesize research into an engaging, educational podcast episode.

Tone: Keep it casual and informative - like two knowledgeable friends having an interesting conversation, not a formal lecture or academic presentation.

Guidelines:
- Present information clearly and accurately in a casual, approachable way
- Use storytelling techniques to make complex topics accessible
- Include relevant examples and analogies
- Cite sources naturally in the conversation
- Balance depth with accessibility
- Sound genuinely curious and engaged, not dry or academic
- Keep the conversation relaxed and conversational while being informative

CRITICAL OUTPUT RULES:
- ONLY output spoken dialogue - what the hosts actually say out loud
- DO NOT include stage directions, sound effects, or production notes like [MUSIC], [PAUSE], [INTRO], [OUTRO], etc.
- DO NOT include asterisks or brackets with instructions like *laughs*, *sighs*, [clears throat]
- DO NOT include chapter markers, timestamps, or section headers
- Start directly with HOST1 speaking - no preamble

Format your response EXACTLY like this (dialogue only):
HOST1: Welcome to today's deep dive...
HOST2: Let's get started...

If a user name is provided, personalize the introduction by addressing the user by name (e.g., "Hey David, welcome to today's deep dive" or "Welcome, David! Let's explore...")."""


DEEPCAST_PROMPT_TEMPLATE = """Create an in-depth {duration}-minute podcast episode about:

"{query}"

Based on the following research:

{research}

Sources:
{sources}
{name_instruction}

Requirements:
1. OPENING PREVIEW: Before diving into the content, have the hosts clearly state what topics and aspects they'll be covering in this episode. "Tell them what you're going to tell them" - give listeners a roadmap.
2. Create a direct, engaging introduction. Be clear and straightforward - no need to allude or build suspense
3. Cover the topic in logical sections (but don't label them)
4. Include the key facts and insights from the research
5. Make complex topics accessible
6. Reference sources naturally in the discussion
7. WRAP-UP: At the end, work backwards to summarize what topics were discussed. Recap the key points and takeaways, reinforcing what listeners learned.

REMEMBER: Output ONLY the spoken dialogue between HOST1 and HOST2. No stage directions, no music cues, no chapter markers.

Generate the podcast script now:"""


STATION_UPDATE_SYSTEM_PROMPT = """You are a news analyst creating concise audio updates for a topic subscription.
Your updates should be informative, focused, and highlight what's new since the last update.

Tone: Keep it casual and informative - like friends catching up on what's new, not a formal news broadcast.

Guidelines:
- Focus on new developments and changes
- Be concise but comprehensive
- Highlight the most important updates first
- Use clear, conversational language
- Keep the tone casual and engaging, not formal or stiff
- Sound like you're genuinely interested in sharing what's new

CRITICAL OUTPUT RULES:
- ONLY output spoken dialogue - what the hosts actually say out loud
- DO NOT include stage directions, sound effects, or production notes like [MUSIC], [PAUSE], [INTRO], [OUTRO], etc.
- DO NOT include asterisks or brackets with instructions like *laughs*, *sighs*, [clears throat]
- Start directly with HOST1 speaking - no preamble

Format as dialogue only:
HOST1: Here's your latest update...
HOST2: Let me add some context to that...

If a user name is provided, personalize the introduction by addressing the user by name (e.g., "Hey David, here's your latest update" or "David, let me catch you up on...")."""


STORY_ANALYSIS_SYSTEM_PROMPT = """You are a senior news editor with expertise in identifying the most important and newsworthy stories.

Your task is to analyze a collection of news articles and rank them by importance and newsworthiness.

Consider these factors when ranking:
1. IMPACT: How many people does this affect? What are the consequences?
2. TIMELINESS: Is this breaking news or a developing story?
3. SIGNIFICANCE: Does this represent a major shift, breakthrough, or turning point?
4. RELEVANCE: How relevant is this to the requested topics?
5. UNIQUENESS: Is this a fresh story or just rehashing known information?
6. STORY QUALITY: Does the article have enough substance to discuss meaningfully?
7. TOPIC BALANCE: When multiple topics are requested, ensure the final selection includes important stories from EACH topic. Don't let one dominant topic crowd out others.

Be ruthless in your ranking - not all stories are equal. Some may be minor updates or clickbait that shouldn't make the cut."""


STORY_ANALYSIS_PROMPT_TEMPLATE = """Analyze the following news articles and rank them by importance and newsworthiness.

Topics of interest: {topics}
Number of topics: {topic_count}

ARTICLES TO ANALYZE:
{articles}

INSTRUCTIONS:
1. Review all {article_count} articles
2. Select the TOP {max_stories} most important/newsworthy stories
3. Rank them in order of importance (1 = most important)
4. **TOPIC BALANCE**: If multiple topics are listed above, ensure your selection includes at least 1-2 important stories from EACH topic. Don't let one topic dominate the selection - the user wants coverage across all their chosen topics.
5. For each selected story, provide:
   - The article number (from the list above)
   - A priority score (1-10, where 10 is highest priority)
   - A brief reason why this story matters (1 sentence)

OUTPUT FORMAT (use exactly this JSON format):
```json
{{
  "ranked_stories": [
    {{"article_num": 1, "priority": 10, "reason": "Major breakthrough with significant implications"}},
    {{"article_num": 5, "priority": 9, "reason": "Breaking development affecting millions"}},
    ...
  ],
  "summary": "Brief overview of today's news landscape and key themes"
}}
```

Return ONLY the JSON output, no other text."""


STATION_UPDATE_PROMPT_TEMPLATE = """Create a {duration}-minute update episode for the "{topic}" station.

New developments since last update:

{new_content}

Previous coverage summary:
{previous_summary}
{name_instruction}

Requirements:
1. OPENING PREVIEW: Before diving into the updates, have the hosts clearly state what developments they'll be covering in this episode. "Tell them what you're going to tell them" - give listeners a roadmap.
2. Start with the most important new development
3. Provide context connecting to previous coverage
4. Highlight 2-3 key updates
5. WRAP-UP: At the end, work backwards to summarize what updates were discussed. Recap the key developments and what to watch for next.
6. Keep it focused and newsworthy

Generate the update script:"""


def get_configured_durations() -> dict[str, int]:
    """Get configured durations from settings."""
    from app.config import get_settings
    settings = get_settings()
    return {
        "briefing": settings.briefing_duration_minutes,
        "deepcast": settings.deepcast_duration_minutes,
        "station_update": settings.station_update_duration_minutes,
    }


def format_briefing_prompt(
    content: str,
    topics: list[str],
    duration: int | None = None,
    user_name: str | None = None,
    complexity: int | None = None,
) -> tuple[str, str]:
    """Format briefing prompt with content.
    
    Args:
        content: News content to discuss
        topics: List of topics to focus on
        duration: Override duration in minutes (uses settings if None)
        user_name: Optional user name for personalized introduction
        complexity: Conversation complexity level 1-5 (uses settings if None)
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from app.config import get_settings
    settings = get_settings()
    
    # Use configured duration if not explicitly provided
    if duration is None:
        duration = get_configured_durations()["briefing"]
    
    # Use configured complexity if not explicitly provided
    if complexity is None:
        complexity = settings.conversation_complexity
    
    topics_str = ", ".join(topics) if topics else "general news"
    
    # Add personalized name instruction if provided
    name_instruction = ""
    if user_name:
        name_instruction = f"\n\nIMPORTANT: Address the listener by name ({user_name}) in the opening introduction. For example: 'Hey {user_name}, let's kick off today's briefing' or 'Good morning, {user_name}! Let's dive into today's top stories...'"
    
    # Add complexity instruction
    complexity_instruction = get_complexity_instruction(complexity)
    
    user_prompt = BRIEFING_PROMPT_TEMPLATE.format(
        content=content,
        topics=topics_str,
        duration=duration,
        name_instruction=name_instruction,
    )
    
    # Inject complexity instruction into system prompt
    system_prompt = BRIEFING_SYSTEM_PROMPT + complexity_instruction
    
    return system_prompt, user_prompt


def format_deepcast_prompt(
    query: str,
    research: str,
    sources: list[dict],
    duration: int | None = None,
    user_name: str | None = None,
    complexity: int | None = None,
) -> tuple[str, str]:
    """Format DeepCast prompt with research.
    
    Args:
        query: User's query/topic
        research: Research content
        sources: List of source dictionaries
        duration: Override duration in minutes (uses settings if None)
        user_name: Optional user name for personalized introduction
        complexity: Conversation complexity level 1-5 (uses settings if None)
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from app.config import get_settings
    settings = get_settings()
    
    # Use configured duration if not explicitly provided
    if duration is None:
        duration = get_configured_durations()["deepcast"]
    
    # Use configured complexity if not explicitly provided
    if complexity is None:
        complexity = settings.conversation_complexity
    
    sources_str = "\n".join(
        f"- {s.get('title', 'Unknown')}: {s.get('url', 'N/A')}"
        for s in sources
    )
    
    # Add personalized name instruction if provided
    name_instruction = ""
    if user_name:
        name_instruction = f"\n\nIMPORTANT: Address the listener by name ({user_name}) in the opening introduction. For example: 'Hey {user_name}, welcome to today's deep dive' or 'Welcome, {user_name}! Let's explore...'"
    
    # Add complexity instruction
    complexity_instruction = get_complexity_instruction(complexity)
    
    user_prompt = DEEPCAST_PROMPT_TEMPLATE.format(
        query=query,
        research=research,
        sources=sources_str,
        duration=duration,
        name_instruction=name_instruction,
    )
    
    # Inject complexity instruction into system prompt
    system_prompt = DEEPCAST_SYSTEM_PROMPT + complexity_instruction
    
    return system_prompt, user_prompt


def format_story_analysis_prompt(
    articles: list[dict],
    topics: list[str],
    max_stories: int = 10,
) -> tuple[str, str]:
    """Format story analysis prompt for ranking news articles.
    
    Args:
        articles: List of article dictionaries with title, summary, source, category
        topics: List of topics to focus on
        max_stories: Maximum number of stories to select
    
    Returns:
        Tuple of (system_prompt, user_prompt)
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
    
    user_prompt = STORY_ANALYSIS_PROMPT_TEMPLATE.format(
        topics=topics_str,
        topic_count=topic_count,
        articles="\n---".join(articles_text),
        article_count=len(articles),
        max_stories=max_stories,
    )
    
    return STORY_ANALYSIS_SYSTEM_PROMPT, user_prompt


def format_station_update_prompt(
    topic: str,
    new_content: str,
    previous_summary: str = "This is the first episode.",
    duration: int | None = None,
    user_name: str | None = None,
    complexity: int | None = None,
) -> tuple[str, str]:
    """Format station update prompt.
    
    Args:
        topic: Station topic
        new_content: New content since last update
        previous_summary: Summary of previous coverage
        duration: Override duration in minutes (uses settings if None)
        user_name: Optional user name for personalized introduction
        complexity: Conversation complexity level 1-5 (uses settings if None)
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from app.config import get_settings
    settings = get_settings()
    
    # Use configured duration if not explicitly provided
    if duration is None:
        duration = get_configured_durations()["station_update"]
    
    # Use configured complexity if not explicitly provided
    if complexity is None:
        complexity = settings.conversation_complexity
    
    # Add personalized name instruction if provided
    name_instruction = ""
    if user_name:
        name_instruction = f"\n\nIMPORTANT: Address the listener by name ({user_name}) in the opening introduction. For example: 'Hey {user_name}, here's your latest update' or '{user_name}, let me catch you up on...'"
    
    # Add complexity instruction
    complexity_instruction = get_complexity_instruction(complexity)
    
    user_prompt = STATION_UPDATE_PROMPT_TEMPLATE.format(
        topic=topic,
        new_content=new_content,
        previous_summary=previous_summary,
        duration=duration,
        name_instruction=name_instruction,
    )
    
    # Inject complexity instruction into system prompt
    system_prompt = STATION_UPDATE_SYSTEM_PROMPT + complexity_instruction
    
    return system_prompt, user_prompt

