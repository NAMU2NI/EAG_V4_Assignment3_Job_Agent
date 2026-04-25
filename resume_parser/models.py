from pydantic import BaseModel, Field
from typing import Optional


class WorkExperience(BaseModel):
    company: str
    role: str
    duration_years: Optional[float] = None
    description: str = ""


class ResumeProfile(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""

    total_experience_years: float = 0.0
    seniority_level: str = ""  # junior / mid / senior / lead / manager

    current_role: str = ""
    target_roles: list[str] = Field(default_factory=list)

    technical_skills: list[str] = Field(default_factory=list)
    domain_skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    industries: list[str] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)

    preferred_locations: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)

    summary: str = ""
