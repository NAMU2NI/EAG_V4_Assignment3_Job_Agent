import json
import openai
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import track

from .searcher import search_jobs_for_company, fetch_all_latest_jobs
from .scorer import score_jobs
from .models import JobListing, ScoredJob
from news_scraper.models import CompanyLead
from resume_parser.models import ResumeProfile

console = Console()

MIN_SCORE_TO_KEEP = 5
SCORER_BATCH_SIZE = 10


class JobFilter:
    def __init__(self, api_key: str | None = None):
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def run(
        self,
        profile: ResumeProfile,
        leads: list[CompanyLead],
        save_path: str = "scored_jobs.json",
        max_companies: int = 10,
    ) -> list[ScoredJob]:

        top_leads = sorted(leads, key=lambda x: x.relevance_score, reverse=True)[:max_companies]
        all_jobs: list[JobListing] = []
        seen_urls: set[str] = set()

        # ── Broad latest jobs (LinkedIn + Naukri, not company-specific) ──────
        console.print("\n[bold cyan]Fetching latest Analytics/AI jobs from LinkedIn + Naukri...[/bold cyan]")
        broad_jobs = fetch_all_latest_jobs(experience=int(profile.total_experience_years))
        li_count = sum(1 for j in broad_jobs if j.source == "linkedin")
        nk_count = sum(1 for j in broad_jobs if j.source == "naukri")
        console.print(f"  LinkedIn: [cyan]{li_count}[/cyan]  |  Naukri: [yellow]{nk_count}[/yellow]")

        for job in broad_jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)

        # ── Company-specific search for high-signal leads ────────────────────
        console.print(f"\n[bold cyan]Targeting {len(top_leads)} high-signal companies...[/bold cyan]")
        for lead in track(top_leads, description="Company search..."):
            jobs = search_jobs_for_company(lead.company_name)
            new = [j for j in jobs if j.url not in seen_urls]
            for j in new:
                seen_urls.add(j.url)
                all_jobs.append(j)
            console.print(f"  [dim]{lead.company_name}[/dim] -> {len(new)} new listings")

        console.print(f"\n[green]Total unique listings: {len(all_jobs)}[/green]")

        if not all_jobs:
            console.print("[yellow]No listings found.[/yellow]")
            return []

        # ── Score ─────────────────────────────────────────────────────────────
        console.print("\n[bold cyan]Scoring against your profile...[/bold cyan]")
        all_scored: list[ScoredJob] = []
        batches = [all_jobs[i:i+SCORER_BATCH_SIZE] for i in range(0, len(all_jobs), SCORER_BATCH_SIZE)]

        for batch in track(batches, description="Scoring..."):
            scored = score_jobs(batch, profile, self.client)
            all_scored.extend(scored)

        filtered = [s for s in all_scored if s.match_score >= MIN_SCORE_TO_KEEP]
        filtered.sort(key=lambda x: x.match_score, reverse=True)

        Path(save_path).write_text(json.dumps([s.model_dump() for s in filtered], indent=2))
        console.print(f"\n[green]Saved {len(filtered)} matched jobs -> {save_path}[/green]")

        return filtered

    def display(self, scored_jobs: list[ScoredJob]):
        table = Table(title="Matched Jobs", show_lines=True)
        table.add_column("#", width=3, justify="right")
        table.add_column("Role", style="bold cyan", width=28)
        table.add_column("Company", style="yellow", width=20)
        table.add_column("Src", width=8)
        table.add_column("Match", justify="center", width=6)
        table.add_column("Fit", width=12)
        table.add_column("Posted", width=12)

        colors = {"strong fit": "green", "good fit": "cyan", "partial fit": "yellow", "skip": "red"}
        src_colors = {"linkedin": "blue", "naukri": "magenta"}

        for i, sj in enumerate(scored_jobs, 1):
            color = colors.get(sj.recommendation, "white")
            src = sj.job.source
            sc = src_colors.get(src, "white")
            table.add_row(
                str(i),
                sj.job.title[:28],
                sj.job.company[:20],
                f"[{sc}]{src[:7]}[/{sc}]",
                f"[{color}]{sj.match_score}/10[/{color}]",
                f"[{color}]{sj.recommendation}[/{color}]",
                sj.job.posted_date[:10],
            )

        console.print(table)
