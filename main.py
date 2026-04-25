import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

load_dotenv()
console = Console()


def parse_resume(file_path: str):
    from resume_parser import ResumeParser

    console.print(Panel(f"[bold cyan]Parsing Resume:[/bold cyan] {file_path}", expand=False))
    parser = ResumeParser()
    profile = parser.parse(file_path)

    table = Table(title="Resume Profile", header_style="bold magenta")
    table.add_column("Field", style="cyan", width=25)
    table.add_column("Value", style="white")

    table.add_row("Name", profile.name)
    table.add_row("Email", profile.email)
    table.add_row("Location", profile.location)
    table.add_row("Experience", f"{profile.total_experience_years} years")
    table.add_row("Seniority", profile.seniority_level)
    table.add_row("Current Role", profile.current_role)
    table.add_row("Target Roles", "\n".join(profile.target_roles))
    table.add_row("Technical Skills", ", ".join(profile.technical_skills))
    table.add_row("Domain Skills", ", ".join(profile.domain_skills))
    table.add_row("Tools", ", ".join(profile.tools))
    table.add_row("Industries", ", ".join(profile.industries))
    table.add_row("Preferred Locations", ", ".join(profile.preferred_locations))

    console.print(table)
    console.print(Panel(f"[bold]Summary:[/bold]\n{profile.summary}", title="Professional Summary"))

    output_path = Path("profile.json")
    output_path.write_text(json.dumps(profile.model_dump(), indent=2))
    console.print(f"\n[green]Profile saved -> {output_path}[/green]")
    return profile


def scrape_news():
    from news_scraper import NewsScraper

    console.print(Panel("[bold cyan]News Scraper - Analytics Hiring Signals[/bold cyan]", expand=False))
    scraper = NewsScraper()
    leads = scraper.run(save_path="company_leads.json")
    scraper.display(leads)
    return leads


def filter_jobs():
    from job_filter import JobFilter
    from resume_parser.models import ResumeProfile
    from news_scraper.models import CompanyLead

    profile_path = Path("profile.json")
    leads_path = Path("company_leads.json")

    if not profile_path.exists():
        console.print("[red]profile.json not found.[/red] Run: python main.py resume <file>")
        sys.exit(1)
    if not leads_path.exists():
        console.print("[red]company_leads.json not found.[/red] Run: python main.py news")
        sys.exit(1)

    profile = ResumeProfile(**json.loads(profile_path.read_text()))
    leads = [CompanyLead(**l) for l in json.loads(leads_path.read_text())]

    console.print(Panel(
        f"[bold cyan]Job Filter[/bold cyan]\n"
        f"Profile: [green]{profile.name}[/green] | "
        f"Leads: [green]{len(leads)} companies[/green]",
        expand=False
    ))

    job_filter = JobFilter()
    scored = job_filter.run(profile, leads, save_path="scored_jobs.json")
    job_filter.display(scored)
    return scored


def summarize():
    from summarizer import JobSummarizer
    from job_filter.models import ScoredJob
    from resume_parser.models import ResumeProfile

    profile_path = Path("profile.json")
    scored_path = Path("scored_jobs.json")

    if not profile_path.exists():
        console.print("[red]profile.json not found.[/red] Run: python main.py resume <file>")
        sys.exit(1)
    if not scored_path.exists():
        console.print("[red]scored_jobs.json not found.[/red] Run: python main.py filter")
        sys.exit(1)

    profile = ResumeProfile(**json.loads(profile_path.read_text()))
    scored_jobs = [ScoredJob(**s) for s in json.loads(scored_path.read_text())]

    console.print(Panel(
        f"[bold cyan]Summarizer[/bold cyan]\n"
        f"Generating digest for [green]{profile.name}[/green] "
        f"from [green]{len(scored_jobs)} scored jobs[/green]",
        expand=False
    ))

    job_summarizer = JobSummarizer()
    digest = job_summarizer.summarize(scored_jobs, profile, save_path="digest.json")
    job_summarizer.display(digest, scored_jobs)
    return digest


def run_all(resume_file: str):
    """End-to-end pipeline: resume -> news -> filter -> summarize."""
    profile = parse_resume(resume_file)

    from news_scraper import NewsScraper
    scraper = NewsScraper()
    leads = scraper.run(save_path="company_leads.json")
    scraper.display(leads)

    from job_filter import JobFilter
    job_filter = JobFilter()
    scored = job_filter.run(profile, leads, save_path="scored_jobs.json")
    job_filter.display(scored)

    from summarizer import JobSummarizer
    job_summarizer = JobSummarizer()
    digest = job_summarizer.summarize(scored, profile, save_path="digest.json")
    job_summarizer.display(digest, scored)


def show_help():
    console.print(Panel(
        "[bold]Job Search Agent[/bold]\n\n"
        "[cyan]python main.py resume <file>[/cyan]    Parse resume -> profile.json\n"
        "[cyan]python main.py news[/cyan]              Scrape news -> company_leads.json\n"
        "[cyan]python main.py filter[/cyan]            Search + score jobs -> scored_jobs.json\n"
        "[cyan]python main.py summarize[/cyan]         Generate daily digest -> digest.json\n"
        "[cyan]python main.py all <file>[/cyan]        Run full pipeline end-to-end\n",
        title="Commands"
    ))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "resume":
        if len(sys.argv) < 3:
            console.print("[red]Usage:[/red] python main.py resume <file>")
            sys.exit(1)
        file_path = sys.argv[2]
        if not Path(file_path).exists():
            console.print(f"[red]File not found:[/red] {file_path}")
            sys.exit(1)
        parse_resume(file_path)

    elif command == "news":
        scrape_news()

    elif command == "filter":
        filter_jobs()

    elif command == "summarize":
        summarize()

    elif command == "all":
        if len(sys.argv) < 3:
            console.print("[red]Usage:[/red] python main.py all <resume_file>")
            sys.exit(1)
        resume_file = sys.argv[2]
        if not Path(resume_file).exists():
            console.print(f"[red]File not found:[/red] {resume_file}")
            sys.exit(1)
        run_all(resume_file)

    else:
        console.print(f"[red]Unknown command:[/red] {command}")
        show_help()
        sys.exit(1)
