import json
import openai
from .extractor import extract_text
from .models import ResumeProfile, WorkExperience

PARSE_PROMPT = """You are a resume parsing expert. Extract structured information from the resume text below.

Return a JSON object with exactly these fields:
{
  "name": "full name",
  "email": "email address",
  "phone": "phone number",
  "location": "current city/location",
  "total_experience_years": <number>,
  "seniority_level": "junior|mid|senior|lead|manager",
  "current_role": "most recent job title",
  "target_roles": ["list of roles this person is suited for"],
  "technical_skills": ["Python", "SQL", "Spark", ...],
  "domain_skills": ["Data Analytics", "Business Intelligence", ...],
  "tools": ["Tableau", "Power BI", "dbt", ...],
  "certifications": ["AWS Certified", ...],
  "industries": ["BFSI", "E-commerce", ...],
  "work_experience": [
    {"company": "...", "role": "...", "duration_years": 2.5, "description": "..."}
  ],
  "preferred_locations": ["Bangalore", "Hyderabad", ...],
  "education": ["B.Tech Computer Science - IIT Delhi 2018"],
  "summary": "2-3 sentence professional summary"
}

Rules:
- Infer target_roles from experience and skills (e.g. Data Analyst, Analytics Engineer, BI Developer)
- Infer preferred_locations from current location if not stated; include Bangalore by default for India-based profiles
- Be exhaustive with technical_skills — include programming languages, frameworks, cloud platforms
- Return ONLY valid JSON, no markdown, no explanation"""


class ResumeParser:
    def __init__(self, api_key: str | None = None):
        self.client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def parse(self, file_path: str) -> ResumeProfile:
        raw_text = extract_text(file_path)
        return self._parse_with_openai(raw_text)

    def parse_text(self, resume_text: str) -> ResumeProfile:
        return self._parse_with_openai(resume_text)

    def _parse_with_openai(self, resume_text: str) -> ResumeProfile:
        response = self.client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": PARSE_PROMPT},
                {"role": "user", "content": f"Resume Text:\n{resume_text}"},
            ],
        )

        data = json.loads(response.choices[0].message.content)

        work_exp = [
            WorkExperience(**exp) if isinstance(exp, dict) else exp
            for exp in data.get("work_experience", [])
        ]
        data["work_experience"] = work_exp

        return ResumeProfile(**data)
