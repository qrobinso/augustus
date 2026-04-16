"""Facts Gatherer Agent - gathers additional quantifiable facts and interesting details about news stories."""

import json
from typing import Optional

from app.services.llm.base import LLMProvider
from app.services.search import get_search_service


class FactsGathererAgent:
    """Agent responsible for gathering additional facts about news stories."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize the facts gatherer agent.
        
        Args:
            llm: LLM provider instance
        """
        self.llm = llm
        self.search_service = get_search_service()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for facts gathering.
        
        Returns:
            System prompt string
        """
        return """You are a research expert specializing in deep analysis of news stories. Your task is to analyze each selected news story by generating essential questions and providing detailed answers that capture the main points and core meaning of the text.

For each article, you must:
1. Generate 5 essential questions that, when answered, capture the main points and core meaning of the text
2. When formulating your questions, ensure they:
   a. Address the central theme or argument
   b. Identify key supporting ideas
   c. Highlight important facts or evidence
   d. Reveal the author's purpose or perspective
   e. Explore any significant implications or conclusions
3. Answer all of your generated questions one-by-one in detail

CRITICAL REQUIREMENTS:
- READ THE FULL ARTICLE CONTENT and ADDITIONAL WEB CONTENT when provided - they contain much more detail than the summary
- The ADDITIONAL WEB CONTENT section contains content fetched directly from the article page or alternative sources - use this to find deeper insights, data points, and interesting details
- Your questions should be thoughtful and probe the deeper meaning, context, and implications of the story
- Answers should be detailed, comprehensive, and include:
  - Quantifiable data when available (numbers, percentages, statistics, specific data points)
  - Evidence-based information from the article and web content
  - Historical context, comparisons, or implications
  - Specific quotes, examples, or nuanced information
  - Connections to broader trends or themes
- Each answer should be substantial (3-5 sentences minimum) and provide meaningful depth
- Questions and answers should help readers understand the "what", "why", and "so what" of the story
- Analyze each article independently - questions and answers should be specific to that story's content and subject matter
- If you cannot generate meaningful questions and answers for an article, return an empty questions array for that article

OUTPUT FORMAT (JSON only):
```json
{
  "articles": [
    {
      "article_num": 1,
      "title": "Article title",
      "questions_and_answers": [
        {
          "question": "What is the central theme or argument of this article?",
          "answer": "Detailed answer addressing the central theme, including specific evidence, data points, and context from the article..."
        },
        {
          "question": "What are the key supporting ideas or evidence presented?",
          "answer": "Comprehensive answer identifying and explaining the main supporting points, with specific examples, statistics, or data..."
        },
        {
          "question": "What important facts or evidence are highlighted in this story?",
          "answer": "Detailed answer covering quantifiable data, statistics, research findings, or verifiable facts mentioned in the article..."
        },
        {
          "question": "What is the author's purpose or perspective in writing this article?",
          "answer": "In-depth answer analyzing the author's intent, viewpoint, and how the article is framed, including any bias or particular angle..."
        },
        {
          "question": "What are the significant implications or conclusions of this story?",
          "answer": "Comprehensive answer exploring the broader implications, potential consequences, future impact, or conclusions that can be drawn..."
        }
      ]
    }
  ]
}
```"""
    
    async def _fetch_article_content(self, story: dict) -> Optional[str]:
        """Fetch article content from URL, or search for alternative articles if unavailable.
        
        Args:
            story: Story dictionary with title, url, etc.
            
        Returns:
            Article content text or None if unavailable
        """
        url = story.get('url')
        if not url:
            return None
        
        # Try to fetch the original article page
        try:
            content = await self.search_service.fetch_page_content(url)
            if content and len(content) > 200:
                return content
        except Exception as e:
            print(f"Failed to fetch article from {url}: {e}")
        
        # If original article failed, search for alternative articles about the same topic
        title = story.get('title', '')
        if title:
            try:
                # Search for articles about this story
                search_query = f"{title} {story.get('summary', '')[:100]}"
                search_results = await self.search_service.search(search_query, num_results=3)
                
                # Try to fetch content from alternative articles
                for result in search_results:
                    if result.url == url:
                        continue  # Skip the original URL we already tried
                    
                    try:
                        alt_content = await self.search_service.fetch_page_content(result.url)
                        if alt_content and len(alt_content) > 200:
                            print(f"Found alternative article for '{title}': {result.url}")
                            return f"[Alternative source: {result.title}]\n{alt_content}"
                    except Exception as e:
                        print(f"Failed to fetch alternative article from {result.url}: {e}")
                        continue
            except Exception as e:
                print(f"Failed to search for alternative articles: {e}")
        
        return None
    
    def _build_user_prompt(self, stories: list[dict], additional_content: dict[int, Optional[str]]) -> str:
        """Build user prompt for facts gathering.
        
        Args:
            stories: List of story dictionaries with title, summary, source, category, url, and full_content
            additional_content: Dictionary mapping story index to additional fetched content
            
        Returns:
            User prompt string
        """
        # Format stories for the prompt
        stories_text = []
        for i, story in enumerate(stories, 1):
            story_text = f"""
