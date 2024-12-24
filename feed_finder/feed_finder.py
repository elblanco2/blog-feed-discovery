import csv
import logging
import asyncio
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiohttp
import feedparser
from bs4 import BeautifulSoup
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple rate limiter for API requests."""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.rate = requests_per_second
        self.last_request = 0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """Wait if necessary to maintain rate limit."""
        async with self._lock:
            now = time.time()
            wait_time = max(0, 1/self.rate - (now - self.last_request))
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_request = time.time()

class RetryStrategy:
    """Implements exponential backoff retry strategy."""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def execute(self, coroutine, *args, **kwargs):
        """Execute coroutine with retry strategy."""
        for attempt in range(self.max_retries):
            try:
                return await coroutine(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

class FeedFinder:
    """A class to discover and validate RSS/Atom feeds from blog URLs."""

    COMMON_PATHS = [
        '/feed',
        '/rss',
        '/atom.xml',
        '/feed.xml',
        '/rss.xml',
        '/index.xml',
        '/feed/atom',
        '/feed/rss',
        '/rss/atom',
        '/blog/feed',
        '/blog.atom',
        # WordPress specific patterns
        '/feed/wp-rss2.xml',
        '/wp-feed.php',
        '/wp-rss.php',
        # Other CMS patterns
        '/blog/index.rss',
        '/syndication.axd',
    ]

    def __init__(self, 
                 timeout: int = 10, 
                 max_redirects: int = 5,
                 max_retries: int = 3,
                 requests_per_second: float = 2.0):
        """Initialize the FeedFinder.

        Args:
            timeout: Request timeout in seconds
            max_redirects: Maximum number of redirects to follow
            max_retries: Maximum number of retry attempts
            requests_per_second: Maximum requests per second
        """
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.rate_limiter = RateLimiter(requests_per_second)
        self.retry_strategy = RetryStrategy(max_retries)

    @staticmethod
    def _clean_url(url: str) -> str:
        """Clean and normalize a URL."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url.rstrip('/')

    async def _fetch_url(self, session: aiohttp.ClientSession, url: str) -> Tuple[str, int]:
        """Fetch a URL and return content and status code."""
        await self.rate_limiter.acquire()
        
        async def _fetch():
            async with session.get(url) as response:
                content = await response.text()
                return content, response.status
        
        try:
            return await self.retry_strategy.execute(_fetch)
        except Exception as e:
            logger.error(f'Error fetching {url}: {str(e)}')
            return '', 0

    async def _check_feed_url(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict]:
        """Check if a URL is a valid feed."""
        content, status = await self._fetch_url(session, url)
        if status != 200 or not content:
            return None

        feed = feedparser.parse(content)
        if feed.get('bozo', 1) == 0 and feed.get('feed', {}):
            return {
                'url': url,
                'type': 'atom' if 'atom' in content.lower() else 'rss',
                'title': feed.feed.get('title', '')
            }
        return None

    async def _find_feeds_in_html(self, session: aiohttp.ClientSession, url: str, content: str) -> List[Dict]:
        """Find feed URLs in HTML content."""
        feeds = []
        soup = BeautifulSoup(content, 'lxml')

        # Check link tags
        for link in soup.find_all('link'):
            if link.get('type') in ['application/rss+xml', 'application/atom+xml']:
                feed_url = urljoin(url, link.get('href', ''))
                if feed_url:
                    feed_info = await self._check_feed_url(session, feed_url)
                    if feed_info:
                        feeds.append(feed_info)

        # Check a tags that might be feed links
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text().lower()
            if any(word in text for word in ['rss', 'feed', 'atom', 'subscribe']):
                feed_url = urljoin(url, href)
                feed_info = await self._check_feed_url(session, feed_url)
                if feed_info:
                    feeds.append(feed_info)

        return feeds

    async def _discover_feeds(self, url: str) -> Dict:
        """Discover feeds for a given URL."""
        url = self._clean_url(url)
        result = {
            'url': url,
            'feeds': [],
            'status': 'success',
            'error': None
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                max_redirects=self.max_redirects
            ) as session:
                # Check common paths
                for path in self.COMMON_PATHS:
                    feed_url = urljoin(url, path)
                    feed_info = await self._check_feed_url(session, feed_url)
                    if feed_info:
                        result['feeds'].append(feed_info)

                # If no feeds found, check HTML
                if not result['feeds']:
                    content, status = await self._fetch_url(session, url)
                    if status == 200 and content:
                        html_feeds = await self._find_feeds_in_html(session, url, content)
                        result['feeds'].extend(html_feeds)

        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)

        return result

    def find_feed(self, url: str) -> Dict:
        """Find feeds for a single URL."""
        return asyncio.run(self._discover_feeds(url))

    async def _process_urls(self, urls: List[str]) -> List[Dict]:
        """Process multiple URLs concurrently."""
        tasks = [self._discover_feeds(url) for url in urls]
        results = []
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks)):
            results.append(await f)
        return results

    def process_file(self, input_file: str, output_file: str):
        """Process URLs from a CSV file and save results."""
        urls = []
        with open(input_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('blog_url') or row.get('url')
                if url:
                    urls.append(url)

        results = asyncio.run(self._process_urls(urls))

        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Blog URL', 'Feed URL', 'Feed Type', 'Status', 'Error'])
            
            for result in results:
                if result['feeds']:
                    for feed in result['feeds']:
                        writer.writerow([
                            result['url'],
                            feed['url'],
                            feed['type'],
                            result['status'],
                            result['error'] or ''
                        ])
                else:
                    writer.writerow([
                        result['url'],
                        '',
                        '',
                        result['status'],
                        result['error'] or 'No feeds found'
                    ])