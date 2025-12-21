"""News and RSS feed fetching service."""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

settings = get_settings()


@dataclass
class NewsItem:
    """Represents a news article."""
    title: str
    summary: str
    url: str
    source: str
    published: Optional[datetime] = None
    author: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None  # Full article content if available
    image_url: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published": self.published.isoformat() if self.published else None,
            "author": self.author,
            "category": self.category,
            "content": self.content,
        }


class NewsService:
    """Service for fetching news from various sources."""
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Augustus/1.0 (News Aggregator)",
                },
            )
        return self._client
    
    async def fetch_rss_feed(self, url: str) -> list[NewsItem]:
        """Fetch and parse an RSS feed."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            feed = feedparser.parse(response.text)
            items = []
            
            for entry in feed.entries[:10]:  # Limit to 10 items per feed
                # Parse publication date
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                
                # Get summary, clean HTML
                summary = entry.get('summary', entry.get('description', ''))
                if summary:
                    soup = BeautifulSoup(summary, 'html.parser')
                    summary = soup.get_text()[:500]  # Limit summary length
                
                items.append(NewsItem(
                    title=entry.get('title', 'Untitled'),
                    summary=summary,
                    url=entry.get('link', ''),
                    source=feed.feed.get('title', url),
                    published=published,
                ))
            
            return items
            
        except Exception as e:
            print(f"Error fetching RSS feed {url}: {e}")
            return []
    
    async def fetch_all_feeds(
        self,
        feed_urls: Optional[list[str]] = None,
        max_age_hours: int = 24,
    ) -> list[NewsItem]:
        """Fetch news from all configured RSS feeds."""
        feed_urls = feed_urls or settings.rss_feed_list
        
        # Fetch all feeds concurrently
        tasks = [self.fetch_rss_feed(url) for url in feed_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combine and filter results
        all_items = []
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            for item in result:
                # Filter by age if published date is available
                if item.published and item.published < cutoff:
                    continue
                all_items.append(item)
        
        # Sort by publication date (newest first)
        all_items.sort(
            key=lambda x: x.published or datetime.min,
            reverse=True,
        )
        
        return all_items
    
    async def fetch_newsapi(
        self,
        topics: Optional[list[str]] = None,
        country: str = "us",
    ) -> list[NewsItem]:
        """Fetch news from NewsAPI using topic names as search queries.
        
        Args:
            topics: List of topic names to search for (e.g., ["Technology", "AI", "Climate"])
            country: Country code for news sources
            
        Returns:
            List of NewsItem objects
        """
        if not settings.news_api_key:
            return []
        
        topics = topics or ["technology", "business", "science", "health"]
        all_items = []
        
        try:
            for topic in topics:
                # Use the "everything" endpoint with topic name as query
                # This allows for custom topic searches beyond NewsAPI's fixed categories
                params = {
                    "apiKey": settings.news_api_key,
                    "q": topic,  # Use topic name as search query
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                }
                
                response = await self.client.get(
                    "https://newsapi.org/v2/everything",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                for article in data.get("articles", []):
                    # Skip articles with [Removed] content
                    if article.get("title") == "[Removed]" or article.get("content") == "[Removed]":
                        continue
                    
                    published = None
                    if article.get("publishedAt"):
                        try:
                            published = datetime.fromisoformat(
                                article["publishedAt"].replace("Z", "+00:00")
                            )
                        except Exception:
                            pass
                    
                    # Get full content if available (NewsAPI truncates at ~200 chars)
                    # The content field contains the first ~200 chars of the article body
                    content = article.get("content", "")
                    if content:
                        # Remove the truncation marker like "[+1234 chars]"
                        content = content.split("[+")[0].strip()
                    
                    # Get description (usually a longer summary)
                    description = article.get("description", "") or ""
                    
                    # Use the longer of description or content for summary
                    summary = description if len(description) > len(content or "") else (content or description)
                    
                    all_items.append(NewsItem(
                        title=article.get("title", "Untitled"),
                        summary=summary[:500] if summary else "",
                        url=article.get("url", ""),
                        source=article.get("source", {}).get("name", "NewsAPI"),
                        published=published,
                        author=article.get("author"),
                        category=topic.lower(),  # Use topic name as category
                        content=content,  # Raw content from NewsAPI (up to ~200 chars)
                        image_url=article.get("urlToImage"),
                    ))
            
            # Remove duplicates by URL
            seen_urls = set()
            unique_items = []
            for item in all_items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    unique_items.append(item)
            
            return unique_items
            
        except Exception as e:
            print(f"Error fetching from NewsAPI: {e}")
            return []
    
    @staticmethod
    def is_reddit_url(url: str) -> bool:
        """Check if a URL is a Reddit subreddit URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is a Reddit subreddit URL
        """
        if not url:
            return False
        
        url_lower = url.lower().strip()
        # Match patterns like:
        # - https://www.reddit.com/r/subreddit/
        # - https://reddit.com/r/subreddit/
        # - http://www.reddit.com/r/subreddit/
        # - r/subreddit (without domain)
        reddit_patterns = [
            r'https?://(www\.)?reddit\.com/r/[^/]+',
            r'^r/[^/]+/?$',
        ]
        
        for pattern in reddit_patterns:
            if re.search(pattern, url_lower):
                return True
        
        return False
    
    @staticmethod
    def extract_subreddit_name(url: str) -> Optional[str]:
        """Extract subreddit name from a Reddit URL.
        
        Args:
            url: Reddit URL (e.g., "https://www.reddit.com/r/technology/" or "r/technology")
            
        Returns:
            Subreddit name without r/ prefix, or None if not a valid Reddit URL
        """
        if not url:
            return None
        
        url_lower = url.lower().strip()
        
        # Pattern 1: Full URL like https://www.reddit.com/r/subreddit/
        match = re.search(r'reddit\.com/r/([^/]+)', url_lower)
        if match:
            return match.group(1)
        
        # Pattern 2: Just r/subreddit
        match = re.search(r'^r/([^/]+)', url_lower)
        if match:
            return match.group(1)
        
        return None
    
    async def fetch_reddit_subreddit(
        self,
        subreddit: str,
        max_age_days: int = 3,
        limit: int = 25,
    ) -> list[NewsItem]:
        """Fetch top posts from this week from a Reddit subreddit.
        
        Args:
            subreddit: Subreddit name without r/ prefix (e.g., "technology")
            max_age_days: Maximum age of posts in days (default 3, used for additional filtering)
            limit: Maximum number of posts to fetch (default 25)
            
        Returns:
            List of NewsItem objects from Reddit posts
        """
        if not subreddit:
            return []
        
        # Remove r/ prefix if present
        subreddit = subreddit.lstrip('r/').strip()
        if not subreddit:
            return []
        
        try:
            # Reddit JSON API endpoint for top posts from this week
            url = f"https://www.reddit.com/r/{subreddit}/top.json"
            params = {
                "limit": limit,
                "t": "week",  # Time period: week (top posts from this week)
            }
            
            # Use proper User-Agent (required by Reddit)
            headers = {
                "User-Agent": "Augustus/1.0 (News Aggregator)",
            }
            
            response = await self.client.get(url, params=params, headers=headers)
            
            # Handle rate limiting
            if response.status_code == 429:
                print(f"[News] Reddit rate limit hit for r/{subreddit}")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            # Extract posts from Reddit's nested structure
            posts = data.get("data", {}).get("children", [])
            items = []
            cutoff_time = datetime.utcnow() - timedelta(days=max_age_days)
            
            for post_data in posts:
                post = post_data.get("data", {})
                
                # Skip stickied posts (they're usually not news)
                if post.get("stickied", False):
                    continue
                
                # Get creation time
                created_utc = post.get("created_utc")
                if created_utc:
                    try:
                        published = datetime.utcfromtimestamp(created_utc)
                        # Filter by age
                        if published < cutoff_time:
                            continue
                    except (ValueError, TypeError):
                        published = None
                else:
                    published = None
                
                # Get title
                title = post.get("title", "Untitled")
                
                # Get summary from selftext (post body) or URL
                selftext = post.get("selftext", "")
                url_link = post.get("url", "")
                
                # Use selftext if available, otherwise use URL
                if selftext:
                    summary = selftext[:500]  # Limit summary length
                elif url_link and not url_link.startswith(f"https://www.reddit.com/r/{subreddit}"):
                    # External link - use URL as summary hint
                    summary = f"External link: {url_link}"
                else:
                    summary = ""
                
                # Get permalink for the post URL
                permalink = post.get("permalink", "")
                if permalink:
                    post_url = f"https://www.reddit.com{permalink}"
                else:
                    post_url = url_link if url_link else ""
                
                # Get author
                author = post.get("author", "")
                
                # Get subreddit name
                subreddit_name = post.get("subreddit", subreddit)
                
                items.append(NewsItem(
                    title=title,
                    summary=summary,
                    url=post_url,
                    source=f"r/{subreddit_name}",
                    published=published,
                    author=author if author != "[deleted]" else None,
                    category=subreddit_name.lower(),
                    content=selftext if selftext else None,
                ))
            
            # Sort by published date (newest first)
            items.sort(
                key=lambda x: x.published or datetime.min,
                reverse=True,
            )
            
            return items
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"[News] Subreddit r/{subreddit} not found")
            else:
                print(f"[News] HTTP error fetching r/{subreddit}: {e}")
            return []
        except Exception as e:
            print(f"[News] Error fetching Reddit subreddit r/{subreddit}: {e}")
            return []
    
    def format_news_for_briefing(self, items: list[NewsItem], max_stories: int = 20) -> str:
        """Format news items into rich text for LLM processing.
        
        Args:
            items: List of news items to format
            max_stories: Maximum number of stories to include (based on duration)
        """
        if not items:
            return "No recent news available."
        
        # Group by category for better context
        by_category: dict[str, list[NewsItem]] = {}
        for item in items[:max_stories]:  # Limit based on duration
            cat = item.category or "general"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)
        
        sections = []
        article_num = 1
        
        for category, cat_items in by_category.items():
            sections.append(f"\n=== {category.upper()} NEWS ===\n")
            
            for item in cat_items:
                # Calculate time ago
                time_ago = ""
                if item.published:
                    delta = datetime.utcnow() - item.published.replace(tzinfo=None)
                    if delta.days > 0:
                        time_ago = f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
                    elif delta.seconds >= 3600:
                        hours = delta.seconds // 3600
                        time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    else:
                        mins = delta.seconds // 60
                        time_ago = f"{mins} minute{'s' if mins > 1 else ''} ago"
                
                # Build rich article info with all available content
                section = f"""
ARTICLE {article_num}: {item.title}
Source: {item.source}{f' | By: {item.author}' if item.author else ''}
Published: {time_ago or 'Recently'}
Category: {category}

Summary: {item.summary}
"""
                # Add content if it provides additional context beyond the summary
                if item.content:
                    # Check if content adds new information (not just a subset of summary)
                    content_lower = item.content.lower()
                    summary_lower = item.summary.lower() if item.summary else ""
                    if content_lower not in summary_lower and len(item.content) > 50:
                        section += f"\nArticle excerpt: {item.content}\n"
                
                sections.append(section)
                article_num += 1
        
        return "\n---\n".join(sections)
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_news_service: Optional[NewsService] = None


def get_news_service() -> NewsService:
    """Get or create news service instance."""
    global _news_service
    if _news_service is None:
        _news_service = NewsService()
    return _news_service