STORY {i}:
Title: {story.get('title', 'Untitled')}
Source: {story.get('source', 'Unknown')}
Category: {story.get('category', 'general')}
URL: {story.get('url', 'Not available')}
Summary: {story.get('summary', 'No summary available')}
"""
            # Include full article content if available
            full_content = story.get('full_content')
            if full_content:
                story_text += f"""
FULL ARTICLE CONTENT (read this carefully for interesting details):
{full_content}
"""
            else:
                story_text += """
FULL ARTICLE CONTENT: Not available (only summary provided above)
"""
            
            # Include additional fetched content from web if available
            additional = additional_content.get(i - 1)
            if additional:
                story_text += f"""
ADDITIONAL WEB CONTENT (fetched from article page or alternative source):
{additional}
"""
            
            stories_text.append(story_text)
        
        prompt = f"""Analyze each of the following selected news stories individually by reading the FULL ARTICLE CONTENT and ADDITIONAL WEB CONTENT (when provided). For each article, generate 5 essential questions and provide detailed answers that capture the main points and core meaning.

SELECTED STORIES:
{"---".join(stories_text)}

INSTRUCTIONS:
1. For EACH article above, READ THE FULL ARTICLE CONTENT and ADDITIONAL WEB CONTENT (if provided) - they contain much more detail than the summary. The ADDITIONAL WEB CONTENT was fetched directly from the article page or alternative sources and may contain valuable data points, statistics, quotes, and deeper context.

2. Generate 5 essential questions for each article that, when answered, capture the main points and core meaning. When formulating your questions, ensure they:
   a. Address the central theme or argument
   b. Identify key supporting ideas
   c. Highlight important facts or evidence
   d. Reveal the author's purpose or perspective
   e. Explore any significant implications or conclusions

3. Answer all of your generated questions one-by-one in detail. Each answer should:
   - Be comprehensive and substantial (3-5 sentences minimum)
   - Include quantifiable data when available (numbers, percentages, statistics, specific data points)
   - Reference specific evidence, quotes, or examples from the article and web content
   - Provide historical context, comparisons, or implications when relevant
   - Help readers understand the "what", "why", and "so what" of the story
   - Connect to broader trends or themes when appropriate

4. Pay special attention to the ADDITIONAL WEB CONTENT sections - they often contain quantifiable data, specific numbers, historical context, and interesting details that aren't in the summary. Use this information to enrich your answers.

5. Each article should be analyzed separately - questions and answers should be specific to that article's content and subject matter.

6. If you cannot generate meaningful questions and answers for an article, return an empty questions_and_answers array for that article.

