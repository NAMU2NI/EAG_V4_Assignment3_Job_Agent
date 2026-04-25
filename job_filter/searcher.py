import time
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from .models import JobListing

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

# LinkedIn: last 7 days (f_TPR=r604800)
LINKEDIN_SEARCH = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    "?keywords={keywords}&location=Bangalore%2C+India&start=0&f_TPR=r604800"
)
LINKEDIN_JOB_PAGE = "https://www.linkedin.com/jobs/view/{job_id}"

# Naukri: last 7 days (jobAge=7)
NAUKRI_SEARCH_URLS = [
    "https://www.naukri.com/{slug}-jobs-in-bengaluru?experience={exp}&jobAge=7",
    "https://www.naukri.com/{slug}-jobs-in-bangalore-bengaluru?experience={exp}&jobAge=7",
]

ROLE_QUERIES_LINKEDIN = [
    "{company} data analyst",
    "{company} analytics engineer",
    "{company} analytics manager",
    "{company} data scientist generative AI",
    "{company} business intelligence",
    "{company} AI ML engineer",
]

NAUKRI_ROLE_SLUGS = [
    "data-analyst",
    "analytics-manager",
    "senior-data-analyst",
    "data-scientist",
    "analytics-engineer",
    "ai-ml",
]


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def _encode(text: str) -> str:
    return text.replace(" ", "%20").replace("&", "%26").replace('"', "")


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    return BeautifulSoup(raw, "lxml").get_text(separator=" ", strip=True)


def _fetch_linkedin_description(job_url: str) -> str:
    """Fetch full JD text from a LinkedIn job page."""
    try:
        with httpx.Client(headers=HEADERS, timeout=12, follow_redirects=True) as c:
            r = c.get(job_url)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            desc = soup.select_one("div.show-more-less-html__markup")
            if desc:
                return desc.get_text(separator=" ", strip=True)[:2500]
    except Exception:
        pass
    return ""


def _enrich_linkedin_descriptions(jobs: list[JobListing], max_workers: int = 5) -> list[JobListing]:
    """Fetch full JDs for all LinkedIn jobs in parallel."""
    def _fetch(job: JobListing) -> tuple[JobListing, str]:
        return job, _fetch_linkedin_description(job.url)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch, job): job for job in jobs if job.url}
        for future in as_completed(futures):
            try:
                job, desc = future.result()
                if desc:
                    job.description = desc
            except Exception:
                pass

    return jobs


def fetch_linkedin_jobs(keywords: str, fallback_company: str, fetch_jd: bool = False) -> list[JobListing]:
    url = LINKEDIN_SEARCH.format(keywords=_encode(keywords))
    try:
        with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    jobs = []

    for card in soup.select("div.base-search-card"):
        title_tag   = card.select_one("h3.base-search-card__title")
        company_tag = card.select_one("h4.base-search-card__subtitle")
        location_tag = card.select_one("span.job-search-card__location")
        link_tag    = card.select_one("a.base-card__full-link")
        date_tag    = card.select_one("time")

        title   = title_tag.get_text(strip=True) if title_tag else ""
        company = company_tag.get_text(strip=True) if company_tag else fallback_company
        location = location_tag.get_text(strip=True) if location_tag else "Bangalore"
        url     = link_tag.get("href", "") if link_tag else ""
        posted  = date_tag.get("datetime", "") if date_tag else ""

        if not title:
            continue

        jobs.append(JobListing(
            title=title,
            company=company or fallback_company,
            location=location,
            url=url,
            posted_date=posted,
            source="linkedin",
        ))

    jobs = jobs[:8]

    if fetch_jd and jobs:
        jobs = _enrich_linkedin_descriptions(jobs)

    return jobs


# ── Naukri (Selenium) ─────────────────────────────────────────────────────────

def _get_selenium_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(f"--user-agent={HEADERS['User-Agent']}")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts,
    )


def _parse_naukri_cards(html: str, company_filter: str) -> list[JobListing]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.srp-jobtuple-wrapper")
    jobs = []

    for card in cards:
        title_tag   = card.select_one("h2 a.title")
        company_tag = card.select_one("a.comp-name")
        location_tag = card.select_one("span.locWdth, li.location span")
        exp_tag     = card.select_one("span.expwdth, li.experience span")
        skills_tags = card.select("ul.tags-gt li, ul.tags li")
        date_tag    = card.select_one("span.job-post-day, span[class*='date']")

        title    = title_tag.get_text(strip=True) if title_tag else ""
        url      = title_tag.get("href", "") if title_tag else ""
        company  = company_tag.get_text(strip=True) if company_tag else ""
        location = location_tag.get_text(strip=True) if location_tag else "Bangalore"
        exp      = exp_tag.get_text(strip=True) if exp_tag else ""
        skills   = [s.get_text(strip=True) for s in skills_tags]
        posted   = date_tag.get_text(strip=True) if date_tag else ""

        if not title:
            continue

        # Filter by company if specified (for targeted search)
        if company_filter and company_filter.lower() not in company.lower():
            # Still include if search was company-agnostic (role-based Naukri search)
            pass

        jobs.append(JobListing(
            title=title,
            company=company,
            location=location,
            url=url,
            experience_required=exp,
            skills_mentioned=skills[:8],
            posted_date=posted,
            source="naukri",
        ))

    return jobs


