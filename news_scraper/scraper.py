import json
import openai
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import track

from .feeds import collect_all_news
from .extractor import extract_companies
from .models import NewsItem, CompanyLead

console = Console()

BATCH_SIZE = 15  # articles per OpenAI call


class NewsScraper:
    def __init__(self, api_key: str | None = None):
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def run(self, save_path: str = "company_leads.json") -> list[CompanyLead]:
        console.print("[bold cyan]Fetching news from Google News, YourStory, Inc42...[/bold cyan]")
        news_items = collect_all_news()
        console.print(f"[green]Fetched {len(news_items)} articles[/green]")

        # Save raw news items for reference in UI
        Path("news_items.json").write_text(
            json.dumps([i.model_dump() for i in news_items], indent=2)
        )

        all_leads: list[CompanyLead] = []
        batches = [news_items[i:i+BATCH_SIZE] for i in range(0, len(news_items), BATCH_SIZE)]

        for batch in track(batches, description="Extracting company leads..."):
            leads = extract_companies(batch, self.client)
            all_leads.extend(leads)

        # Deduplicate by company name — merge source articles, keep highest score
        seen: dict[str, CompanyLead] = {}
        for lead in all_leads:
            key = lead.company_name.lower().strip()
            if key not in seen:
                seen[key] = lead
            else:
                existing = seen[key]
                # Merge source articles (deduplicate by URL)
                existing_urls = {a.url for a in existing.source_articles}
                for art in lead.source_articles:
                    if art.url not in existing_urls:
                        existing.source_articles.append(art)
                        existing_urls.add(art.url)
                if lead.relevance_score > existing.relevance_score:
                    seen[key] = lead

        unique_leads = sorted(seen.values(), key=lambda x: x.relevance_score, reverse=True)

        Path(save_path).write_text(
            json.dumps([l.model_dump() for l in unique_leads], indent=2)
        )
        console.print(f"[green]Saved {len(unique_leads)} company leads -> {save_path}[/green]")

        return unique_leads

    def display(self, leads: list[CompanyLead]):
        table = Table(title="Company Leads - Analytics Hiring Signals", show_lines=True)
        table.add_column("Company", style="bold cyan", width=22)
        table.add_column("Signal", style="yellow", width=14)
        table.add_column("Detail", width=30)
        table.add_column("Domain", style="magenta", width=18)
        table.add_column("Score", justify="center", width=6)

        for lead in leads:
            score_color = "green" if lead.relevance_score >= 7 else "yellow" if lead.relevance_score >= 4 else "red"
            table.add_row(
                lead.company_name,
                lead.signal,
                lead.signal_detail[:40],
                lead.domain,
                f"[{score_color}]{lead.relevance_score}[/{score_color}]",
            )

        console.print(table)
