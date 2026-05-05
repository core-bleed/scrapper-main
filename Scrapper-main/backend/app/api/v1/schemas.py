"""Pydantic models for API v1 (Week 2+)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Capture ---


class CaptureCompanyIn(BaseModel):
    name: str = Field(..., min_length=1)
    primary_domain: str | None = None
    website: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    location: str | None = None
    team_size: str | None = None
    founded_year: int | None = None


class CapturePersonIn(BaseModel):
    full_name: str = Field(..., min_length=1)
    first_name: str | None = None
    last_name: str | None = None
    linkedin_url: str | None = None
    headline: str | None = None
    location: str | None = None
    raw_data: dict[str, Any] | None = None


class CaptureEmploymentIn(BaseModel):
    title: str | None = None
    department: str | None = None
    is_current: bool = True


class CaptureSourceIn(BaseModel):
    source_type: str = Field(..., min_length=1)
    source_url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CapturePersonRequest(BaseModel):
    person: CapturePersonIn
    company: CaptureCompanyIn
    employment: CaptureEmploymentIn = Field(default_factory=CaptureEmploymentIn)
    source: CaptureSourceIn


class CapturePersonResponse(BaseModel):
    person_id: uuid.UUID
    company_id: uuid.UUID
    employment_id: uuid.UUID
    source_observation_id: uuid.UUID
    person_created: bool
    company_created: bool


# --- Pagination ---


class PaginationMeta(BaseModel):
    total: int
    limit: int
    offset: int


# --- People ---


class CompanyBrief(BaseModel):
    id: uuid.UUID
    name: str
    primary_domain: str | None

    model_config = {"from_attributes": True}


class EmploymentBrief(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    title: str | None
    seniority: str | None
    is_current: bool
    is_c_suite: bool
    company: CompanyBrief | None = None

    model_config = {"from_attributes": True}


class PersonListItem(BaseModel):
    id: uuid.UUID
    full_name: str
    linkedin_url: str | None
    headline: str | None
    location: str | None
    current_title: str | None = None
    current_company_name: str | None = None
    seniority: str | None = None

    model_config = {"from_attributes": True}


class PersonListResponse(BaseModel):
    items: list[PersonListItem]
    meta: PaginationMeta


class ContactCandidateOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    company_id: uuid.UUID
    email: str
    normalized_email: str
    pattern_code: str | None
    generation_source: str | None
    verification_state: str | None
    final_score: float | None
    is_best_current: bool

    model_config = {"from_attributes": True}


class VerificationEventOut(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    provider: str
    status: str
    confidence: float | None
    verified_at: datetime

    model_config = {"from_attributes": True}


class SourceObservationOut(BaseModel):
    id: uuid.UUID
    source_type: str
    source_url: str | None
    person_id: uuid.UUID | None
    company_id: uuid.UUID | None
    payload: dict[str, Any]
    observed_at: datetime

    model_config = {"from_attributes": True}


class PersonDetail(BaseModel):
    id: uuid.UUID
    full_name: str
    first_name: str | None
    last_name: str | None
    linkedin_url: str | None
    headline: str | None
    location: str | None
    raw_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    employments: list[EmploymentBrief]
    contact_candidates: list[ContactCandidateOut]
    source_observations: list[SourceObservationOut]

    model_config = {"from_attributes": True}


# --- Companies ---


class CompanyListItem(BaseModel):
    id: uuid.UUID
    name: str
    primary_domain: str | None
    industry: str | None
    location: str | None

    model_config = {"from_attributes": True}


class CompanyListResponse(BaseModel):
    items: list[CompanyListItem]
    meta: PaginationMeta


class PersonMinimal(BaseModel):
    id: uuid.UUID
    full_name: str
    linkedin_url: str | None

    model_config = {"from_attributes": True}


class CompanyEmailPatternOut(BaseModel):
    id: uuid.UUID
    domain: str
    pattern_code: str
    confidence: float
    evidence_count: int

    model_config = {"from_attributes": True}


class CompanyDetail(BaseModel):
    id: uuid.UUID
    name: str
    normalized_name: str | None
    primary_domain: str | None
    website: str | None
    linkedin_url: str | None
    industry: str | None
    location: str | None
    team_size: str | None
    founded_year: int | None
    domain_confidence: float | None
    needs_domain_review: bool
    raw_data: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    people: list[PersonMinimal]
    email_patterns: list[CompanyEmailPatternOut]

    model_config = {"from_attributes": True}


# --- Lists ---


class ListCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: str | None = None


class ListOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    entry_count: int
    created_at: datetime
    updated_at: datetime


class ListEntryCreate(BaseModel):
    person_id: uuid.UUID


# --- Week 3: resolve / contacts / verify ---


class ResolvePersonRequest(BaseModel):
    person_id: uuid.UUID
    employment_id: uuid.UUID | None = None
    persist: bool = True


class ResolvePersonResponse(BaseModel):
    person_id: uuid.UUID
    employment_id: uuid.UUID
    company_id: uuid.UUID
    domain: str | None
    confidence: float
    source: str
    needs_review: bool


class CandidateGeneratedOut(BaseModel):
    email: str
    pattern_code: str | None
    generation_rank: int
    pattern_confidence: float | None
    final_score: float | None
    verification_state: str | None
    candidate_id: uuid.UUID | None = None


class FindEmailRequest(BaseModel):
    person_id: uuid.UUID
    employment_id: uuid.UUID | None = None
    persist_domain: bool = True


class FindEmailResponse(BaseModel):
    person_id: uuid.UUID
    employment_id: uuid.UUID
    company_id: uuid.UUID
    domain: str
    domain_confidence: float
    candidates: list[CandidateGeneratedOut]


class FindAndVerifyRequest(BaseModel):
    person_id: uuid.UUID
    employment_id: uuid.UUID | None = None
    persist_domain: bool = True


class FindAndVerifyResponse(BaseModel):
    person_id: uuid.UUID
    employment_id: uuid.UUID
    company_id: uuid.UUID
    domain: str
    verified: list[CandidateGeneratedOut]
    best: CandidateGeneratedOut | None


class VerifyEmailRequest(BaseModel):
    email: str = Field(..., min_length=3)
    person_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None


class VerifyEmailResponse(BaseModel):
    email: str
    status: str
    provider: str
    confidence: float | None
    candidate_id: uuid.UUID | None = None
    verification_event_id: uuid.UUID | None = None


class DomainPatternsResponse(BaseModel):
    domain: str
    patterns: list[CompanyEmailPatternOut]


class CompanyPatternsListResponse(BaseModel):
    company_id: uuid.UUID
    patterns: list[CompanyEmailPatternOut]


# --- Week 4: Jobs + Bulk ---


class JobOut(BaseModel):
    id: uuid.UUID
    job_type: str
    status: str
    progress_current: int
    progress_total: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class JobDetail(JobOut):
    result_summary: dict[str, Any] | None
    artifact_path: str | None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobOut]
    meta: PaginationMeta


class BulkJobResponse(BaseModel):
    job_id: uuid.UUID
    total_rows: int


class RecheckResponse(BaseModel):
    job_id: uuid.UUID


# --- Week 7: Domain Search ---


class DomainSearchRequest(BaseModel):
    domain: str = Field(..., min_length=1)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class DomainSearchPerson(BaseModel):
    id: uuid.UUID
    full_name: str
    linkedin_url: str | None
    current_title: str | None
    seniority: str | None
    best_email: str | None
    best_status: str | None


class DomainSearchResponse(BaseModel):
    domain: str
    company: CompanyBrief | None
    people: list[DomainSearchPerson]
    total: int


# --- Week 8: Export ---


class ExportRequest(BaseModel):
    list_id: uuid.UUID | None = None
    person_ids: list[uuid.UUID] | None = None
    format: str = Field(default="csv", pattern="^(csv|xlsx)$")
