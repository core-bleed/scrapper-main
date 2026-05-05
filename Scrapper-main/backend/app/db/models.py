from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index(
            "uq_companies_primary_domain",
            "primary_domain",
            unique=True,
            postgresql_where=text("primary_domain IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    domain_confidence: Mapped[Any | None] = mapped_column(Numeric(5, 4), nullable=True)
    domain_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_domain_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    employments: Mapped[list[Employment]] = relationship(back_populates="company")
    contact_candidates: Mapped[list[ContactCandidate]] = relationship(back_populates="company")
    email_patterns: Mapped[list[CompanyEmailPattern]] = relationship(back_populates="company")


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        Index(
            "uq_people_linkedin_url",
            "linkedin_url",
            unique=True,
            postgresql_where=text("linkedin_url IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    employments: Mapped[list[Employment]] = relationship(back_populates="person")
    contact_candidates: Mapped[list[ContactCandidate]] = relationship(back_populates="person")


class ContactCandidate(Base):
    __tablename__ = "contact_candidates"
    __table_args__ = (
        Index(
            "uq_contact_candidates_person_email",
            "person_id",
            "normalized_email",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_email: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    local_part: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pattern_confidence: Mapped[Any | None] = mapped_column(Numeric(5, 4), nullable=True)
    final_score: Mapped[Any | None] = mapped_column(Numeric(6, 4), nullable=True)
    verification_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deliverability_risk: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_best_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    person: Mapped[Person] = relationship(back_populates="contact_candidates")
    company: Mapped[Company] = relationship(back_populates="contact_candidates")
    verification_events: Mapped[list[VerificationEvent]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class Employment(Base):
    __tablename__ = "employments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seniority: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_c_suite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact_candidates.id", ondelete="SET NULL"), nullable=True
    )
    best_candidate_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    best_candidate_score: Mapped[Any | None] = mapped_column(Numeric(6, 4), nullable=True)
    ranked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    person: Mapped[Person] = relationship(back_populates="employments")
    company: Mapped[Company] = relationship(back_populates="employments")
    best_candidate: Mapped[ContactCandidate | None] = relationship(
        foreign_keys=[best_candidate_id],
    )


class VerificationEvent(Base):
    __tablename__ = "verification_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact_candidates.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Any | None] = mapped_column(Numeric(5, 4), nullable=True)
    verifier_score: Mapped[Any | None] = mapped_column(Numeric(5, 4), nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    candidate: Mapped[ContactCandidate] = relationship(back_populates="verification_events")


class CompanyEmailPattern(Base):
    __tablename__ = "company_email_patterns"
    __table_args__ = (
        Index(
            "uq_company_email_patterns_company_pattern",
            "company_id",
            "pattern_code",
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_code: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Any] = mapped_column(Numeric(5, 4), nullable=False, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    company: Mapped[Company] = relationship(back_populates="email_patterns")


class SourceObservation(Base):
    __tablename__ = "source_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DomainResolutionCache(Base):
    __tablename__ = "domain_resolution_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_company_name: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Any | None] = mapped_column(Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class LeadList(Base):
    __tablename__ = "lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    entries: Mapped[list[ListEntry]] = relationship(
        back_populates="lead_list",
        cascade="all, delete-orphan",
    )


class ListEntry(Base):
    __tablename__ = "list_entries"
    __table_args__ = (Index("uq_list_entries_list_person", "list_id", "person_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lists.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="CASCADE"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    lead_list: Mapped[LeadList] = relationship(back_populates="entries")
    person: Mapped[Person] = relationship()


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
