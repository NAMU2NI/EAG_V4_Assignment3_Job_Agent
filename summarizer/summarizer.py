import json
import openai
from datetime import date
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text
from rich import box

from job_filter.models import ScoredJob
from resume_parser.models import ResumeProfile

console = Console()

DIGEST_PROMPT = """You are a career advisor summarizing job opportunities for a job seeker.

Candidate: {name} | {experience} years experience | {seniority} level | Skills: {top_skills}

Given these scored job matches, produce a concise daily digest with:

1. "top_picks": Top 3-5 jobs worth applying to immediately (score >= 7). For each:
   - why it's a strong fit in 1 sentence
   - one key thing to highlight from their profile in the cover letter / interview

2. "skill_gaps": Skills that appear frequently in job descriptions but candidate lacks. Max 5.

3. "market_insight": 2-3 sentence observation about what the job market is signaling today
   (e.g. which tools are in demand, what seniority is being hired, which companies are hot).

4. "preparation_tips": 3 specific actionable tips before applying to these roles.

5. "daily_summary": 2-sentence TL;DR the candidate can read in 10 seconds.

Jobs data:
{jobs}

Return ONLY valid JSON, no markdown:
{{
  "top_picks": [
    {{
      "rank": 1,
      "title": "...",
      "company": "...",
      "score": 9,
      "why_fit": "...",
      "highlight_for_application": "...",
      "url": "..."
    }}
  ],
  "skill_gaps": ["dbt", "Snowflake", ...],
  "market_insight": "...",
  "preparation_tips": ["...", "...", "..."],
  "daily_summary": "..."
}}"""


class JobSummarizer:
    def __init__(self, api_key: str | None = None):
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def summarize(
        self,
        scored_jobs: list[ScoredJob],
        profile: ResumeProfile,
        save_path: str = "digest.json",
    ) -> dict:
        if not scored_jobs:
            console.print("[yellow]No scored jobs to summarize.[/yellow]")
            return {}

        jobs_payload = [
            {
                "title": sj.job.title,
                "company": sj.job.company,
                "location": sj.job.location,
                "url": sj.job.url,
                "score": sj.match_score,
                "recommendation": sj.recommendation,
                "matched_skills": sj.matched_skills,
                "missing_skills": sj.missing_skills,
                "reasoning": sj.gpt_reasoning,
                "description": sj.job.description[:300],
            }
            for sj in scored_jobs[:20]  # top 20 is enough context
        ]

        top_skills = (profile.technical_skills + profile.domain_skills + profile.tools)[:12]

        response = self.client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": DIGEST_PROMPT.format(
                        name=profile.name,
                        experience=profile.total_experience_years,
                        seniority=profile.seniority_level,
                        top_skills=", ".join(top_skills),
                        jobs=json.dumps(jobs_payload, indent=2),
                    ),
                },
                {"role": "user", "content": "Generate today's job digest."},
            ],
        )

        digest = json.loads(response.choices[0].message.content)
        digest["generated_on"] = str(date.today())
        digest["total_matches"] = len(scored_jobs)
        digest["candidate"] = profile.name

        Path(save_path).write_text(json.dumps(digest, indent=2))
        console.print(f"[green]Digest saved -> {save_path}[/green]")

        return digest

    def display(self, digest: dict, scored_jobs: list[ScoredJob]):
        if not digest:
            return

        # ── Header ──────────────────────────────────────────────────────────
        console.print(Panel(
            f"[bold white]{digest.get('daily_summary', '')}[/bold white]",
            title=f"[bold cyan] Daily Job Digest - {digest.get('generated_on', '')} [/bold cyan]",
            subtitle=f"[dim]{digest.get('total_matches', 0)} matches found for {digest.get('candidate', '')}[/dim]",
            border_style="cyan",
            padding=(1, 2),
        ))

        # ── Top Picks ────────────────────────────────────────────────────────
        console.print("\n[bold cyan] Top Picks - Apply Today[/bold cyan]")
        picks_table = Table(show_lines=True, box=box.ROUNDED, border_style="cyan")
        picks_table.add_column("#", width=3, justify="right")
        picks_table.add_column("Role", style="bold", width=28)
        picks_table.add_column("Company", style="yellow", width=18)
        picks_table.add_column("Score", justify="center", width=7)
        picks_table.add_column("Why It Fits", width=35)
        picks_table.add_column("Highlight", style="dim", width=35)

        for pick in digest.get("top_picks", []):
            score = pick.get("score", 0)
            color = "green" if score >= 8 else "cyan"
            picks_table.add_row(
                str(pick.get("rank", "")),
                pick.get("title", "")[:28],
                pick.get("company", "")[:18],
                f"[{color}]{score}/10[/{color}]",
                pick.get("why_fit", "")[:80],
                pick.get("highlight_for_application", "")[:80],
            )

        console.print(picks_table)

        # ── Skill Gaps ───────────────────────────────────────────────────────
        gaps = digest.get("skill_gaps", [])
        if gaps:
            console.print(f"\n[bold yellow] Skill Gaps to Address:[/bold yellow]  " +
                          "  ".join(f"[red]{g}[/red]" for g in gaps))

        # ── Market Insight ───────────────────────────────────────────────────
        insight = digest.get("market_insight", "")
        if insight:
            console.print(Panel(
                insight,
                title="[bold magenta] Market Insight[/bold magenta]",
                border_style="magenta",
                padding=(0, 2),
            ))

        # ── Preparation Tips ─────────────────────────────────────────────────
        tips = digest.get("preparation_tips", [])
        if tips:
            console.print("\n[bold green] Before You Apply:[/bold green]")
            for i, tip in enumerate(tips, 1):
                console.print(f"  [green]{i}.[/green] {tip}")

        # ── Full Ranked List ─────────────────────────────────────────────────
        if scored_jobs:
            console.print("\n[bold cyan] All Matched Jobs (ranked)[/bold cyan]")
            full_table = Table(show_lines=False, box=box.SIMPLE, border_style="dim")
            full_table.add_column("#", width=4, justify="right")
            full_table.add_column("Role", width=30)
            full_table.add_column("Company", style="yellow", width=20)
            full_table.add_column("Score", justify="center", width=7)
            full_table.add_column("Fit", width=12)
            full_table.add_column("URL", style="dim blue", width=40)

            fit_colors = {"strong fit": "green", "good fit": "cyan", "partial fit": "yellow", "skip": "red"}
            for i, sj in enumerate(scored_jobs, 1):
                color = fit_colors.get(sj.recommendation, "white")
                full_table.add_row(
                    str(i),
                    sj.job.title[:30],
                    sj.job.company[:20],
                    f"[{color}]{sj.match_score}/10[/{color}]",
                    f"[{color}]{sj.recommendation}[/{color}]",
                    sj.job.url[:40],
                )

            console.print(full_table)
