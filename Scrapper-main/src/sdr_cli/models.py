import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


def normalize_domain(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    v = value.strip().lower()
    if "://" in v:
        parsed = urlparse(v if "://" in v else f"https://{v}")
        host = parsed.netloc or parsed.path.split("/")[0]
        v = host
    v = v.rstrip("/")
    if v.startswith("www."):
        v = v[4:]
    return v or None


def infer_seniority(title: str | None) -> str | None:
    if not title:
        return None
    t = title.lower()
    if "founder" in t or "co-founder" in t or "cofounder" in t:
        return "founder"
    if re.search(
        r"\b(ceo|cto|cfo|coo|cmo|cpo|chief|president)\b",
        t,
    ):
        return "c_suite"
    if re.search(r"\bvp\b|vice president", t):
        return "vp"
    if "director" in t:
        return "director"
    if re.search(r"\bhead of\b", t):
        return "head"
    return None


class Company(BaseModel):
    name: str
    domain: str | None = None
    website: str | None = None
    description: str | None = None
    industry: str | None = None
    location: str | None = None
    team_size: int | None = None
    founded_year: int | None = None
    batch: str | None = None
    source: str
    source_url: str | None = None
    tags: str | None = None

    @field_validator("domain", mode="before")
    @classmethod
    def validate_domain(cls, v: str | None) -> str | None:
        return normalize_domain(v)

    @model_validator(mode="after")
    def domain_from_website(self) -> "Company":
        if not self.domain and self.website:
            self.domain = normalize_domain(self.website)
        return self


class Person(BaseModel):
    company_id: int
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    headline: str | None = None
    location: str | None = None
    is_decision_maker: int = 0
    source: str
    source_url: str | None = None

    @field_validator("linkedin_url", "twitter_url", mode="before")
    @classmethod
    def strip_urls(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def seniority_from_title(self) -> "Person":
        if self.seniority is None and self.title:
            self.seniority = infer_seniority(self.title)
        if self.seniority in ("founder", "c_suite", "vp", "director", "head"):
            self.is_decision_maker = 1
        return self


class ContactMethod(BaseModel):
    person_id: int
    method_type: str
    value: str
    status: str = "discovered"
    provider: str
    confidence_score: float | None = None


class ExportRow(BaseModel):
    company_name: str | None = None
    company_domain: str | None = None
    company_batch: str | None = None
    company_source: str | None = None
    person_name: str | None = None
    title: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    twitter_url: str | None = None
    work_email: str | None = None
    email_status: str | None = None
