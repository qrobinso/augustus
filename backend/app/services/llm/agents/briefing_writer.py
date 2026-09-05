"""Briefing Writer Agent - generates podcast script content for briefings."""

from typing import Optional

from app.services.llm.base import LLMProvider
from app.services.llm.prompts import (
    COMPLEXITY_LEVELS,
    get_complexity_instruction,
    tokens_for_duration,
    target_words_for_duration,
)
from app.services.llm.personalities import get_personality


# Non-speech sounds guide for Gemini TTS
NON_SPEECH_SOUNDS_GUIDE = """

=== NON-SPEECH SOUNDS & STYLE MARKUP ===

Use these tags to add realism and natural pacing, and to break up the script:

SOUNDS (audible vocalizations): [sigh], [laughing], [uhm]
STYLE (modifies delivery): [sarcasm], [shouting], [whispering], [extremely fast]
PAUSES: [short pause] ~250ms, [medium pause] ~500ms, [long pause] ~1s

USE NATURALLY (do not overdo it):
- [uhm] - occasionally, at genuine thinking or transition points, to soften delivery.
- [short pause] - to break up longer sentences or set up an important point.

Examples:
- "That's... [sigh] honestly not surprising."
- "[laughing] Okay, that's actually pretty clever."
- "So... [uhm] what happens next? [short pause] Well, the thing is..."
- "[sarcasm] Oh yes, because that worked so well last time."
- "[whispering] Here's the thing most people don't realize... [short pause] It's actually..."
- "The data shows [uhm] [short pause] that we're seeing a significant shift."
- "I think [uhm] the important part here [short pause] is understanding why this happened."

Guidelines:
- Use [uhm] and [short pause] where they make speech feel natural — a few per segment, not in every sentence.
- Place [uhm] at natural thinking points, transitions, or when a host is formulating a thought
- Place [short pause] to break up longer sentences, emphasize points, or create natural rhythm
- Use other sounds (sigh, laughing, etc.) sparingly and match them to the host's personality
- The goal is to make the dialogue feel like a real conversation, not a script being read
"""

def build_host_research_section(host_research, stories) -> str:
    """Render each host's own research so the writer can stage an asymmetric debate."""
    if not host_research:
        return ""

    def _title(idx):
        if stories and 0 <= idx < len(stories):
            item = stories[idx]
            return getattr(item, "title", None) or (item.get("title") if isinstance(item, dict) else None) or f"Story {idx+1}"
        return f"Story {idx+1}"

    blocks = ["\n\n=== WHAT EACH HOST RESEARCHED (bring your own findings to the conversation) ==="]
    for hr in host_research:
        blocks.append(f"\n{hr.host_name} ({hr.angle}):")
        if not hr.facts_by_story_index:
            blocks.append("- (no distinct findings)")
            continue
        for idx, facts in hr.facts_by_story_index.items():
            blocks.append(f"On \"{_title(idx)}\":")
            claims = getattr(hr, "claims_by_story_index", {}).get(idx)
            if claims:
                for claim in claims:
                    if claim.get("sources"):
                        blocks.append(f"  - Source-linked finding: {claim['text']}")
                        for source in claim["sources"]:
                            blocks.append(f"    {source['title']} ({source['url']}): {source['excerpt']}")
                    else:
                        blocks.append(f"  - Unverified research lead (do not assert): {claim['text']}")
            else:
                for fact in facts:
                    blocks.append(f"  - Unverified research lead (do not assert): {fact}")
    blocks.append(
        "\nEach host knows only their own findings above. Let one host be surprised or "
        "corrected by something the other found; do not have both recite the same facts. "
        "A linked excerpt is evidence to inspect, not proof: ensure it supports the claim. "
        "Do not assert unverified leads as facts. Attribute supported facts naturally; never speak URLs. "
        "When sources conflict, explain what is disputed and what remains unknown. Label interpretation as interpretation."
    )
    return "\n".join(blocks)


def build_continuity_section(prior_titles: list[str]) -> str:
    """Build the 'previously covered' section from prior story titles.

    Using titles (not a raw transcript tail) gives the model a precise list of
    what to avoid repeating, without biasing toward the previous wrap-up.
    """
    titles = [t for t in (prior_titles or []) if t]
    if not titles:
        return ""
    lines = "\n".join(f"- {t}" for t in titles)
    return (
        "\n\n=== ALREADY COVERED IN THE LAST BRIEFING (do not repeat) ===\n"
        "These stories were covered last time. Do not repeat them; only reference "
        "one if there is a genuine update or new angle.\n"
        f"{lines}\n"
    )


