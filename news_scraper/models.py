from pydantic import BaseModel, Field
from typing import Optional


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published: str = ""
    summary: str = ""
    full_text: str = ""


class SourceArticle(BaseModel):
    title: str
    url: str
    source: str
    published: str = ""
    snippet: str = ""


class CompanyLead(BaseModel):
    company_name: str
    signal: str                        # "funding" | "gcc_expansion" | "hiring"
    signal_detail: str                 # e.g. "Series B $20M", "New GCC in Bangalore"
    location: str = "Bangalore"
    domain: str = ""                   # e.g. "Analytics", "Data Engineering"
    source_title: str = ""
    source_url: str = ""
    source_articles: list[SourceArticle] = Field(default_factory=list)
    relevance_score: int = Field(default=0, ge=0, le=10)
