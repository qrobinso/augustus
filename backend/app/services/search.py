"""Web search service for research."""

import asyncio
from typing import Optional
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

settings = get_settings()


@dataclass
class SearchResult:
    """Represents a search result."""
    title: str
    url: str
    snippet: str
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
        }


class SearchService:
    """Service for web search using DuckDuckGo HTML (no API required)."""
    
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
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
        return self._client
    
    async def search_duckduckgo(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[SearchResult]:
        """Search using DuckDuckGo HTML (no API key required)."""
        try:
            # Use DuckDuckGo HTML search
            encoded_query = quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for result in soup.select('.result')[:num_results]:
                title_elem = result.select_one('.result__title')
                snippet_elem = result.select_one('.result__snippet')
                link_elem = result.select_one('.result__a')
                
                if title_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    href = link_elem.get('href', '')
                    
                    # Extract actual URL from DuckDuckGo redirect
                    url = href
                    if 'uddg=' in href:
                        try:
                            from urllib.parse import parse_qs, urlparse
                            parsed = urlparse(href)
                            params = parse_qs(parsed.query)
                            if 'uddg' in params:
                                url = params['uddg'][0]
                        except:
                            pass
                    
                    if not url.startswith('http'):
                        continue
                    
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append(SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet[:500],
                    ))
            
            return results
            
        except Exception as e:
            print(f"DuckDuckGo search failed: {e}")
            return []
    
    async def search(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[SearchResult]:
        """Search the web for information."""
        results = await self.search_duckduckgo(query, num_results)
        return results
    
    async def fetch_page_content(self, url: str) -> Optional[str]:
        """Fetch and extract text content from a URL."""
        try:
            response = await self.client.get(url, timeout=15.0)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript']):
                element.decompose()
            
            # Try to find main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            # Clean up whitespace
            text = ' '.join(text.split())
            
            # Limit length
            return text[:5000]
            
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            return None
    
    async def research_topic(
        self,
        query: str,
        num_sources: int = 5,
    ) -> tuple[str, list[SearchResult]]:
        """Research a topic by searching and fetching content.
        
        Returns:
            Tuple of (combined research text, list of sources)
        """
        # Search for relevant pages
        results = await self.search(query, num_sources * 2)
        
        if not results:
            # Return a basic response if no results
            return f"Search query: {query}\n\nNo search results were found. Please generate content based on general knowledge about this topic.", []
        
        # Fetch content from top results
        research_parts = []
        valid_sources = []
        
        for result in results[:num_sources]:
            content = await self.fetch_page_content(result.url)
            
            if content and len(content) > 100:
                research_parts.append(f"""
Source: {result.title}
URL: {result.url}
Content: {content[:2000]}
""")
                valid_sources.append(result)
            elif result.snippet:
                # Use snippet as fallback
                research_parts.append(f"""
Source: {result.title}
URL: {result.url}
Summary: {result.snippet}
""")
                valid_sources.append(result)
        
        if not research_parts:
            # Fallback to snippets only
            for result in results[:num_sources]:
                if result.snippet:
                    research_parts.append(f"""
Source: {result.title}
URL: {result.url}
Summary: {result.snippet}
""")
                    valid_sources.append(result)
        
        combined_research = "\n---\n".join(research_parts) if research_parts else f"Topic: {query}"
        
        return combined_research, valid_sources
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_search_service: Optional[SearchService] = None


def get_search_service() -> SearchService:
    """Get or create search service instance."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
