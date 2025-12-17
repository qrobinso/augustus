"""News and RSS feed fetching service."""

import asyncio
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
        query: Optional[str] = None,
        categories: Optional[list[str]] = None,
        country: str = "us",
    ) -> list[NewsItem]:
        """Fetch news from NewsAPI (requires API key)."""
        if not settings.news_api_key:
            return []
        
        categories = categories or ["technology", "business", "science", "health"]
        all_items = []
        
        try:
            for category in categories:
                params = {
                    "apiKey": settings.news_api_key,
                    "country": country,
                    "category": category,
                    "pageSize": 10,
                }
                
                if query:
                    params["q"] = query
                
                response = await self.client.get(
                    "https://newsapi.org/v2/top-headlines",
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
                        category=category,
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