OUTPUT FORMAT (JSON only, no other text):
```json
{{
  "articles": [
    {{
      "article_num": 1,
      "title": "Micron is killing Crucial after nearly 30 years",
      "questions_and_answers": [
        {{
          "question": "What is the central theme or argument of this article?",
          "answer": "The central theme is Micron's strategic decision to phase out the Crucial brand after nearly 30 years, reflecting a shift in the company's branding and market positioning strategy. This move represents a consolidation of Micron's consumer memory products under its primary brand name, signaling a focus on brand unity and potentially streamlining marketing efforts in a competitive memory market."
        }},
        {{
          "question": "What are the key supporting ideas or evidence presented?",
          "answer": "The article presents several key supporting points: the Crucial brand has been a significant presence in the consumer memory market for nearly three decades, Micron is making this change as part of a broader strategic initiative, and the transition will affect how consumers identify and purchase Micron memory products. The decision reflects broader industry trends toward brand consolidation and direct-to-consumer marketing strategies."
        }},
        {{
          "question": "What important facts or evidence are highlighted in this story?",
          "answer": "Key facts include the 30-year history of the Crucial brand, Micron's position as a major memory manufacturer, and the timing of this strategic change. The article may reference market share data, consumer recognition metrics, or financial implications of maintaining multiple brands versus consolidating under a single brand identity."
        }},
        {{
          "question": "What is the author's purpose or perspective in writing this article?",
          "answer": "The author appears to be reporting on a significant brand transition in the technology industry, likely aiming to inform consumers and industry observers about the change. The perspective seems neutral and informational, focusing on the facts of the transition rather than advocating for or against the decision."
        }},
        {{
          "question": "What are the significant implications or conclusions of this story?",
          "answer": "The implications include potential changes in consumer purchasing behavior, the impact on Micron's brand recognition and market positioning, and broader industry trends toward brand consolidation. This move may signal how major technology companies are adapting their branding strategies in response to market dynamics, consumer preferences, and competitive pressures in the memory industry."
        }}
      ]
    }}
  ]
}}
```

