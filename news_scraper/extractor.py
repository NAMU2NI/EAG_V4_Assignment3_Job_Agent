import json
import openai
from bs4 import BeautifulSoup
from .models import NewsItem, CompanyLead, SourceArticle

EXTRACT_PROMPT = """You are an analyst identifying companies that are likely hiring for Analytics/Data roles in India.

Given a batch of news article titles and summaries, extract companies that show strong hiring signals:
- Received funding (seed, series A/B/C, IPO)
- Opened or expanding a GCC (Global Capability Centre) in Bangalore/India
- Announced India expansion with analytics/data focus
- Hiring spree mentioned for tech/data roles

Return a JSON object with key "leads" containing an array. Each element:
{
  "company_name": "Acme Corp",
  "signal": "funding|gcc_expansion|hiring",
  "signal_detail": "Series B $30M for data platform",
  "location": "Bangalore",
  "domain": "Analytics|Data Engineering|BI|AI/ML",
  "source_title": "exact article title that triggered this",
  "source_url": "exact article url that triggered this",
  "relevance_score": 8
}

relevance_score: 1-10 (10 = definitely hiring analytics roles in Bangalore)

Only include companies with clear signals. Skip generic/unrelated news.
Return {{"leads": []}} if nothing relevant found.
Return ONLY valid JSON with the "leads" key, no markdown."""


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)[:3000]


def _match_articles(lead: CompanyLead, news_items: list[NewsItem]) -> list[SourceArticle]:
    """Find news items that mention this company."""
    company_lower = lead.company_name.lower()
    matched = []
    for item in news_items:
        text = (item.title + " " + item.summary).lower()
        if company_lower in text or any(w in text for w in company_lower.split() if len(w) > 4):
            matched.append(SourceArticle(
                title=item.title,
                url=item.url,
                source=item.source,
                published=item.published,
                snippet=item.summary[:200],
            ))
    # Always include the GPT-cited source if not already present
    if lead.source_url and not any(a.url == lead.source_url for a in matched):
        matched.insert(0, SourceArticle(
            title=lead.source_title,
            url=lead.source_url,
            source="",
            snippet="",
        ))
    return matched[:5]


def extract_companies(news_items: list[NewsItem], client: openai.OpenAI) -> list[CompanyLead]:
    batch = [
        {
            "title": item.title,
            "summary": item.summary[:300],
            "url": item.url,
            "source": item.source,
        }
        for item in news_items
    ]

    if not batch:
        return []

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACT_PROMPT},
            {"role": "user", "content": f"News articles:\n{json.dumps(batch, indent=2)}"},
        ],
    )

    raw = json.loads(response.choices[0].message.content)

    if isinstance(raw, dict):
        items_list = raw.get("leads", [])
        if not items_list and "company_name" in raw:
            items_list = [raw]
    elif isinstance(raw, list):
        items_list = raw
    else:
        items_list = []

    leads = []
    for item in items_list:
        if not isinstance(item, dict):
            continue
        try:
            lead = CompanyLead(**item)
            lead.source_articles = _match_articles(lead, news_items)
            leads.append(lead)
        except Exception:
            pass

    return sorted(leads, key=lambda x: x.relevance_score, reverse=True)
