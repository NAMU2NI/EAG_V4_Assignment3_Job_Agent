# Job Search Agent

An agentic, AI-powered job search pipeline built in pure Python using the OpenAI API (GPT-4o). No LangChain, no CrewAI — each agent is a focused Python module with a clear input/output contract.

---

## Overview

The system works like a personal job search assistant that runs a full pipeline on your behalf:

1. Understands who you are (resume)
2. Watches the market for hiring signals (news)
3. Searches and scores relevant jobs (job filter)
4. Summarizes the best opportunities (digest)
5. Tailors your resume for the best fits (tweaker)

---

## Project Structure

```
Job Search Agent/
├── resume_parser/          # Agent 1 — Parse resume into structured profile
│   ├── extractor.py        # PDF / DOCX / TXT text extraction
│   ├── parser.py           # GPT-4o structured extraction
│   └── models.py           # ResumeProfile, WorkExperience (Pydantic)
│
├── news_scraper/           # Agent 2 — Market intelligence from news
│   ├── feeds.py            # Google News RSS + YourStory + Inc42
│   ├── extractor.py        # GPT-4o company lead extraction
│   ├── scraper.py          # Orchestrator, deduplication, saves JSON
│   └── models.py           # NewsItem, CompanyLead, SourceArticle (Pydantic)
│
├── job_filter/             # Agent 3 — Search and score jobs
│   ├── searcher.py         # LinkedIn guest API + Selenium Naukri
│   ├── scorer.py           # GPT-4o multi-dimension scoring
│   ├── filter.py           # Orchestrator, broad + targeted search
│   └── models.py           # JobListing, ScoredJob (Pydantic)
│
├── summarizer/             # Agent 4 — Daily digest
│   └── summarizer.py       # GPT-4o narrative summary
│
├── resume_tweaker/         # Agent 5 — On-demand resume tailoring
│   ├── tweaker.py          # GPT-4o minimal targeted tweaks
│   └── models.py           # TweakedResume, BulletTweak, KeywordAddition
│
├── app.py                  # Streamlit UI (4 tabs)
├── main.py                 # CLI entrypoint
├── requirements.txt
└── .env                    # OPENAI_API_KEY
```

---

## Agentic Orchestration

Each agent is an autonomous unit. They communicate through structured JSON files on disk and Pydantic models in memory. No shared state, no framework magic.

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER / UI                               │
│              (Streamlit app.py or CLI main.py)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │      Agent 1: Resume Parser  │
              │  Input : PDF / DOCX / TXT    │
              │  Tool  : pdfplumber / docx   │
              │  LLM   : GPT-4o (JSON mode)  │
              │  Output: profile.json        │
              │          ResumeProfile       │
              └──────────────┬──────────────┘
                             │  profile.json
              ┌──────────────▼──────────────┐
              │    Agent 2: News Scraper     │
              │  Input : RSS feeds           │
              │  Tool  : feedparser + httpx  │
              │  LLM   : GPT-4o (JSON mode)  │
              │  Output: company_leads.json  │
              │          list[CompanyLead]   │
              └──────────────┬──────────────┘
                             │  profile.json
                             │  company_leads.json
              ┌──────────────▼──────────────┐
              │     Agent 3: Job Filter      │
              │                             │
              │  Searcher:                  │
              │    LinkedIn guest API       │
              │    Selenium (Naukri)        │
              │    -> list[JobListing]      │
              │                             │
              │  Scorer (GPT-4o):           │
              │    Domain match   35%       │
              │    Skill match    25%       │
              │    Industry match 25%       │
              │    Seniority match 15%      │
              │                             │
              │  Output: scored_jobs.json   │
              │          list[ScoredJob]    │
              └──────────────┬──────────────┘
                             │  scored_jobs.json
                             │  profile.json
              ┌──────────────▼──────────────┐
              │    Agent 4: Summarizer       │
              │  Input : top ScoredJobs     │
              │  LLM   : GPT-4o             │
              │  Output: digest.json        │
              │    - top_picks              │
              │    - skill_gaps             │
              │    - market_insight         │
              │    - preparation_tips       │
              └──────────────┬──────────────┘
                             │  (on demand, one job at a time)
              ┌──────────────▼──────────────┐
              │   Agent 5: Resume Tweaker    │
              │  Input : ResumeProfile       │
              │          ScoredJob (picked)  │
              │  Tool  : fetch full JD       │
              │           (LinkedIn URL)     │
              │  LLM   : GPT-4o             │
              │  Rules :                    │
              │    No fabrication           │
              │    Max 3 bullet tweaks      │
              │    Max 5 keyword additions  │
              │  Output: TweakedResume      │
              │    - summary_tweak          │
              │    - bullet_tweaks          │
              │    - keywords_to_add        │
              │    - skills_to_highlight    │
              └─────────────────────────────┘
