"""Web scraper service for fetching articles from custom sites."""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.services.news import NewsItem


class ScraperService:
    """Service for scraping articles from custom websites."""
    
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
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
        return self._client
    
    async def fetch_site_articles(
        self,
        url: str,
        site_name: str,
        category: str,
        max_articles: int = 3,
    ) -> list[NewsItem]:
        """Fetch articles from a website and extract content from each article page.
        
        Args:
            url: The website URL to scrape
            site_name: Display name for the source
            category: Category to assign to articles
            max_articles: Maximum number of articles to return (default 3)
            
        Returns:
            List of NewsItem objects with full article content
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            
            articles = []
            
            # Try multiple strategies to find articles
            article_elements = self._find_article_elements(soup)
            
            for element in article_elements[:max_articles * 3]:  # Get extra in case some fail
                article = self._extract_article_from_element(element, base_url, site_name, category)
                if article and article.title and article.url:
                    # Avoid duplicates
                    if not any(a.url == article.url for a in articles):
                        articles.append(article)
                
                if len(articles) >= max_articles:
                    break
            
            # If we didn't find articles with structured elements, try link-based extraction
            if len(articles) < max_articles:
                link_articles = self._extract_articles_from_links(soup, base_url, site_name, category)
                for article in link_articles:
                    if not any(a.url == article.url for a in articles):
                        articles.append(article)
                    if len(articles) >= max_articles:
                        break
            
            # Limit to max_articles before fetching full content
            articles = articles[:max_articles]
            
            # Fetch full content from each article page
            enriched_articles = await self._enrich_articles_with_content(articles)
            
            return enriched_articles
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            raise
    
    async def _enrich_articles_with_content(
        self,
        articles: list[NewsItem],
    ) -> list[NewsItem]:
        """Visit each article URL and extract fuller content/synopsis.
        
        Args:
            articles: List of NewsItem objects with URLs
            
        Returns:
            List of NewsItem objects with enriched content
        """
        async def fetch_article_content(article: NewsItem) -> NewsItem:
            """Fetch and extract content from a single article page."""
            try:
                response = await self.client.get(article.url, timeout=15.0)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove unwanted elements
                for tag in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
                    tag.decompose()
                
                # Try to find the main article content
                content = self._extract_article_content(soup)
                
                if content and len(content) > len(article.summary or ""):
                    # Create a new NewsItem with the enriched content
                    return NewsItem(
                        title=article.title,
                        summary=content[:200],  # First 200 chars as summary
                        url=article.url,
                        source=article.source,
                        published=article.published,
                        author=article.author,
                        category=article.category,
                        # No separate content field - summary is sufficient
                    )
                
                return article
                
            except Exception as e:
                print(f"[Scraper] Could not fetch article content from {article.url}: {e}")
                return article
        
        # Fetch all articles concurrently
        tasks = [fetch_article_content(article) for article in articles]
        enriched = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid articles
        result = []
        for item in enriched:
            if isinstance(item, NewsItem):
                result.append(item)
            elif isinstance(item, Exception):
                print(f"[Scraper] Article fetch failed: {item}")
        
        return result
    
    def _extract_article_content(self, soup: BeautifulSoup) -> str:
        """Extract the main article content from a page.
        
        Args:
            soup: BeautifulSoup object of the article page
            
        Returns:
            Extracted article text content
        """
        content_parts = []
        
        # Strategy 1: Look for article tag
        article = soup.find('article')
        if article:
            # Look for paragraphs within the article
            paragraphs = article.find_all('p')
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50:  # Skip very short paragraphs
                    content_parts.append(text)
        
        # Strategy 2: Look for common content container classes
        if not content_parts:
            content_selectors = [
                {'class_': re.compile(r'article.*(body|content|text)', re.I)},
                {'class_': re.compile(r'(post|entry|story).*(body|content|text)', re.I)},
                {'class_': re.compile(r'^(content|main|body)$', re.I)},
                {'itemprop': 'articleBody'},
            ]
            
            for selector in content_selectors:
                container = soup.find(['div', 'section', 'article'], **selector)
                if container:
                    paragraphs = container.find_all('p')
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if len(text) > 50:
                            content_parts.append(text)
                    if content_parts:
                        break
        
        # Strategy 3: Find the div with the most paragraph content
        if not content_parts:
            divs = soup.find_all('div')
            best_div = None
            best_score = 0
            
            for div in divs:
                paragraphs = div.find_all('p', recursive=False)
                score = sum(len(p.get_text(strip=True)) for p in paragraphs)
                if score > best_score:
                    best_score = score
                    best_div = div
            
            if best_div and best_score > 200:
                paragraphs = best_div.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 50:
                        content_parts.append(text)
        
        # Combine and clean up
        content = ' '.join(content_parts)
        
        # Clean up extra whitespace
        content = re.sub(r'\s+', ' ', content).strip()
        
        # Limit to reasonable length
        if len(content) > 2000:
            content = content[:2000] + "..."
        
        return content
    
    def _find_article_elements(self, soup: BeautifulSoup) -> list:
        """Find article elements using various strategies."""
        elements = []
        
        # Strategy 1: Look for <article> tags
        elements.extend(soup.find_all('article', limit=20))
        
        # Strategy 2: Look for common article container classes
        article_classes = [
            'post', 'article', 'entry', 'story', 'news-item',
            'blog-post', 'content-item', 'feed-item', 'card'
        ]
        for cls in article_classes:
            elements.extend(soup.find_all(class_=re.compile(cls, re.I), limit=20))
        
        # Strategy 3: Look for elements with common article ID patterns
        elements.extend(soup.find_all(id=re.compile(r'post-\d+|article-\d+', re.I), limit=20))
        
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for el in elements:
            el_id = id(el)
            if el_id not in seen:
                seen.add(el_id)
                unique.append(el)
        
        return unique
    
    def _extract_article_from_element(
        self,
        element,
        base_url: str,
        site_name: str,
        category: str,
    ) -> Optional[NewsItem]:
        """Extract article information from an HTML element."""
        try:
            # Find title
            title = None
            title_element = (
                element.find(['h1', 'h2', 'h3', 'h4'], class_=re.compile(r'title|headline', re.I)) or
                element.find(['h1', 'h2', 'h3', 'h4']) or
                element.find(class_=re.compile(r'title|headline', re.I))
            )
            if title_element:
                title = title_element.get_text(strip=True)
            
            # Find link
            url = None
            link = (
                element.find('a', class_=re.compile(r'title|headline|link', re.I)) or
                (title_element.find('a') if title_element else None) or
                element.find('a', href=True)
            )
            if link and link.get('href'):
                url = urljoin(base_url, link['href'])
                # Use link text as title if we didn't find one
                if not title:
                    title = link.get_text(strip=True)
            
            # Find summary/description
            summary = ""
            summary_element = (
                element.find(class_=re.compile(r'summary|excerpt|description|preview|teaser', re.I)) or
                element.find('p')
            )
            if summary_element:
                summary = summary_element.get_text(strip=True)[:500]
            
            # Find date
            published = self._extract_date(element)
            
            # Find author
            author = None
            author_element = element.find(class_=re.compile(r'author|byline|writer', re.I))
            if author_element:
                author = author_element.get_text(strip=True)
                # Clean up common prefixes
                author = re.sub(r'^(by|author:?)\s*', '', author, flags=re.I).strip()
            
            if not title or not url:
                return None
            
            # Filter out non-article links
            if self._is_likely_navigation_link(url, title):
                return None
            
            return NewsItem(
                title=title,
                summary=summary,
                url=url,
                source=site_name,
                published=published,
                author=author,
                category=category,
            )
            
        except Exception:
            return None
    
    def _extract_articles_from_links(
        self,
        soup: BeautifulSoup,
        base_url: str,
        site_name: str,
        category: str,
    ) -> list[NewsItem]:
        """Extract articles by finding links that look like article URLs."""
        articles = []
        
        # Look for links with article-like URLs
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            full_url = urljoin(base_url, href)
            title = link.get_text(strip=True)
            
            # Skip if no meaningful title
            if not title or len(title) < 10:
                continue
            
            # Check if URL looks like an article
            if not self._is_article_url(full_url):
                continue
            
            # Skip navigation links
            if self._is_likely_navigation_link(full_url, title):
                continue
            
            # Look for nearby summary text
            summary = ""
            parent = link.find_parent(['div', 'article', 'section', 'li'])
            if parent:
                # Find a paragraph near the link
                p = parent.find('p')
                if p and p != link:
                    summary = p.get_text(strip=True)[:500]
            
            articles.append(NewsItem(
                title=title,
                summary=summary,
                url=full_url,
                source=site_name,
                category=category,
            ))
        
        return articles
    
    def _extract_date(self, element) -> Optional[datetime]:
        """Try to extract a publication date from an element."""
        # Look for time elements
        time_el = element.find('time')
        if time_el:
            datetime_attr = time_el.get('datetime')
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                except Exception:
                    pass
        
        # Look for date in common class patterns
        date_el = element.find(class_=re.compile(r'date|time|published|posted', re.I))
        if date_el:
            date_text = date_el.get_text(strip=True)
            parsed = self._parse_date_text(date_text)
            if parsed:
                return parsed
        
        return None
    
    def _parse_date_text(self, text: str) -> Optional[datetime]:
        """Try to parse various date formats."""
        import re
        
        # Clean up text
        text = text.strip()
        
        # Handle relative dates
        relative_patterns = [
            (r'(\d+)\s*min(ute)?s?\s*ago', lambda m: datetime.utcnow() - timedelta(minutes=int(m.group(1)))),
            (r'(\d+)\s*hour?s?\s*ago', lambda m: datetime.utcnow() - timedelta(hours=int(m.group(1)))),
            (r'(\d+)\s*day?s?\s*ago', lambda m: datetime.utcnow() - timedelta(days=int(m.group(1)))),
            (r'yesterday', lambda m: datetime.utcnow() - timedelta(days=1)),
            (r'today', lambda m: datetime.utcnow()),
        ]
        
        for pattern, handler in relative_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    return handler(match)
                except Exception:
                    pass
        
        # Try common date formats
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%m/%d/%Y',
            '%d/%m/%Y',
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(text[:len(text)], fmt)
            except Exception:
                continue
        
        return None
    
    def _is_article_url(self, url: str) -> bool:
        """Check if a URL looks like an article URL."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # Article URLs often have these patterns
        article_patterns = [
            r'/\d{4}/\d{2}/',  # Date-based paths like /2024/01/
            r'/article/',
            r'/post/',
            r'/blog/',
            r'/news/',
            r'/story/',
            r'\.html?$',
            r'/p/',  # Medium-style
            r'-[a-z0-9]{6,}$',  # Slug patterns
        ]
        
        for pattern in article_patterns:
            if re.search(pattern, path):
                return True
        
        # Also check for long paths with multiple segments (likely articles)
        segments = [s for s in path.split('/') if s]
        if len(segments) >= 2 and len(segments[-1]) > 10:
            return True
        
        return False
    
    def _is_likely_navigation_link(self, url: str, title: str) -> bool:
        """Check if a link is likely navigation rather than an article."""
        title_lower = title.lower()
        url_lower = url.lower()
        
        nav_keywords = [
            'about', 'contact', 'privacy', 'terms', 'login', 'signup',
            'register', 'subscribe', 'home', 'menu', 'search', 'category',
            'tag', 'archive', 'author', 'all posts', 'read more', 'see more',
            'view all', 'next', 'previous', 'older', 'newer'
        ]
        
        for keyword in nav_keywords:
            if keyword in title_lower or f'/{keyword}' in url_lower:
                return True
        
        # Very short titles are often navigation
        if len(title) < 15 and not any(c.isdigit() for c in title):
            return True
        
        return False
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
_scraper_service: Optional[ScraperService] = None


def get_scraper_service() -> ScraperService:
    """Get or create scraper service instance."""
    global _scraper_service
    if _scraper_service is None:
        _scraper_service = ScraperService()
    return _scraper_service