class BriefingWriterAgent:
    """Agent responsible for writing the podcast script for briefings."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the briefing writer agent.
        
        Args:
            llm: LLM provider instance
        """
        self.llm = llm
    
    def _build_system_prompt(
        self,
        cast_members: list[dict],
        cast_name: Optional[str] = None,
        cast_description: Optional[str] = None,
        topics: Optional[list[str]] = None,
        briefing_title: Optional[str] = None,
        complexity: int = 3,
        enable_non_speech_sounds: bool = False,
        breakout: Optional[dict] = None,
    ) -> str:
        """Build briefing system prompt dynamically based on cast members.
        
        Args:
            cast_members: List of dicts with 'name' and 'personality' keys, sorted by order
            cast_name: Optional name of the cast
            cast_description: Optional description of how the cast works
            topics: Optional list of topic names
            briefing_title: Optional briefing title (e.g., "Morning X" for scheduled briefings)
            complexity: Conversation complexity level 1-5
            enable_non_speech_sounds: Whether to include non-speech sounds markup guide
            
        Returns:
            System prompt string
        """
        num_hosts = len(cast_members)
        host_names = [m.get("name", f"HOST{i+1}") for i, m in enumerate(cast_members)]

        host_blocks = []
        for name, member in zip(host_names, cast_members):
            personality = get_personality(member.get("personality", "Casual"))
            lines = [f"{name}: {personality.core_trait}. {personality.voice}."]
            if personality.stance:
                lines.append(f"  Stance: {personality.stance}")
            for g in personality.get_behavioral_guidelines()[:3]:
                lines.append(f"  - {g}")
            host_blocks.append("\n".join(lines))
        hosts_text = "\n".join(host_blocks)

        if breakout and num_hosts == 1:
            host_intro = (
                f"You write {host_names[0]}'s focused breakout podcast: one subject, "
                "explored deeply for one listener."
            )
        elif breakout:
            names = ", ".join(host_names[:-1]) + f" and {host_names[-1]}"
            host_intro = (
                f"You write a focused breakout podcast hosted by {names}: one subject, "
                "explored deeply through a real conversation."
            )
        elif num_hosts == 1:
            host_intro = f"You write {host_names[0]}'s daily news podcast. One host, talking to one listener."
        else:
            names = ", ".join(host_names[:-1]) + f" and {host_names[-1]}"
            host_intro = f"You write a daily news podcast hosted by {names}. It is a conversation between people who disagree sometimes, not a news read."

        cast_description_text = f"\n\nABOUT THIS SHOW\n{cast_description.strip()}\n" if cast_description else ""

        show_name = cast_name or "the show"
        opening = briefing_title or (f"today's {self._join(topics)} briefing" if topics else "today's briefing")

        if num_hosts >= 2:
            conversation_rules = f"""- It is a conversation, not alternating monologues. A host may speak two or three times in a row, or cut in with half a sentence. Do not ping-pong {host_names[0]} / {host_names[1]} / {host_names[0]} / {host_names[1]}.
- Hosts react to each other: agree, push back, get corrected, change their mind, or refuse to. Let the stances above collide when the material invites it. Nobody has to win.
- Each host talks in their own register. If you could swap the names and nothing would change, rewrite it."""
        else:
            conversation_rules = "- Talk to the listener like a friend who happens to know this stuff. Think out loud, change your mind mid-sentence if the facts warrant it."

        if breakout and num_hosts == 1:
            format_example = f"TITLE: Why Fusion Timelines Keep Slipping\n[CHAPTER: 1 | Foundations]\n{host_names[0]}: Start with the core idea...\n[CHAPTER: 2 | Mechanism]\n{host_names[0]}: Now the machinery matters..."
        elif breakout:
            format_example = f"TITLE: Why Fusion Timelines Keep Slipping\n[CHAPTER: 1 | Foundations]\n{host_names[0]}: Start with the core idea...\n{host_names[1]}: And the first disagreement is...\n[CHAPTER: 2 | Mechanism]\n{host_names[0]}: Now the machinery matters..."
        elif num_hosts == 1:
            format_example = f"TITLE: Chips, Courts, and a Quiet Rate Cut\n{host_names[0]}: Morning. It's {show_name}, and the story I can't stop thinking about is...\n[CHAPTER: 1 | Nvidia's Export Problem]\n{host_names[0]}: So here's what actually happened..."
        else:
            format_example = f"TITLE: Chips, Courts, and a Quiet Rate Cut\n{host_names[0]}: Morning. {show_name}, {host_names[0]} here with {host_names[1]}. Did you read the Nvidia filing?\n{host_names[1]}: I read the part where they said it wouldn't affect guidance. I don't believe it.\n[CHAPTER: 1 | Nvidia's Export Problem]\n{host_names[0]}: Okay so walk me through why not..."

        bracket_rule = (
            "- The only bracketed tags allowed are [CHAPTER: ...] and the sound/pause tags listed below."
            if enable_non_speech_sounds else
            "- No stage directions, sound effects, or bracketed notes of any kind other than [CHAPTER: ...]."
        )

        episode_rules = (
            """- Stay on the single breakout subject. Build understanding in an arc rather than treating facets as separate news headlines.
- Use the retrieved pages as the factual boundary. Attribute consequential evidence naturally, distinguish evidence from interpretation, and state uncertainty where the supplied material is incomplete or disputed.
- Develop foundations, mechanisms, evidence and examples, competing viewpoints, and implications. Spend time on causal links and disagreements instead of repeating the premise."""
            if breakout
            else """- Not every story gets the same treatment. Argue about the one that deserves it; dispatch a minor one in a few lines.
- Open fast: a greeting, the show name, the hosts, and straight into the first story. Never \"there's a lot to unpack here\". If a listener name is given, use it once at the top.
- Mention the date only if a story needs it, never as an opening line."""
        )
        chapter_rule = (
            "- Use 4–6 sequential chapters for conceptual stages of the exploration, such as Foundations, Mechanism, Evidence, Debate, and Implications. These are facets of one subject, not article numbers or separate headlines."
            if breakout
            else "- Put [CHAPTER: N | Short Title] (title max 5 words) on its own line where each story starts. N is its ARTICLE number in the supplied content. Exactly one numbered chapter per selected article; no intro/outro chapter markers. Start a new Name: spoken line after every marker."
        )

        prompt = f"""{host_intro}

THE HOSTS
{hosts_text}{cast_description_text}

HOW THIS SHOW SOUNDS
{conversation_rules}
{episode_rules}
- Plain spoken English for text-to-speech. Numbers said the way a person says them. Attribute the facts that matter to their source in passing ("Reuters reports", "per the filing").

OUTPUT FORMAT
- First line: TITLE: followed by a short, glanceable episode title (max 60 characters).
- Then only spoken lines, each as "Name: what they say".
{chapter_rule}
{bracket_rule}

Example of the shape (not the content):
{format_example}

This episode is {opening}."""

        complexity_instruction = get_complexity_instruction(complexity)
        non_speech_sounds_section = NON_SPEECH_SOUNDS_GUIDE if enable_non_speech_sounds else ""
        return prompt + complexity_instruction + non_speech_sounds_section

    @staticmethod
    def _join(items: list[str]) -> str:
        if not items:
            return ""
        if len(items) == 1:
            return items[0]
        if len(items) == 2:
            return f"{items[0]} and {items[1]}"
        return ", ".join(items[:-1]) + f", and {items[-1]}"

    def _build_user_prompt(
        self,
        content: str,
        topics: list[str],
        duration: int,
        user_name: Optional[str] = None,
        additional_facts: Optional[dict[int, list[str]]] = None,
        ranked_items: Optional[list] = None,
        recent_articles: Optional[list[dict]] = None,
        last_script: Optional[str] = None,
        prior_titles: Optional[list[str]] = None,
        host_research=None,
        breakout: Optional[dict] = None,
    ) -> str:
        """Build user prompt for briefing generation.
        
        Args:
            content: News content to discuss
            topics: List of topics to focus on
            duration: Target duration in minutes
            user_name: Optional user name for personalized introduction
            additional_facts: Dictionary mapping article index (0-based) to lists of additional facts
            ranked_items: List of ranked news items (used to match facts to articles)
            recent_articles: List of recent articles from previous briefings for continuity context
            last_script: Transcript from the last briefing with matching topics (for continuity/reference)
            
        Returns:
            User prompt string
        """
        from app.config import get_settings
        from app.utils.timezone import get_time_of_day, local_now

        settings = get_settings()
        now = local_now()
        current_date_time = now.strftime("%A, %B %d, %Y at %I:%M %p")
        time_of_day = get_time_of_day(settings.timezone)
        topics_str = self._join(topics) if topics else "general news"

        if breakout:
            word_target = target_words_for_duration(duration)
            listener_line = (
                f"- Listener: {user_name} (greet them by name once at the top)"
                if user_name
                else "- Listener: not named"
            )
            focus = str(breakout.get("focus") or "").strip()
            return f"""Write a {duration}-minute breakout episode about one subject: {breakout.get('topic', topics_str)}.
Requested focus: {focus or 'No narrower focus supplied.'}

SOURCE MATERIAL
{content}

CONTEXT
- Now: {current_date_time} ({settings.timezone}), {time_of_day}
{listener_line}

SHAPE
- Form one coherent deep dive that moves through foundations, mechanisms, source-backed evidence and examples, competing viewpoints, and implications.
- Use 4–6 short conceptual chapters. The chapters are stages of deeper exploration, not multiple headlines.
- Treat the source episode context as framing only, not independent evidence. Base factual claims on the fetched page content above.
- Do not invent citations, studies, quotes, or facts. When the retrieved material does not settle a point, say what remains unknown or disputed.
- Roughly {word_target} words of dialogue in total (about {duration} minutes spoken).
- Close in a line or two without recapping the whole episode.

Output the TITLE line, then the dialogue, and nothing else."""

        facts_section = ""
        if additional_facts and ranked_items:
            lines = []
            for article_idx, facts in additional_facts.items():
                if 0 <= article_idx < len(ranked_items) and facts:
                    lines.append(f"\nFACTS FOR ARTICLE {article_idx + 1}: {ranked_items[article_idx].title[:80]}")
                    lines.extend(f"  - {fact}" for fact in facts)
            if lines:
                facts_section = "\n\n=== UNVERIFIED RESEARCH LEADS (do not assert without support in the supplied articles) ===" + "\n".join(lines) + "\n"

        host_research_section = build_host_research_section(host_research, ranked_items)

        recent_section = ""
        if recent_articles:
            recent_lines = [f"- {a.get('title', 'Untitled')} ({a.get('source', 'Unknown')})" for a in recent_articles[:5]]
            recent_section = (
                "\n\n=== COVERED ON RECENT EPISODES (context only; reference if there is an update) ===\n"
                + "\n".join(recent_lines) + "\n"
            )

        continuity_section = ""
        if prior_titles:
            continuity_section = build_continuity_section(prior_titles)
        elif last_script:
            # Head of the last script, not the tail: the tail is the previous outro and
            # feeding it back tends to produce a copy of last episode's ending.
            continuity_section = (
                "\n\n=== HOW THE LAST EPISODE OPENED (tone reference only; do not repeat its stories) ===\n"
                f"{last_script[:1500]}\n"
            )

        word_target = target_words_for_duration(duration)
        listener_line = f"- Listener: {user_name} (greet them by name once at the top)" if user_name else "- Listener: not named"

        return f"""Write a {duration}-minute episode from the stories below. They are in the editor's priority order; the editor's priority and reason are shown on each.

{content}{facts_section}{host_research_section}{recent_section}{continuity_section}

CONTEXT
- Now: {current_date_time} ({settings.timezone}), {time_of_day}
{listener_line}
- Topics: {topics_str}

SHAPE
- Lead with the useful new development and why it matters; briefly supply context only when the listener has no confirmed baseline.
- Give the top story about half the runtime. The last story can be a brief exchange.
- Roughly {word_target} words of dialogue in total (about {duration} minutes spoken).
- Close in a line or two. No summary of what you just said.

Output the TITLE line, then the dialogue, and nothing else."""

    async def write_briefing(
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
        host_research=None,
        enable_non_speech_sounds: bool = False,
        briefing_id: Optional[str] = None,
        breakout: Optional[dict] = None,
    ):
        """Generate podcast script for a briefing.

        Args:
            content: News content to discuss
            topics: List of topics to focus on
            cast_members: List of cast member dicts with name, personality, etc.
            duration: Target duration in minutes
            user_name: Optional user name for personalized introduction
            complexity: Conversation complexity level 1-5
            additional_facts: Dictionary mapping article index to lists of facts
            ranked_items: List of ranked news items
            cast_name: Optional name of the cast
            cast_description: Optional description of how the cast works
            briefing_title: Optional briefing title
            recent_articles: List of recent articles for continuity
            last_script: Transcript from last briefing for continuity
            prior_titles: List of story titles covered in the last briefing (preferred over last_script)
            enable_non_speech_sounds: Whether to include non-speech sounds markup
            briefing_id: Optional briefing ID for cancellation support

        Returns:
            LLMResponse object with generated content, model, and usage info
        """
        system_prompt = self._build_system_prompt(
            cast_members=cast_members,
            cast_name=cast_name,
            cast_description=cast_description,
            topics=topics,
            briefing_title=briefing_title,
            complexity=complexity,
            enable_non_speech_sounds=enable_non_speech_sounds,
            breakout=breakout,
        )
        user_prompt = self._build_user_prompt(
            content=content,
            topics=topics,
            duration=duration,
            user_name=user_name,
            additional_facts=additional_facts,
            ranked_items=ranked_items,
            recent_articles=recent_articles,
            last_script=last_script,
            prior_titles=prior_titles,
            host_research=host_research,
            breakout=breakout,
        )

        from app.config import get_settings
        from app.services.llm.openrouter import cached_system_message

        max_tokens = tokens_for_duration(duration)
        if get_settings().llm_prompt_cache:
            messages = [
                cached_system_message(system_prompt),
                {"role": "user", "content": user_prompt},
            ]
            response = await self.llm.generate_conversation(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
                briefing_id=briefing_id,
            )
        else:
            response = await self.llm.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                briefing_id=briefing_id,
            )
        return response
