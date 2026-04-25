import json
import openai
from resume_parser.models import ResumeProfile
from .models import TweakedResume, SummaryTweak, BulletTweak, KeywordAddition

TWEAK_PROMPT = """You are an expert resume coach. Your job is to make MINIMAL, TARGETED tweaks to a resume for a specific job.

Rules:
- Do NOT fabricate experience, skills, or achievements the candidate doesn't have
- Do NOT rewrite everything — only change what genuinely improves relevance
- PRIORITISE domain alignment and industry alignment over generic skill matching
- Tweak language to mirror the JD's terminology where candidate already has that experience
- Suggest moving existing skills higher in the list if they match the JD
- Max 3 bullet tweaks, max 5 keyword additions

Candidate Profile:
{profile}

Target Job:
Title: {job_title}
Company: {company}
Job Description:
{jd}

Return JSON with this exact structure:
{{
  "job_title": "{job_title}",
  "company": "{company}",
  "domain_alignment": "one sentence on how candidate domain matches this JD",
  "industry_alignment": "one sentence on how candidate industry experience applies here",
  "summary_tweak": {{
    "original": "candidate's current summary",
    "tweaked": "slightly reworded summary to mirror JD language — max 2 sentences changed",
    "reason": "what was changed and why"
  }},
  "bullet_tweaks": [
    {{
      "section": "Work Experience — CompanyName",
      "original": "exact original bullet from candidate profile",
      "tweaked": "reworded bullet using JD terminology — same fact, better framing",
      "reason": "why this phrasing is better for this role"
    }}
  ],
  "keywords_to_add": [
    {{
      "keyword": "specific term from JD",
      "where_to_add": "Skills section / Summary / Experience bullet",
      "reason": "candidate has this experience but didn't use this exact term"
    }}
  ],
  "skills_to_highlight": ["existing skills to move to top of skills list"],
  "skills_to_move_up": ["skills already on resume that match JD — emphasise these"],
  "do_not_change": ["things already perfectly aligned — keep as is"],
  "overall_advice": "2 sentences: what makes this a good/bad fit and main thing to emphasise"
}}

Return ONLY valid JSON, no markdown."""


class ResumeTweaker:
    def __init__(self, api_key: str | None = None):
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def tweak(self, profile: ResumeProfile, job_title: str, company: str, jd_text: str) -> TweakedResume:
        profile_summary = {
            "name": profile.name,
            "summary": profile.summary,
            "total_experience_years": profile.total_experience_years,
            "seniority_level": profile.seniority_level,
            "current_role": profile.current_role,
            "target_roles": profile.target_roles,
            "technical_skills": profile.technical_skills,
            "domain_skills": profile.domain_skills,
            "tools": profile.tools,
            "industries": profile.industries,
            "work_experience": [
                {
                    "company": e.company,
                    "role": e.role,
                    "duration_years": e.duration_years,
                    "description": e.description[:400],
                }
                for e in profile.work_experience
            ],
        }

        response = self.client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": TWEAK_PROMPT.format(
                        profile=json.dumps(profile_summary, indent=2),
                        job_title=job_title,
                        company=company,
                        jd=jd_text[:3000],
                    ),
                },
                {"role": "user", "content": "Generate the resume tweaks for this job."},
            ],
        )

        data = json.loads(response.choices[0].message.content)

        summary_raw = data.get("summary_tweak", {})
        bullet_raws = data.get("bullet_tweaks", [])
        keyword_raws = data.get("keywords_to_add", [])

        return TweakedResume(
            job_title=data.get("job_title", job_title),
            company=data.get("company", company),
            domain_alignment=data.get("domain_alignment", ""),
            industry_alignment=data.get("industry_alignment", ""),
            summary_tweak=SummaryTweak(**summary_raw) if summary_raw else SummaryTweak(
                original=profile.summary, tweaked=profile.summary, reason="No changes needed"
            ),
            bullet_tweaks=[BulletTweak(**b) for b in bullet_raws if isinstance(b, dict)],
            keywords_to_add=[KeywordAddition(**k) for k in keyword_raws if isinstance(k, dict)],
            skills_to_highlight=data.get("skills_to_highlight", []),
            skills_to_move_up=data.get("skills_to_move_up", []),
            do_not_change=data.get("do_not_change", []),
            overall_advice=data.get("overall_advice", ""),
        )
