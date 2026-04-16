"""Briefing Writer Agent - generates podcast script content for briefings."""

from typing import Optional

from app.services.llm.base import LLMProvider
from app.services.llm.prompts import (
    COMPLEXITY_LEVELS,
    get_complexity_instruction,
)
from app.services.llm.personalities import get_personality


# Non-speech sounds guide for Gemini TTS
NON_SPEECH_SOUNDS_GUIDE = """

=== NON-SPEECH SOUNDS & STYLE MARKUP ===

Use these tags FREQUENTLY to add realism, natural pacing, and break up the script:

SOUNDS (audible vocalizations): [sigh], [laughing], [uhm]
STYLE (modifies delivery): [sarcasm], [shouting], [whispering], [extremely fast]
PAUSES: [short pause] ~250ms, [medium pause] ~500ms, [long pause] ~1s

CRITICAL - USE FREQUENTLY:
- [uhm] - Use this OFTEN (2-4 times per segment) at natural thinking/transition points to make speech feel more natural and conversational. Examples: "So... [uhm] what I think is...", "That's interesting because [uhm] it shows...", "Well [uhm] the thing is..."
- [short pause] - Use this FREQUENTLY (3-5 times per segment) to break up sentences and create natural rhythm. Place after commas, before important points, or between thoughts. Examples: "The key point here [short pause] is that...", "So what happened [short pause] was...", "This matters because [short pause] it affects..."

Examples:
- "That's... [sigh] honestly not surprising."
- "[laughing] Okay, that's actually pretty clever."
- "So... [uhm] what happens next? [short pause] Well, the thing is..."
- "[sarcasm] Oh yes, because that worked so well last time."
- "[whispering] Here's the thing most people don't realize... [short pause] It's actually..."
- "The data shows [uhm] [short pause] that we're seeing a significant shift."
- "I think [uhm] the important part here [short pause] is understanding why this happened."

Guidelines: 
- Use [uhm] and [short pause] FREQUENTLY throughout each segment (not just a few times) to create natural, conversational pacing
- Place [uhm] at natural thinking points, transitions, or when a host is formulating a thought
- Place [short pause] to break up longer sentences, emphasize points, or create natural rhythm
- Use other sounds (sigh, laughing, etc.) sparingly and match them to the host's personality
- The goal is to make the dialogue feel like a real conversation, not a script being read
"""

