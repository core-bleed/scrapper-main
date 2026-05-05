"""Async CRUD helpers (PostgreSQL)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m


async def count_companies(session: AsyncSession) -> int:
    from sqlalchemy import func

    r = await session.execute(select(func.count()).select_from(m.Company))
    return int(r.scalar_one())


async def count_people(session: AsyncSession) -> int:
    from sqlalchemy import func

    r = await session.execute(select(func.count()).select_from(m.Person))
    return int(r.scalar_one())


async def get_company_by_id(session: AsyncSession, company_id: UUID) -> m.Company | None:
    return await session.get(m.Company, company_id)


async def get_person_by_id(session: AsyncSession, person_id: UUID) -> m.Person | None:
    return await session.get(m.Person, person_id)


async def upsert_employment(
    session: AsyncSession,
    *,
    person_id: uuid.UUID,
    company_id: uuid.UUID,
    title: str | None,
    department: str | None,
    is_current: bool,
    seniority: str | None,
    is_c_suite: bool,
    title_rank: int,
) -> tuple[m.Employment, bool]:
    r = await session.execute(
        select(m.Employment).where(
            m.Employment.person_id == person_id,
            m.Employment.company_id == company_id,
        )
    )
    emp = r.scalar_one_or_none()
    if emp:
        emp.title = title
        emp.department = department
        emp.is_current = is_current
        emp.seniority = seniority
        emp.is_c_suite = is_c_suite
        emp.title_rank = title_rank
        await session.flush()
        return emp, False

    emp = m.Employment(
        id=uuid.uuid4(),
        person_id=person_id,
        company_id=company_id,
        title=title,
        department=department,
        is_current=is_current,
        seniority=seniority,
        is_c_suite=is_c_suite,
        title_rank=title_rank,
    )
    session.add(emp)
    await session.flush()
    return emp, True


async def add_source_observation(
    session: AsyncSession,
    *,
    source_type: str,
    source_url: str | None,
    person_id: uuid.UUID | None,
    company_id: uuid.UUID | None,
    payload: dict,
    observed_at=None,
) -> m.SourceObservation:
    from datetime import datetime, timezone

    obs = m.SourceObservation(
        id=uuid.uuid4(),
        source_type=source_type,
        source_url=source_url,
        person_id=person_id,
        company_id=company_id,
        payload=payload,
        observed_at=observed_at or datetime.now(timezone.utc),
    )
    session.add(obs)
    await session.flush()
    return obs


async def upsert_contact_candidate(
    session: AsyncSession,
    *,
    person_id: uuid.UUID,
    company_id: uuid.UUID,
    email: str,
    normalized_email: str,
    domain: str,
    local_part: str,
    pattern_code: str | None,
    generation_source: str | None,
    generation_rank: int,
    pattern_confidence: float | None,
) -> m.ContactCandidate:
    r = await session.execute(
        select(m.ContactCandidate).where(
            m.ContactCandidate.person_id == person_id,
            m.ContactCandidate.normalized_email == normalized_email,
        )
    )
    row = r.scalar_one_or_none()
    pc = Decimal(str(pattern_confidence)) if pattern_confidence is not None else None
    if row:
        if pattern_code:
            row.pattern_code = pattern_code
        if generation_source:
            row.generation_source = generation_source
        row.generation_rank = generation_rank
        if pattern_confidence is not None:
            row.pattern_confidence = pc
        await session.flush()
        return row

    cand = m.ContactCandidate(
        id=uuid.uuid4(),
        person_id=person_id,
        company_id=company_id,
        email=email,
        normalized_email=normalized_email,
        domain=domain,
        local_part=local_part,
        pattern_code=pattern_code,
        generation_source=generation_source,
        generation_rank=generation_rank,
        pattern_confidence=pc,
        verification_state="pending",
    )
    session.add(cand)
    await session.flush()
    return cand


async def add_verification_event(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    provider: str,
    status: str,
    confidence: float | None,
    verifier_score: float | None,
    raw_response: dict | None,
    latency_ms: int | None,
    verified_at: datetime,
) -> m.VerificationEvent:
    ev = m.VerificationEvent(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        provider=provider,
        status=status,
        confidence=Decimal(str(confidence)) if confidence is not None else None,
        verifier_score=Decimal(str(verifier_score)) if verifier_score is not None else None,
        raw_response=raw_response,
        latency_ms=latency_ms,
        verified_at=verified_at,
    )
    session.add(ev)
    await session.flush()
    return ev


async def clear_best_flags_for_person_company(
    session: AsyncSession,
    *,
    person_id: uuid.UUID,
    company_id: uuid.UUID,
) -> None:
    await session.execute(
        update(m.ContactCandidate)
        .where(
            m.ContactCandidate.person_id == person_id,
            m.ContactCandidate.company_id == company_id,
        )
        .values(is_best_current=False)
    )
    await session.flush()


async def update_employment_best_candidate(
    session: AsyncSession,
    employment: m.Employment,
    *,
    best_candidate_id: uuid.UUID | None,
    best_status: str | None,
    best_score: float | None,
) -> None:
    employment.best_candidate_id = best_candidate_id
    employment.best_candidate_status = best_status
    employment.best_candidate_score = (
        Decimal(str(best_score)) if best_score is not None else None
    )
    employment.ranked_at = datetime.now(timezone.utc)
    await session.flush()