def fetch_naukri_jobs(slug: str, experience: int = 8, driver=None) -> list[JobListing]:
    """Fetch Naukri jobs for a role slug using headless Chrome."""
    url = NAUKRI_SEARCH_URLS[0].format(slug=slug, exp=experience)
    own_driver = driver is None

    try:
        if own_driver:
            driver = _get_selenium_driver()
        driver.get(url)
        time.sleep(3)
        return _parse_naukri_cards(driver.page_source, company_filter="")
    except Exception:
        return []
    finally:
        if own_driver and driver:
            driver.quit()


def fetch_naukri_for_company(company: str, driver=None) -> list[JobListing]:
    """Search Naukri jobs filtered to a specific company."""
    # Naukri doesn't have direct company+role search; we use general role search
    # then filter results by company name in post-processing
    all_jobs = []
    own_driver = driver is None

    try:
        if own_driver:
            driver = _get_selenium_driver()

        for slug in NAUKRI_ROLE_SLUGS[:3]:  # limit to 3 slugs per company to be fast
            url = NAUKRI_SEARCH_URLS[0].format(slug=slug, exp=8)
            try:
                driver.get(url)
                time.sleep(2.5)
                jobs = _parse_naukri_cards(driver.page_source, company_filter=company)
                # Keep only jobs from this company
                company_jobs = [j for j in jobs if company.lower() in j.company.lower()]
                all_jobs.extend(company_jobs)
            except Exception:
                continue

    finally:
        if own_driver and driver:
            driver.quit()

    return all_jobs


# ── Orchestrator ──────────────────────────────────────────────────────────────

def search_jobs_for_company(company: str, delay: float = 1.0) -> list[JobListing]:
    all_jobs: list[JobListing] = []
    seen_urls: set[str] = set()

    # ── LinkedIn ──────────────────────────────────────────────────────────
    for template in ROLE_QUERIES_LINKEDIN:
        keywords = template.format(company=company)
        jobs = fetch_linkedin_jobs(keywords, fallback_company=company)
        for job in jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)
        time.sleep(delay)

    # ── Naukri (single driver session across all slugs) ───────────────────
    naukri_driver = None
    try:
        naukri_driver = _get_selenium_driver()

        for slug in NAUKRI_ROLE_SLUGS:
            url = NAUKRI_SEARCH_URLS[0].format(slug=slug, exp=8)
            try:
                naukri_driver.get(url)
                time.sleep(2.5)
                jobs = _parse_naukri_cards(naukri_driver.page_source, company_filter=company)
                # Keep only jobs from this company (or all if company not found, as Naukri
                # search is role-based not company-based)
                company_jobs = [j for j in jobs if company.lower() in j.company.lower()]
                for job in company_jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
            except Exception:
                continue

    finally:
        if naukri_driver:
            naukri_driver.quit()

    return all_jobs


def fetch_jd_for_job(job: JobListing) -> str:
    """Lazily fetch full JD for a single job when needed (e.g. for resume tweaker)."""
    if job.source == "linkedin" and job.url:
        return _fetch_linkedin_description(job.url)
    return job.description or ""


def fetch_all_latest_jobs(experience: int = 8) -> list[JobListing]:
    """
    Broad fetch — not tied to specific companies.
    Pulls latest analytics/AI jobs from LinkedIn + Naukri directly.
    """
    all_jobs: list[JobListing] = []
    seen_urls: set[str] = set()

    # LinkedIn — broad role searches in Bangalore (no JD fetch during search — lazy load later)
    broad_queries = [
        "analytics manager bangalore",
        "data scientist generative AI bangalore",
        "analytics engineer bangalore",
        "senior data analyst bangalore",
    ]
    for query in broad_queries:
        jobs = fetch_linkedin_jobs(query, fallback_company="", fetch_jd=False)
        for job in jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                all_jobs.append(job)
        time.sleep(0.8)

    # Naukri — role-based search (single driver session, top 4 slugs only)
    naukri_driver = None
    try:
        naukri_driver = _get_selenium_driver()
        for slug in NAUKRI_ROLE_SLUGS[:4]:
            url = NAUKRI_SEARCH_URLS[0].format(slug=slug, exp=experience)
            try:
                naukri_driver.get(url)
                time.sleep(2.5)
                jobs = _parse_naukri_cards(naukri_driver.page_source, company_filter="")
                for job in jobs:
                    if job.url not in seen_urls:
                        seen_urls.add(job.url)
                        all_jobs.append(job)
            except Exception:
                continue
    finally:
        if naukri_driver:
            naukri_driver.quit()

    return all_jobs