# Conversational dynamics for natural multi-host dialogue
CONVERSATIONAL_DYNAMICS = """
=== CONVERSATIONAL DYNAMICS ===

Real conversations aren't perfectly choreographed. Add these natural patterns throughout:

FRICTION & PUSHBACK:
- One host challenges an assumption: "Wait, doesn't that contradict what they said last quarter?"
- Genuine skepticism: "I don't know, I'm not totally sold on that read..."
- Requesting clarification: "Hang on, walk me through that again—why would they do that?"
- Mild disagreement: "See, I read that differently..." or "I think that's only half the story."

INCOMPLETE THOUGHTS & CALLBACKS:
- Start a point, get interrupted, return to it: "Actually—going back to what I was saying about [X]..."
- Callbacks to earlier in the conversation: "This connects to that [topic] thing we mentioned earlier..."
- Self-revision: "Wait, actually... let me rephrase that."
- Building on partner's point: "To add to that..." or "That reminds me..."

KNOWLEDGE ASYMMETRY:
- One host genuinely learns something: "Oh, I didn't realize that. So basically..."
- Admitting uncertainty: "I'm not sure I fully understand their angle here..."
- Asking for the other's take: "What's your read on this?"

TANGENTS & RECOVERY:
- Brief tangent that gets pulled back: "—anyway, that's a whole other thing. Point is..."
- Catching yourself: "Sorry, I'm going down a rabbit hole. The main takeaway is..."

Use these SPARINGLY (2-4 instances per segment). They should feel organic, not forced. The goal is texture, not chaos.
"""


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
        
        # Build host descriptions
        host_descriptions = []
        host_names = []
        
        for i, member in enumerate(cast_members):
            name = member.get("name", f"HOST{i+1}")
            personality_name = member.get("personality", "Casual")
            
            # Get personality instance
            personality = get_personality(personality_name)
            personality_data = personality.get_description()
            
            host_names.append(name)
            
            # Build detailed personality description
            core_trait = personality_data.get("core_trait", "")
            voice = personality_data.get("voice", "")
            role = personality_data.get("role", "")
            personality_params = personality_data.get("personality_params", "")
            
            # Get behavioral guidelines for this personality
            behavioral_guidelines = personality.get_behavioral_guidelines()
            guidelines_text = ""
            if behavioral_guidelines:
                guidelines_text = "\n" + "\n".join(f"- {guideline}" for guideline in behavioral_guidelines)
            
            if num_hosts == 1:
                # Single host - narrator style
                host_descriptions.append(
                    f"{name}: You are the podcast host. "
                    f"Core trait: {core_trait}. "
                    f"Voice: {voice}. "
                    f"Role: {role}. You provide the main narrative and context, explaining complex topics clearly. "
                    f"Personality parameters: {personality_params}. "
                    f"Keep the tone engaging and informative while maintaining your distinctive style."
                    f"{guidelines_text}"
                )
            elif num_hosts == 2:
                # Two hosts - conversation style
                if i == 0:
                    host_descriptions.append(
                        f"{name}: The lead anchor. "
                        f"Core trait: {core_trait}. "
                        f"Voice: {voice}. "
                        f"Role: {role}. Provides the main narrative and context. Keeps the tone engaging while being informative. "
                        f"Personality parameters: {personality_params}."
                        f"{guidelines_text}"
                    )
                else:
                    host_descriptions.append(
                        f"{name}: The co-host. "
                        f"Core trait: {core_trait}. "
                        f"Voice: {voice}. "
                        f"Role: {role}. Adds depth and unique perspectives. Asks insightful questions and offers analysis. "
                        f"Personality parameters: {personality_params}."
                        f"{guidelines_text}"
                    )
            else:
                # Three hosts - panel style
                roles = ["lead anchor", "analyst", "contributor"]
                host_descriptions.append(
                    f"{name}: The {roles[i]}. "
                    f"Core trait: {core_trait}. "
                    f"Voice: {voice}. "
                    f"Role: {role}. Contributes to the discussion with your unique perspective and style. "
                    f"Personality parameters: {personality_params}."
                    f"{guidelines_text}"
                )
        
        # Build context for introduction (briefing title OR topics)
        briefing_name = ""
        if briefing_title:
            briefing_name = briefing_title
        elif topics:
            if len(topics) == 1:
                briefing_name = f"your {topics[0]} briefing"
            elif len(topics) == 2:
                briefing_name = f"your {topics[0]} and {topics[1]} briefing"
            else:
                topics_str = ", ".join(topics[:-1]) + f", and {topics[-1]}"
                briefing_name = f"your {topics_str} briefing"
        
        # Build natural podcast intro instructions
        show_name = cast_name or "the show"
        other_hosts = ", ".join(host_names[1:]) if len(host_names) > 1 else ""
        all_hosts_str = ", ".join(host_names[:-1]) + f", and {host_names[-1]}" if len(host_names) > 2 else " and ".join(host_names) if len(host_names) == 2 else host_names[0]
        
        # Build dynamic topic presentation examples
        topic_intro_examples = []
        if topics:
            if len(topics) == 1:
                topic_intro_examples = [
                    f"we're diving into {topics[0]} today",
                    f"today's focus is {topics[0]}",
                    f"we're covering {topics[0]}",
                    f"let's talk {topics[0]}",
                    f"today's briefing is all about {topics[0]}",
                ]
            elif len(topics) == 2:
                topic_intro_examples = [
                    f"we're covering {topics[0]} and {topics[1]} today",
                    f"today's focus is {topics[0]} and {topics[1]}",
                    f"we're diving into {topics[0]} and {topics[1]}",
                    f"let's talk {topics[0]} and {topics[1]}",
                    f"today we're looking at {topics[0]} and {topics[1]}",
                ]
            else:
                topics_str = ", ".join(topics[:-1]) + f", and {topics[-1]}"
                topic_intro_examples = [
                    f"we're covering {topics_str} today",
                    f"today's focus is {topics_str}",
                    f"we're diving into {topics_str}",
                    f"let's talk {topics_str}",
                    f"today we're looking at {topics_str}",
                ]
        
        intro_examples = []
        if num_hosts == 1:
            if topics:
                topic_intro_0 = topic_intro_examples[0] if topic_intro_examples else "Let's get into it."
                topic_intro_1 = topic_intro_examples[1] if len(topic_intro_examples) > 1 else "Let's dive in."
                topic_intro_2 = topic_intro_examples[2] if len(topic_intro_examples) > 2 else "let's dive in."
                intro_examples = [
                    f"'Hey, welcome back! This is {show_name}, I'm {host_names[0]}. {topic_intro_0}'",
                    f"'Good morning! Welcome to {show_name}, I'm {host_names[0]}. {topic_intro_1}'",
                    f"'What's up everyone, welcome back to {show_name}. I'm {host_names[0]}, {topic_intro_2}'",
                ]
            else:
                intro_examples = [
                    f"'Hey, welcome back! This is {show_name}, I'm {host_names[0]}. Let's get into it.'",
                    f"'Good morning! Welcome to {show_name}, I'm {host_names[0]}. We've got a lot to cover today.'",
                    f"'What's up everyone, welcome back to {show_name}. I'm {host_names[0]}, let's dive in.'",
                ]
        elif num_hosts == 2:
            if topics:
                topic_intro_0 = topic_intro_examples[0] if topic_intro_examples else "Let's get into it."
                topic_intro_1 = topic_intro_examples[1] if len(topic_intro_examples) > 1 else "Good to be here."
                topic_intro_2 = topic_intro_examples[2] if len(topic_intro_examples) > 2 else "Let's dive in."
                intro_examples = [
                    f"'Hey, welcome back to {show_name}! I'm {host_names[0]} alongside {host_names[1]}. {topic_intro_0}'",
                    f"'Good morning everyone! This is {show_name}, I'm {host_names[0]}.' followed by '{host_names[1]}: And I'm {host_names[1]}. {topic_intro_1}'",
                    f"'What's going on everybody, welcome to {show_name}. I'm {host_names[0]}, got {host_names[1]} with me today. {topic_intro_2}'",
                ]
            else:
                intro_examples = [
                    f"'Hey, welcome back to {show_name}! I'm {host_names[0]} alongside {host_names[1]}. Let's get into it.'",
                    f"'Good morning everyone! This is {show_name}, I'm {host_names[0]}.' followed by '{host_names[1]}: And I'm {host_names[1]}. Good to be here.'",
                    f"'What's going on everybody, welcome to {show_name}. I'm {host_names[0]}, got {host_names[1]} with me today.'",
                ]
        else:
            if topics:
                topic_intro_0 = topic_intro_examples[0] if topic_intro_examples else "Let's get into it."
                topic_intro_1 = topic_intro_examples[1] if len(topic_intro_examples) > 1 else "Let's dive in."
                topic_intro_2 = topic_intro_examples[2] if len(topic_intro_examples) > 2 else "Let's get started."
                intro_examples = [
                    f"'Hey, welcome back to {show_name}! I'm {host_names[0]} here with {other_hosts}. {topic_intro_0}'",
                    f"'Good morning everyone! This is {show_name}. I'm {host_names[0]}.' followed by the other hosts briefly greeting, then '{topic_intro_1}'",
                    f"'What's up everybody, welcome to {show_name}. I'm {host_names[0]}, joined by {other_hosts}. {topic_intro_2}'",
                ]
            else:
                intro_examples = [
                    f"'Hey, welcome back to {show_name}! I'm {host_names[0]} here with {other_hosts}. Let's get into it.'",
                    f"'Good morning everyone! This is {show_name}. I'm {host_names[0]}.' followed by the other hosts briefly greeting.",
                    f"'What's up everybody, welcome to {show_name}. I'm {host_names[0]}, joined by {other_hosts}. We've got a packed show.'",
                ]
        
        # Build topic mention instruction
        topic_instruction = ""
        if topics:
            if len(topics) == 1:
                topic_instruction = f"""
CRITICAL: You MUST mention the topic "{topics[0]}" in the opening. Vary how you present it - don't use the same phrase every time. Examples of dynamic ways to mention it:
- "we're diving into {topics[0]} today"
- "today's focus is {topics[0]}"
- "we're covering {topics[0]}"
- "let's talk {topics[0]}"
- "today's briefing is all about {topics[0]}"
- "we're looking at {topics[0]}"
- "let's get into {topics[0]}"
"""
            elif len(topics) == 2:
                topic_instruction = f"""
CRITICAL: You MUST mention both topics "{topics[0]}" and "{topics[1]}" in the opening. Vary how you present them - don't use the same phrase every time. Examples of dynamic ways to mention them:
- "we're covering {topics[0]} and {topics[1]} today"
- "today's focus is {topics[0]} and {topics[1]}"
- "we're diving into {topics[0]} and {topics[1]}"
- "let's talk {topics[0]} and {topics[1]}"
- "today we're looking at {topics[0]} and {topics[1]}"
- "we're exploring {topics[0]} and {topics[1]}"
"""
            else:
                topics_str = ", ".join(topics[:-1]) + f", and {topics[-1]}"
                topic_instruction = f"""
CRITICAL: You MUST mention all the topics ({topics_str}) in the opening. Vary how you present them - don't use the same phrase every time. Examples of dynamic ways to mention them:
- "we're covering {topics_str} today"
- "today's focus is {topics_str}"
- "we're diving into {topics_str}"
- "let's talk {topics_str}"
- "today we're looking at {topics_str}"
- "we're exploring {topics_str}"
"""
        
        # Build banter instruction for multi-host shows
        banter_instruction = ""
        if num_hosts >= 2:
            host_personality_hints = []
            for member in cast_members:
                name = member.get("name", "Host")
                personality_name = member.get("personality", "Casual")
                host_personality_hints.append(f"{name} ({personality_name})")
            hosts_hint = ", ".join(host_personality_hints)
            
            banter_instruction = f"""
PLAYFUL BANTER: After introductions but BEFORE the first story, include 2-4 lines of brief, playful banter between hosts. This should:
- Be grounded in the ACTUAL CONTENT - tease an upcoming story, react to a headline, or express excitement/skepticism about something you'll discuss
- OR reference previous shows - "Remember when we talked about X last time? Well..." or "Called it!" moments
- Reflect each host's personality ({hosts_hint}) - a skeptic might groan about a story, an optimist might be excited
- Be short and punchy - not a full conversation
- Naturally set up or transition into the first story

Examples of good banter:
- "Did you see that [Company] headline?" / "Oh, we're definitely getting into that one. I have thoughts."
- "Remember when we said [prediction] last week?" / "And look what happened. Called it."
- "I've been waiting all morning to talk about this first story." / "The [topic] thing? Yeah, that's a wild one."
- "You ready for this one?" / "I saw the headlines. This is going to be good."
"""
        
        if briefing_name:
            cast_intro_text = f"""Start with a natural, conversational greeting - like a real podcast. Lead with "welcome back", "hey everyone", "good morning", etc. Then mention this is {briefing_name} and introduce the hosts naturally.
{topic_instruction}
Vary your openings - don't use the same format every time. Some examples:
{chr(10).join('- ' + ex for ex in intro_examples)}

Keep the intro itself SHORT (1-2 sentences max). Don't list the date in the opening line - weave it in naturally later if needed.
{banter_instruction}
After any banter, jump into the first story with concrete details. DO NOT use filler phrases like:
- "there's a lot to unpack here"
- "we've got a lot to cover"
- "there's a lot happening"
- "we've got some interesting stuff"

Instead, transition from banter to the actual story content naturally. For example:
- BAD: "Alright, there's a lot to unpack here today..."
- GOOD: "Alright, first up - [company] just announced [specific detail]..."
"""
        else:
            cast_intro_text = f"""Start with a natural, conversational greeting - like a real podcast. Lead with "welcome back", "hey everyone", "good morning", etc. Then introduce the show and hosts naturally.
{topic_instruction}
Vary your openings - don't use the same format every time. Some examples:
{chr(10).join('- ' + ex for ex in intro_examples)}

Keep the intro itself SHORT (1-2 sentences max). Don't list the date in the opening line - weave it in naturally later if needed.
{banter_instruction}
After any banter, jump into the first story with concrete details. DO NOT use filler phrases like:
- "there's a lot to unpack here"
- "we've got a lot to cover"
- "there's a lot happening"
- "we've got some interesting stuff"

Instead, transition from banter to the actual story content naturally. For example:
- BAD: "Alright, there's a lot to unpack here today..."
- GOOD: "Alright, first up - [company] just announced [specific detail]..."
"""
        
        # Build format example based on number of hosts
        if num_hosts == 1:
            format_example = f"TITLE: Tech & Business Update - Dec 15\n{host_names[0]}: Hey, welcome back to {show_name}! I'm {host_names[0]}. We're diving into tech today.\n[CHAPTER: Tech News]\n{host_names[0]}: First up, let's talk about..."
            host_intro = f"You are {host_names[0]}, an expert podcast host creating insightful daily audio briefings."
            style_note = "Your Style:\n- Engaging solo narration - like a knowledgeable friend explaining the news\n"
        elif num_hosts == 2:
            format_example = f"TITLE: Tech & Business Update - Dec 15\n{host_names[0]}: Hey everyone, welcome back to {show_name}! I'm {host_names[0]} here with {host_names[1]}. We're covering tech and business today.\n{host_names[1]}: Good to be here. Did you see that [Company] announcement this morning?\n{host_names[0]}: Oh yeah, we're definitely getting into that. I have thoughts.\n[CHAPTER: Tech News]\n{host_names[0]}: Alright, so [Company] just announced [specific detail]..."
            host_intro = f"You are a team of two expert podcast hosts ({host_names[0]} and {host_names[1]}) creating insightful daily audio briefings."
            style_note = "Your Style:\n- Casual and informative - like smart friends having an engaging conversation about the news\n"
        else:
            format_example = f"TITLE: Tech & Business Update - Dec 15\n{host_names[0]}: What's up everybody, welcome back to {show_name}! I'm {host_names[0]}, got {other_hosts} with me. We're diving into tech, business, and more.\n{host_names[1]}: Good to be here.\n{host_names[2]}: Yeah, I've been waiting to talk about that first story all morning.\n{host_names[1]}: The [Company] thing? That one's wild.\n{host_names[0]}: Let's get into it.\n[CHAPTER: Tech News]\n{host_names[1]}: So [Company] just announced [specific detail]...\n{host_names[0]}: That's interesting because...\n{host_names[2]}: I think what's really important here is..."
            host_intro = f"You are a team of three expert podcast hosts ({host_names[0]}, {host_names[1]}, and {host_names[2]}) creating insightful daily audio briefings."
            style_note = "Your Style:\n- Engaging panel discussion - like knowledgeable friends having a dynamic conversation about the news\n"
        
        # Collect personality-specific system prompt additions
        personality_additions = []
        for i, member in enumerate(cast_members):
            name = member.get("name", f"HOST{i+1}")
            personality_name = member.get("personality", "Casual")
            personality = get_personality(personality_name)
            addition = personality.get_system_prompt_addition(name, i, num_hosts)
            if addition:
                personality_additions.append(addition)
        
        personality_additions_text = ""
        if personality_additions:
            personality_additions_text = "\n\n" + "\n".join(personality_additions) + "\n"
        
        # Add cast description if provided
        cast_description_text = ""
        if cast_description:
            cast_description_text = f"""

=== CAST DESCRIPTION ===
{cast_description}

This description provides context about how this cast works and should guide the overall tone, style, and approach of the briefing.
"""
        
        # Build the prompt
        prompt = f"""{host_intro}

{chr(10).join(host_descriptions)}
{personality_additions_text}
{cast_description_text}
{style_note}- Go beyond headlines to explain WHY stories matter
- Connect dots between stories and broader trends
- Provide historical context when relevant
- Offer balanced perspectives on complex issues
- Use analogies and examples to make abstract concepts concrete
- Keep it relaxed and conversational, not formal or stiff
{CONVERSATIONAL_DYNAMICS if num_hosts >= 2 else ''}
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
{f"- CRITICAL FOR {num_hosts}+ HOSTS: Mix up the order and frequency of who speaks. Don't always go in the same sequence (e.g., {host_names[0]} -> {host_names[1]} -> {host_names[2]}). Vary it naturally - sometimes {host_names[1]} might speak twice in a row, or {host_names[2]} might jump in before {host_names[1]}. Make it feel like a real conversation where people naturally interject and respond, not a rigid rotation. Different hosts should speak different amounts based on their personality and the topic at hand." if num_hosts > 2 else ""}
{f"- Incorporate natural conversational friction—pushback, clarifications, incomplete thoughts (see CONVERSATIONAL DYNAMICS section above)" if num_hosts >= 2 else ""}

AVOID:
- Excessive fluffy language or embellishment (e.g., "incredibly fascinating", "absolutely amazing", "truly remarkable" - occasional use is fine, but don't overdo it)
- Catastrophizing or exaggerating severity (e.g., avoid "devastating", "catastrophic", "disastrous" unless truly warranted by facts)
- Overly dramatic language or hyperbole
- Overuse of qualifiers (e.g., "very", "really", "quite" are fine occasionally, but don't lean on them)
- Sensationalism - stick to facts and measured analysis
- Doom-and-gloom framing - present information accurately without making things sound worse than they are

CRITICAL OUTPUT RULES:
- FIRST: Output a short, glanceable podcast title (max 60 characters) that includes the key topics. Format: TITLE: [title here]
- THEN: Output ONLY spoken dialogue - what the hosts actually say out loud
- INCLUDE chapter markers to break up the content into logical sections. Format: [CHAPTER: Short Title Here] where the title is no more than 5 words. Place chapter markers at natural transition points between major topics or stories. Each chapter should represent a distinct story or topic being discussed.
- BEFORE EACH CHAPTER MARKER: Add a natural transition phrase or sentence that signals a topic change, followed by a medium pause. Examples: "Alright, let's shift gears here...", "Moving on to something completely different...", "Now, switching topics entirely...", "Let's talk about something else now...", "Okay, completely different subject...", "Now, onto a different story...", "Let's pivot to another topic...", "Switching gears completely...", "Alright, moving on...", "Now for something different...". Then add [medium pause] before the chapter marker to create a clear break.
- TRANSITIONS: Use varied, natural transition phrases before chapters. Don't repeat the same transition. Make it feel like hosts are naturally moving between topics in conversation.
- DO NOT include stage directions, sound effects, or production notes like [MUSIC], [INTRO], [OUTRO], etc. (except [medium pause] which is allowed before chapter markers)
- DO NOT include asterisks or brackets with instructions like *laughs*, *sighs*, [clears throat]
- DO NOT include timestamps or other section headers

CRITICAL: {cast_intro_text}

Format your response EXACTLY like this:
{format_example}

If a user name is provided, greet them naturally (e.g., "Hey David!" or "What's up, David?"). Keep it casual - don't force it into every sentence.

When the time of day context is provided, use an appropriate greeting naturally:
- Morning: "Good morning!" or "Rise and shine!"
- Afternoon: "Good afternoon!" or "Hope you're having a great afternoon!"
- Evening: "Good evening!" or "Hope you're winding down nicely!"
- Night: "Good evening!" or "Hope you're having a relaxing evening!"

About the date: Don't put the date in the opening line - it sounds robotic. Instead, weave the date naturally into the content when referencing specific stories (e.g., "So this news just dropped today..." or mentioning the day of week). If you must reference the date explicitly, do it casually mid-briefing, not as part of the intro.

When specific topics are provided, make sure to cover stories from ALL of those topics and reference them naturally throughout the conversation. The conversation should feel like {('a knowledgeable friend' if num_hosts == 1 else 'smart friends')} casually discussing the news, informative but never stuffy or overly formal."""
        
        # Add complexity instruction
        complexity_instruction = get_complexity_instruction(complexity)
        
        # Add non-speech sounds guide if enabled
        non_speech_sounds_section = ""
        if enable_non_speech_sounds:
            non_speech_sounds_section = NON_SPEECH_SOUNDS_GUIDE
        
        return prompt + complexity_instruction + non_speech_sounds_section
    
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
        
        # Get current date and time in user's timezone
        now = local_now()
        current_date_time = now.strftime("%B %d, %Y at %I:%M %p")
        
        # Get time of day based on user's timezone
        time_of_day = get_time_of_day(settings.timezone)
        timezone = settings.timezone
        
        # Format topics list
        if topics:
            if len(topics) == 1:
                topics_str = topics[0]
            elif len(topics) == 2:
                topics_str = f"{topics[0]} and {topics[1]}"
            else:
                topics_str = ", ".join(topics[:-1]) + f", and {topics[-1]}"
        else:
            topics_str = "general news"
        
        # Format user name for display
        user_name_display = user_name if user_name else "the listener"
        
        # Add personalized name instruction if provided
        name_instruction = ""
        if user_name:
            name_instruction = f"\n\nIMPORTANT: Address the listener by name ({user_name}) in the opening introduction. For example: 'Hey {user_name}, let's kick off today's briefing' or 'Good morning, {user_name}! Let's dive into today's top stories...'"
        
        # Format additional facts section
        additional_facts_section = ""
        if additional_facts and ranked_items:
            facts_lines = []
            for article_idx, facts in additional_facts.items():
                if 0 <= article_idx < len(ranked_items) and facts:
                    article = ranked_items[article_idx]
                    article_num = article_idx + 1
                    article_title = article.title[:80]
                    facts_lines.append(f"\nADDITIONAL FACTS FOR ARTICLE {article_num}: {article_title}")
                    for i, fact in enumerate(facts, 1):
                        facts_lines.append(f"  {i}. {fact}")
            
            if facts_lines:
                additional_facts_section = "\n\n=== ADDITIONAL QUANTIFIABLE FACTS ===\n" + "\n".join(facts_lines) + "\n"
                additional_facts_section += "\nThese facts are provided to add concrete, quantifiable data to the discussion. Incorporate them naturally into the conversation when discussing the corresponding articles.\n"
        
        # Format recent articles section
        recent_articles_section = ""
        if recent_articles:
            articles_lines = []
            articles_lines.append("\n\n=== RECENT ARTICLES FROM PREVIOUS BRIEFINGS (FOR CONTINUITY CONTEXT) ===\n")
            articles_lines.append("The following articles were discussed in recent briefings on these topics. They are provided for context and continuity.")
            articles_lines.append("You do NOT need to discuss these articles in the current briefing, but you can reference them if they provide relevant context or if there are updates to these stories.\n")
            
            for i, article in enumerate(recent_articles[:5], 1):
                articles_lines.append(f"\nRECENT ARTICLE {i}:")
                articles_lines.append(f"Title: {article.get('title', 'Untitled')}")
                articles_lines.append(f"Source: {article.get('source', 'Unknown')}")
                if article.get('summary'):
                    articles_lines.append(f"Summary: {article.get('summary', '')[:200]}")
                if article.get('fetched_at'):
                    articles_lines.append(f"Previously discussed: {article.get('fetched_at', '')}")
            
            articles_lines.append("\nThese articles are for reference only - focus on the new articles provided in the main content section above.")
            recent_articles_section = "\n".join(articles_lines)
        
        # Format last script section
        last_script_section = ""
        if last_script:
            script_preview = last_script[-2000:] if len(last_script) > 2000 else last_script
            last_script_section = f"""

=== LAST SCRIPT FROM PREVIOUS BRIEFING (FOR CONTINUITY REFERENCE) ===
The following is the transcript from the last briefing generated with the same set of topics. This is provided for context, continuity, and reference.

IMPORTANT INSTRUCTIONS:
- Use this as a reference to understand what was discussed previously
- Maintain continuity in tone, style, and approach
- DO NOT repeat the same stories, facts, or points that were already covered
- If referencing a previous story, provide an UPDATE or NEW ANGLE, not a rehash
- Build on what was discussed before, don't duplicate it
- Vary your language and phrasing - avoid using the same expressions or transitions
- If the last script covered certain topics extensively, focus on different aspects or new developments

Last script transcript:
{script_preview}

Remember: This is for reference only. Create fresh content that builds on this foundation without repeating it.
"""
        
        prompt = f"""Create an engaging {duration}-minute daily briefing podcast script covering the following news and information:

{content}
{additional_facts_section}
{recent_articles_section}
{last_script_section}

IMPORTANT CONTEXT FOR THIS BRIEFING:
- Current date and time: {current_date_time} (based on the listener's timezone: {timezone})
- Listener's name: {user_name_display}
- Topics to focus on: {topics_str}
- Time of day: {time_of_day}
{name_instruction}

NOTE: When you need to reference dates in the briefing, use the current date provided above. Don't announce the date in the opening - weave it naturally into the content when discussing specific stories.

The hosts should clearly reference these specific topics throughout the briefing and ensure coverage across all of them.

Requirements:
1. OPENING: Keep the introduction brief (1-2 sentences max). You MUST mention the topics being covered in the opening - vary how you present them (e.g., "we're covering [topics]", "today's focus is [topics]", "let's dive into [topics]"). After mentioning the topics, IMMEDIATELY jump into the first story with concrete details. DO NOT use filler phrases like "there's a lot to unpack here" or "we've got a lot to cover" - go straight to the actual story content.
2. HOOK: Start with the most compelling story. Be direct and clear - no need to allude or build suspense. Jump right into the details of what happened.
3. CONTEXT: For each major story, explain:
   - What happened (the facts)
   - Why it matters (the significance)  
   - What it means going forward (implications)
   - How it connects to bigger trends or other stories
4. ADDITIONAL FACTS: When discussing each article, incorporate the additional quantifiable facts provided above that correspond to that specific article. These facts should be woven naturally into the conversation to provide concrete data and evidence, making the discussion more informative and less "fluffy". Use these facts to ground the conversation in real numbers and statistics when covering each story.
5. ANALYSIS: Have hosts ask insightful questions and offer unique perspectives
6. DEPTH: Go beyond surface-level reporting - help listeners truly understand the stories
7. CONNECTIONS: Draw connections between different stories when relevant
8. BALANCE: Present multiple viewpoints on controversial topics
9. CHAPTER TRANSITIONS: Before each new chapter marker, add a natural transition phrase that signals a topic change (e.g., "Alright, let's shift gears here...", "Moving on to something completely different...", "Now, switching topics entirely...", "Let's talk about something else now..."). Vary these transitions - don't repeat the same phrase. Immediately after the transition phrase, add [medium pause] to create a clear break before the chapter marker.
10. WRAP-UP: At the end, work backwards to summarize what topics were discussed. Recap the key stories and takeaways, reinforcing what listeners learned.

CRITICAL LANGUAGE GUIDELINES:
- Use clear, direct language - avoid fluffy filler words and unnecessary embellishment
- Present facts accurately without catastrophizing or exaggerating severity
- Avoid sensationalism - stick to measured, factual analysis
- Don't use dramatic language unless the situation genuinely warrants it
- Be informative and engaging without being hyperbolic or alarmist
- Keep it substantive and insightful - listeners should come away feeling smarter about the world, not anxious or misled

Total speaking time: approximately {duration} minutes

OUTPUT FORMAT:
1. First, provide a short, glanceable podcast title (max 60 characters) that includes the key topics being discussed. Format: TITLE: [title here]
2. Then, provide the podcast script dialogue between the hosts.

Example:
TITLE: Tech & Business Update - Jan 15
HOST1: Good morning! Welcome back to the show.
HOST2: Good to be here.
Alright, let's dive into the tech news. [medium pause]
[CHAPTER: Tech News]
HOST1: First up, [Company] just announced [specific detail]...
HOST2: That's interesting because...
[After discussing tech news, transition to next chapter]
HOST1: Moving on to something completely different now. [medium pause]
[CHAPTER: Business Update]
HOST2: So in business news today...

REMEMBER: 
- The title should be short, glanceable, and include key topics
- Add natural transition phrases before each chapter marker, followed by [medium pause]
- Use varied transition phrases - don't repeat the same one
- Output ONLY the title line and spoken dialogue - no stage directions, no music cues (except [medium pause] before chapters)
- Start directly with the TITLE line, then the first host speaking

Generate the podcast script now:"""
        
        return prompt
    
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
        enable_non_speech_sounds: bool = False,
        briefing_id: Optional[str] = None,
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
        )

        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=4096,
            temperature=0.7,
            briefing_id=briefing_id,
        )

        return response