Return ONLY the JSON output, no other text."""
        
        return prompt
    
    async def gather_facts(
        self,
        stories: list[dict],
        briefing_id: Optional[str] = None,
    ) -> tuple[dict[int, list[str]], str, dict]:
        """Gather additional facts for each story by generating questions and detailed answers.

        Args:
            stories: List of story dictionaries with title, summary, source, category, url, and full_content
            briefing_id: Optional briefing ID for cancellation support

        Returns:
            Tuple of (facts_dict, raw_response, usage)
            facts_dict: Dictionary mapping article index (0-based) to lists of formatted question-answer strings
            raw_response: Raw LLM response content
            usage: LLM usage data including cost information
        """
        # Fetch additional content from article pages or alternative sources
        print("[Facts Gatherer] Fetching additional content from article pages...")
        additional_content = {}
        for i, story in enumerate(stories):
            content = await self._fetch_article_content(story)
            if content:
                additional_content[i] = content
                print(f"[Facts Gatherer] Successfully fetched content for article {i+1}: {story.get('title', 'Untitled')[:50]}")
            else:
                print(f"[Facts Gatherer] Could not fetch content for article {i+1}: {story.get('title', 'Untitled')[:50]}")

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(stories, additional_content)

        # Call LLM to generate questions and answers
        response = await self.llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=4096,  # Increased for detailed answers
            temperature=0.5,  # Moderate temperature for factual but varied responses
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
        
        # Try multiple parsing strategies
        facts_data = None
        
        # Strategy 1: Try parsing as-is
        try:
            facts_data = json.loads(content)
        except json.JSONDecodeError as e1:
            print(f"[Facts Gatherer] Initial JSON parse failed: {e1}")
            
            # Strategy 2: Try to fix common issues and parse again
            try:
                fixed_content = self._fix_json_issues(content)
                facts_data = json.loads(fixed_content)
                print(f"[Facts Gatherer] Successfully parsed after fixing JSON issues")
            except (json.JSONDecodeError, Exception) as e2:
                print(f"[Facts Gatherer] Fixed JSON parse also failed: {e2}")
                
                # Strategy 3: Try to extract partial data using regex as fallback
                try:
                    facts_data = self._extract_partial_json(content)
                    if facts_data:
                        print(f"[Facts Gatherer] Extracted partial JSON data using fallback method")
                except Exception as e3:
                    print(f"[Facts Gatherer] Fallback extraction also failed: {e3}")
                    # Log the problematic content for debugging
                    error_pos = getattr(e1, 'pos', None)
                    if error_pos:
                        start = max(0, error_pos - 200)
                        end = min(len(content), error_pos + 200)
                        problematic_section = content[start:end]
                        print(f"[Facts Gatherer] Original error at position {error_pos}")
                        print(f"[Facts Gatherer] Problematic section: ...{problematic_section}...")
                    raise ValueError(f"Failed to parse facts agent JSON: {e1}")
        
        if not facts_data:
            raise ValueError("Failed to parse facts agent JSON: All parsing strategies failed")
        
        articles_facts = facts_data.get("articles", [])
        
        # Convert to dictionary mapping article index to formatted question-answer strings
        # Article numbers in response are 1-based, convert to 0-based index
        facts_dict = {}
        for article_data in articles_facts:
            article_num = article_data.get("article_num", 0)
            qa_pairs = article_data.get("questions_and_answers", [])
            # Convert 1-based article_num to 0-based index
            idx = article_num - 1
            if 0 <= idx < len(stories) and qa_pairs:
                # Format as list of strings: "Question: ...\nAnswer: ..."
                formatted_facts = []
                for qa in qa_pairs:
                    question = qa.get("question", "")
                    answer = qa.get("answer", "")
                    if question and answer:
                        formatted_facts.append(f"Question: {question}\nAnswer: {answer}")
                if formatted_facts:
                    facts_dict[idx] = formatted_facts
        
        # Return usage data from response
        usage = response.usage if hasattr(response, 'usage') else {}
        
        return facts_dict, raw_response, usage
    
    def _fix_json_issues(self, content: str) -> str:
        """Attempt to fix common JSON issues like unterminated strings.
        
        Args:
            content: JSON string that may have issues
            
        Returns:
            Fixed JSON string
        """
        import re
        
        # Remove trailing commas before closing braces/brackets (common JSON issue)
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # Try to fix unterminated strings by tracking string state
        # Find the main JSON object
        first_brace = content.find('{')
        if first_brace == -1:
            return content
        
        # Track state while processing
        result = []
        i = first_brace
        in_string = False
        escape_next = False
        brace_count = 0
        bracket_count = 0
        
        while i < len(content):
            char = content[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                result.append(char)
                in_string = not in_string
                i += 1
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                    result.append(char)
                elif char == '}':
                    brace_count -= 1
                    result.append(char)
                elif char == '[':
                    bracket_count += 1
                    result.append(char)
                elif char == ']':
                    bracket_count -= 1
                    result.append(char)
                else:
                    result.append(char)
                i += 1
            else:
                # We're in a string - just copy characters
                result.append(char)
                i += 1
        
        fixed_content = ''.join(result)
        
        # If we ended in a string, try to close it intelligently
        if in_string:
            # Close the string and any unclosed structures
            if bracket_count > 0:
                fixed_content += '"' + ']' * bracket_count
            if brace_count > 0:
                fixed_content += '"' + '}' * brace_count
            else:
                fixed_content += '"'
        
        # Ensure the JSON object is properly closed
        if brace_count > 0:
            fixed_content += '}' * brace_count
        if bracket_count > 0:
            fixed_content += ']' * bracket_count
        
        return fixed_content
    
    def _extract_partial_json(self, content: str) -> Optional[dict]:
        """Extract partial JSON data using regex as a fallback.
        
        Args:
            content: JSON string that failed to parse
            
        Returns:
            Dictionary with extracted data, or None if extraction fails
        """
        import re
        
        # Try to extract article data using regex patterns
        # This is a fallback when JSON parsing completely fails
        
        articles = []
        
        # Look for article patterns: "article_num": number
        article_pattern = r'"article_num"\s*:\s*(\d+)'
        article_matches = list(re.finditer(article_pattern, content))
        
        for match in article_matches:
            article_num = int(match.group(1))
            
            # Try to extract the title
            title = ""
            title_match = re.search(r'"title"\s*:\s*"([^"]*)"', content[match.start():match.start() + 2000])
            if title_match:
                title = title_match.group(1)
            
            # Try to extract questions and answers
            qa_pattern = r'"questions_and_answers"\s*:\s*\[(.*?)\]'
            qa_match = re.search(qa_pattern, content[match.start():match.start() + 5000], re.DOTALL)
            
            questions_and_answers = []
            if qa_match:
                qa_content = qa_match.group(1)
                # Try to extract individual Q&A pairs
                # More lenient pattern that handles multi-line answers
                qa_pair_pattern = r'\{\s*"question"\s*:\s*"([^"]*)"\s*,\s*"answer"\s*:\s*"([^"]*)"'
                qa_pairs = re.finditer(qa_pair_pattern, qa_content, re.DOTALL)
                for qa_pair in qa_pairs:
                    questions_and_answers.append({
                        "question": qa_pair.group(1),
                        "answer": qa_pair.group(2)
                    })
            
            if questions_and_answers:
                articles.append({
                    "article_num": article_num,
                    "title": title,
                    "questions_and_answers": questions_and_answers
                })
        
        if articles:
            return {"articles": articles}
        
        return None

