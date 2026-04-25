import json
import openai
from .models import JobListing, ScoredJob
from resume_parser.models import ResumeProfile

# Scoring weights — domain + industry matter most to this user
WEIGHTS = {
    "skill":     0.25,
    "domain":    0.35,
    "industry":  0.25,
    "seniority": 0.15,
}

SCORE_PROMPT = """You are a senior recruiter evaluating job fit for a candidate in India.

Score each job across FOUR dimensions, then compute a weighted overall score.

Candidate Profile:
{profile}

Scoring weights (must reflect these priorities):
  - domain_score    35% — does the job domain match candidate's analytics/AI domain expertise?
  - skill_score     25% — do technical skills align?
  - industry_score  25% — does the company's industry match candidate's industry background?
  - seniority_score 15% — is the seniority level right?

Overall = (domain * 0.35) + (skill * 0.25) + (industry * 0.25) + (seniority * 0.15), rounded to nearest int.

Domain examples: Data Analytics, Business Intelligence, Generative AI, MLOps, LLMOps, NLP, Predictive Modeling
Industry examples: BFSI, Fintech, E-commerce, Procurement, Aerospace, Healthcare, SaaS, Retail

For each job return exactly:
{{
  "title": "as given",
  "company": "as given",
  "skill_score": 0-10,
  "domain_score": 0-10,
  "industry_score": 0-10,
  "seniority_score": 0-10,
  "match_score": 0-10,
  "matched_skills": ["skills that match"],
  "missing_skills": ["required skills candidate lacks"],
  "matched_domains": ["domains from candidate profile that match this JD"],
  "matched_industries": ["industries that match"],
  "seniority_match": true/false,
  "location_match": true/false,
  "recommendation": "strong fit|good fit|partial fit|skip",
  "gpt_reasoning": "2 sentences: lead with domain/industry fit, then skill gaps"
}}

Scoring guide (apply to each dimension):
- 9-10: Exact match
- 7-8 : Strong overlap
- 5-6 : Partial / transferable
- 3-4 : Weak overlap
- 0-2 : Mismatch

Return {{"scored_jobs": [...]}} — ONLY valid JSON, no markdown."""


def score_jobs(jobs: list[JobListing], profile: ResumeProfile, client: openai.OpenAI) -> list[ScoredJob]:
    if not jobs:
        return []

    profile_summary = {
        "name": profile.name,
        "total_experience_years": profile.total_experience_years,
        "seniority_level": profile.seniority_level,
        "current_role": profile.current_role,
        "target_roles": profile.target_roles,
        "technical_skills": profile.technical_skills,
        "domain_skills": profile.domain_skills,
        "tools": profile.tools,
        "industries": profile.industries,
        "preferred_locations": profile.preferred_locations,
    }

    jobs_payload = [
        {
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "description": j.description[:600],   # full JD if available
            "skills_mentioned": j.skills_mentioned,
            "experience_required": j.experience_required,
        }
        for j in jobs
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": SCORE_PROMPT.format(profile=json.dumps(profile_summary, indent=2)),
            },
            {
                "role": "user",
                "content": f"Score these jobs:\n{json.dumps(jobs_payload, indent=2)}",
            },
        ],
    )

    raw = json.loads(response.choices[0].message.content)

    if isinstance(raw, dict):
        items_list = raw.get("scored_jobs", [])
        if not items_list and "match_score" in raw:
            items_list = [raw]
        if not items_list:
            for v in raw.values():
                if isinstance(v, list):
                    items_list = v
                    break
    elif isinstance(raw, list):
        items_list = raw
    else:
        items_list = []

    scored = []
    for i, item in enumerate(items_list):
        if not isinstance(item, dict):
            continue
        job = jobs[i] if i < len(jobs) else jobs[0]
        try:
            scored.append(ScoredJob(
                job=job,
                match_score=item.get("match_score", 0),
                skill_score=item.get("skill_score", 0),
                domain_score=item.get("domain_score", 0),
                industry_score=item.get("industry_score", 0),
                seniority_score=item.get("seniority_score", 0),
                matched_skills=item.get("matched_skills", []),
                missing_skills=item.get("missing_skills", []),
                matched_domains=item.get("matched_domains", []),
                matched_industries=item.get("matched_industries", []),
                seniority_match=item.get("seniority_match", True),
                location_match=item.get("location_match", True),
                recommendation=item.get("recommendation", "skip"),
                gpt_reasoning=item.get("gpt_reasoning", ""),
            ))
        except Exception:
            pass

    return sorted(scored, key=lambda x: x.match_score, reverse=True)
