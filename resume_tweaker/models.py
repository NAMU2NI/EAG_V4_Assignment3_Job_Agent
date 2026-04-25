from pydantic import BaseModel, Field


class SummaryTweak(BaseModel):
    original: str
    tweaked: str
    reason: str


class BulletTweak(BaseModel):
    section: str           # e.g. "Work Experience — Infosys"
    original: str
    tweaked: str
    reason: str


class KeywordAddition(BaseModel):
    keyword: str
    where_to_add: str      # e.g. "Skills section", "Summary"
    reason: str


class TweakedResume(BaseModel):
    job_title: str
    company: str
    domain_alignment: str          # 1-line note on domain fit
    industry_alignment: str        # 1-line note on industry fit

    summary_tweak: SummaryTweak
    bullet_tweaks: list[BulletTweak] = Field(default_factory=list)
    keywords_to_add: list[KeywordAddition] = Field(default_factory=list)
    skills_to_highlight: list[str] = Field(default_factory=list)
    skills_to_move_up: list[str] = Field(default_factory=list)

    do_not_change: list[str] = Field(default_factory=list)   # things that already match well
    overall_advice: str = ""