```

---

## Agent Details

### Agent 1 — Resume Parser

- Reads PDF/DOCX/TXT and sends raw text to GPT-4o with a structured extraction prompt
- Outputs a `ResumeProfile` with: name, email, experience years, seniority level, technical skills, domain skills, tools, industries, work history, preferred locations
- Saved to `profile.json` — used as input by all downstream agents

### Agent 2 — News Scraper

- Queries Google News RSS for targeted searches: Analytics funding India, new GCC Bangalore, AI startup hiring, etc.
- Also reads YourStory and Inc42 RSS feeds
- GPT-4o extracts company names, funding stage, reason this company is hiring, confidence score
- Deduplicates leads and links back to source articles
- Saved to `company_leads.json`

### Agent 3 — Job Filter

**Searcher** (two strategies running in sequence):

| Strategy | Source | Method |
|---|---|---|
| Broad search | LinkedIn | Guest API — no auth required, last 7 days (`f_TPR=r604800`) |
| Broad search | Naukri | Selenium headless Chrome — JS-rendered, last 7 days (`jobAge=7`) |
| Targeted search | LinkedIn | 6 query templates per company from `company_leads.json` |
| Targeted search | Naukri | Role slug search + company name filter |

**Scorer** — GPT-4o evaluates each job on four dimensions:

| Dimension | Weight | What it checks |
|---|---|---|
| Domain match | 35% | Analytics / BI / GenAI / MLOps alignment |
| Skill match | 25% | Technical skill overlap |
| Industry match | 25% | BFSI / Fintech / SaaS / E-commerce experience |
| Seniority match | 15% | Level fit (senior / manager / lead) |

Scores are 0–10 per dimension; overall = weighted average. Recommendation: `strong fit / good fit / partial fit / skip`.

### Agent 4 — Summarizer

- Takes top-scored jobs + resume profile
- GPT-4o generates a daily digest: top picks with reasoning, skill gaps to address, market trends, preparation tips

### Agent 5 — Resume Tweaker (on demand)

- Triggered when user selects a job in the UI
- Lazily fetches the full LinkedIn JD (only at this point — not during broad search)
- GPT-4o applies minimal, targeted changes: mirrors JD language, highlights existing experience using the JD's terminology
- **Strict rules**: no fabrication, no complete rewrites, max 3 bullet tweaks, max 5 keyword additions
- Output: before/after for summary, bullets, and a keyword placement guide

---

## Data Flow (files on disk)

```
Resume file
    -> [Agent 1] -> profile.json
                        -> [Agent 2] -> company_leads.json
                                            -> [Agent 3] -> scored_jobs.json
                                                                -> [Agent 4] -> digest.json
                                                                -> [Agent 5] -> TweakedResume (in-memory)
```

---

## Setup

```bash
pip install -r requirements.txt
```

Create `.env`:
```
OPENAI_API_KEY=sk-proj-...
```

---

## Usage

### Streamlit UI

```bash
streamlit run app.py
```

Four tabs:
- **Resume** — Upload PDF/DOCX, view parsed profile
- **Market Signals** — Run news scraper, view company leads with source links
- **Job Matches** — Fetch and score jobs, filter by fit, view domain/industry/skill sub-scores
- **Resume Tweaker** — Pick a good-fit job, fetch its JD, get targeted resume suggestions

### CLI

```bash
# Step by step
python main.py resume Resume/my_resume.pdf
python main.py news
python main.py filter
python main.py summarize

# End-to-end
python main.py all Resume/my_resume.pdf
```

---

## Key Design Decisions

**No frameworks** — Each agent is a plain Python class. No LangChain, no CrewAI. Easier to debug, easier to extend.

**JSON mode for all LLM calls** — `response_format={"type": "json_object"}` ensures GPT-4o always returns valid, parseable JSON.

**Pydantic v2 for all data models** — Type safety at every boundary. If GPT returns unexpected fields, Pydantic catches it.

**Lazy JD fetching** — Full job descriptions are only fetched when the user selects a job for tweaking. Broad search returns listings in ~2-3 minutes instead of 10+.

**Domain + Industry weighted higher than skills** — At senior levels, domain context and industry experience are stronger signals than raw skill matching. Scoring reflects this: domain 35%, industry 25%, skills 25%, seniority 15%.

**LinkedIn guest API + Selenium Naukri** — LinkedIn's guest API works without authentication. Naukri is a Next.js SSR app with CAPTCHA-protected APIs; Selenium headless Chrome is the only reliable approach.
