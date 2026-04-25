import feedparser
import httpx
from bs4 import BeautifulSoup
from .models import NewsItem

SEARCH_QUERIES = [
    ("analytics startup funding india", "funding"),
    ("data analytics company funding india 2025", "funding"),
    ("GCC Bangalore 2025", "gcc_expansion"),
    ("global capability centre Bangalore analytics", "gcc_expansion"),
    ("analytics hiring Bangalore 2025", "hiring"),
]

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
YOURSTORY_RSS = "https://yourstory.com/feed"
INC42_RSS = "https://inc42.com/feed/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    return soup.get_text(separator=" ", strip=True)[:400]


def _resolve_google_url(url: str, timeout: int = 8) -> str:
    """Follow Google News redirect to get the actual article URL."""
    try:
        with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            return str(r.url)
    except Exception:
        return url


def _fetch_article_snippet(url: str, timeout: int = 8) -> str:
    """Fetch first 800 chars of article body text."""
    try:
        with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)[:800]
    except Exception:
        return ""


def fetch_google_news(query: str, max_items: int = 10) -> list[NewsItem]:
    url = GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        raw_summary = entry.get("summary", "")
        clean_summary = _strip_html(raw_summary)

        # If summary is empty after stripping (Google News gives HTML junk),
        # fall back to fetching the article directly
        article_text = ""
        article_url = entry.get("link", "")
        if not clean_summary and article_url:
            article_text = _fetch_article_snippet(article_url)

        items.append(NewsItem(
            title=entry.get("title", ""),
            url=article_url,
            source=entry.get("source", {}).get("title", "Google News"),
            published=entry.get("published", ""),
            summary=clean_summary or article_text[:400],
        ))
    return items


def fetch_rss_feed(rss_url: str, source_name: str, max_items: int = 15) -> list[NewsItem]:
    feed = feedparser.parse(rss_url)
    items = []
    for entry in feed.entries[:max_items]:
        raw = entry.get("summary", "") or entry.get("description", "")
        items.append(NewsItem(
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            source=source_name,
            published=entry.get("published", ""),
            summary=_strip_html(raw),
        ))
    return items


def collect_all_news() -> list[NewsItem]:
    all_items: list[NewsItem] = []
    seen_urls: set[str] = set()

    for query, _ in SEARCH_QUERIES:
        items = fetch_google_news(query, max_items=8)
        for item in items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                all_items.append(item)

    for rss_url, name in [(YOURSTORY_RSS, "YourStory"), (INC42_RSS, "Inc42")]:
        try:
            items = fetch_rss_feed(rss_url, name, max_items=20)
            for item in items:
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    all_items.append(item)
        except Exception:
            pass

    return all_items
