from pydantic import BaseModel, Field
from typing import Optional


class JobListing(BaseModel):
    title: str
    company: str
    location: str = ""
    url: str = ""
    description: str = ""
    experience_required: str = ""
    skills_mentioned: list[str] = Field(default_factory=list)
    posted_date: str = ""
    source: str = ""                  # "linkedin" | "naukri"


class ScoredJob(BaseModel):
    job: JobListing
    match_score: int = Field(ge=0, le=10)       # overall weighted score
    skill_score: int = Field(default=0, ge=0, le=10)
    domain_score: int = Field(default=0, ge=0, le=10)
    industry_score: int = Field(default=0, ge=0, le=10)
    seniority_score: int = Field(default=0, ge=0, le=10)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    matched_domains: list[str] = Field(default_factory=list)
    matched_industries: list[str] = Field(default_factory=list)
    seniority_match: bool = True
    location_match: bool = True
    recommendation: str = ""          # "strong fit" | "good fit" | "partial fit" | "skip"
    gpt_reasoning: str = ""
