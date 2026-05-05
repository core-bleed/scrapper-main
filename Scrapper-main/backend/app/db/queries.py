"""List/search/detail queries."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import models as m


def _title_rank(seniority: str | None) -> int:
    if seniority == "c_suite" or seniority == "founder":
        return 100
    if seniority == "vp":
        return 80
    if seniority == "director":
        return 60
    if seniority == "head":
        return 50
    return 0


def _people_ids_select(
    *,
    name: str | None = None,
    title: str | None = None,
    seniority: str | None = None,
    company: str | None = None,
):
    stmt = select(m.Person.id).distinct()
    if title or seniority or company:
        stmt = stmt.join(m.Employment, m.Employment.person_id == m.Person.id)
        if title:
            stmt = stmt.where(m.Employment.title.ilike(f"%{title}%"))
        if seniority:
            stmt = stmt.where(m.Employment.seniority == seniority)
        if company:
            stmt = stmt.join(m.Company, m.Company.id == m.Employment.company_id).where(
                m.Company.name.ilike(f"%{company}%")
            )
    if name:
        stmt = stmt.where(m.Person.full_name.ilike(f"%{name}%"))
    return stmt


async def count_people_filtered(
    session: AsyncSession,
    *,
    name: str | None = None,
    title: str | None = None,
    seniority: str | None = None,
    company: str | None = None,
) -> int:
    inner = _people_ids_select(
        name=name, title=title, seniority=seniority, company=company
    ).subquery()
    r = await session.execute(select(func.count()).select_from(inner))
    return int(r.scalar_one() or 0)


async def list_people_filtered(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    name: str | None = None,
    title: str | None = None,
    seniority: str | None = None,
    company: str | None = None,
) -> list[m.Person]:
    base = select(m.Person).distinct()

    if title or seniority or company:
        base = base.join(m.Employment, m.Employment.person_id == m.Person.id)
        if title:
            base = base.where(m.Employment.title.ilike(f"%{title}%"))
        if seniority:
            base = base.where(m.Employment.seniority == seniority)
        if company:
            base = base.join(m.Company, m.Company.id == m.Employment.company_id).where(
                m.Company.name.ilike(f"%{company}%")
            )

    if name:
        base = base.where(m.Person.full_name.ilike(f"%{name}%"))

    base = (
        base.options(
            selectinload(m.Person.employments).selectinload(m.Employment.company),
        )
        .order_by(m.Person.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    r = await session.execute(base)
    return list(r.scalars().unique().all())


async def get_person_with_relations(session: AsyncSession, person_id: uuid.UUID) -> m.Person | None:
    stmt = (
        select(m.Person)
        .where(m.Person.id == person_id)
        .options(
            selectinload(m.Person.employments).selectinload(m.Employment.company),
            selectinload(m.Person.contact_candidates),
        )
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def list_source_observations_for_person(
    session: AsyncSession,
    person_id: uuid.UUID,
) -> list[m.SourceObservation]:
    r = await session.execute(
        select(m.SourceObservation)
        .where(m.SourceObservation.person_id == person_id)
        .order_by(m.SourceObservation.observed_at.desc())
    )
    return list(r.scalars().all())


async def count_companies_filtered(
    session: AsyncSession,
    *,
    name: str | None = None,
    domain: str | None = None,
    industry: str | None = None,
) -> int:
    stmt = select(func.count()).select_from(m.Company)
    conds = []
    if name:
        conds.append(m.Company.name.ilike(f"%{name}%"))
    if domain:
        conds.append(m.Company.primary_domain.ilike(f"%{domain}%"))
    if industry:
        conds.append(m.Company.industry.ilike(f"%{industry}%"))
    if conds:
        stmt = stmt.where(and_(*conds))
    r = await session.execute(stmt)
    return int(r.scalar_one() or 0)


async def list_companies_filtered(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    name: str | None = None,
    domain: str | None = None,
    industry: str | None = None,
) -> list[m.Company]:
    stmt = select(m.Company).order_by(m.Company.updated_at.desc())
    conds = []
    if name:
        conds.append(m.Company.name.ilike(f"%{name}%"))
    if domain:
        conds.append(m.Company.primary_domain.ilike(f"%{domain}%"))
    if industry:
        conds.append(m.Company.industry.ilike(f"%{industry}%"))
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.limit(limit).offset(offset)
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def get_company_with_relations(session: AsyncSession, company_id: uuid.UUID) -> m.Company | None:
    stmt = (
        select(m.Company)
        .where(m.Company.id == company_id)
        .options(selectinload(m.Company.email_patterns))
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def list_people_ids_for_company(session: AsyncSession, company_id: uuid.UUID) -> list[m.Person]:
    """Distinct people linked via employment."""
    stmt = (
        select(m.Person)
        .join(m.Employment, m.Employment.person_id == m.Person.id)
        .where(m.Employment.company_id == company_id)
        .distinct()
        .order_by(m.Person.full_name)
    )
    r = await session.execute(stmt)
    return list(r.scalars().all())


async def list_lead_lists_with_counts(session: AsyncSession) -> list[tuple[m.LeadList, int]]:
    cnt = func.count(m.ListEntry.id).label("entry_count")
    stmt = (
        select(m.LeadList, cnt)
        .outerjoin(m.ListEntry, m.ListEntry.list_id == m.LeadList.id)
        .group_by(m.LeadList.id)
        .order_by(m.LeadList.updated_at.desc())
    )
    r = await session.execute(stmt)
    return [(row[0], int(row[1])) for row in r.all()]


async def get_lead_list(session: AsyncSession, list_id: uuid.UUID) -> m.LeadList | None:
    return await session.get(m.LeadList, list_id)


async def get_list_entry(
    session: AsyncSession,
    list_id: uuid.UUID,
    person_id: uuid.UUID,
) -> m.ListEntry | None:
    r = await session.execute(
        select(m.ListEntry).where(
            m.ListEntry.list_id == list_id,
            m.ListEntry.person_id == person_id,
        )
    )
    return r.scalar_one_or_none()


# Export _title_rank for capture
def employment_title_rank(seniority: str | None) -> int:
    return _title_rank(seniority)


async def get_employment_with_company(
    session: AsyncSession,
    employment_id: uuid.UUID,
) -> m.Employment | None:
    stmt = (
        select(m.Employment)
        .where(m.Employment.id == employment_id)
        .options(
            selectinload(m.Employment.company),
            selectinload(m.Employment.person),
        )
    )
    r = await session.execute(stmt)
    return r.scalar_one_or_none()


async def pick_current_employment_for_person(
    session: AsyncSession,
    person_id: uuid.UUID,
) -> m.Employment | None:
    stmt = (
        select(m.Employment)
        .where(m.Employment.person_id == person_id)
        .options(selectinload(m.Employment.company), selectinload(m.Employment.person))
    )
    r = await session.execute(stmt)
    rows = list(r.scalars().all())
    if not rows:
        return None
    current = [e for e in rows if e.is_current]
    pool = current if current else rows
    return max(pool, key=lambda e: (e.title_rank, e.updated_at or e.created_at))


async def list_contact_candidates_for_pair(
    session: AsyncSession,
    *,
    person_id: uuid.UUID,
    company_id: uuid.UUID,
) -> list[m.ContactCandidate]:
    r = await session.execute(
        select(m.ContactCandidate)
        .where(
            m.ContactCandidate.person_id == person_id,
            m.ContactCandidate.company_id == company_id,
        )
        .order_by(m.ContactCandidate.generation_rank, m.ContactCandidate.email)
    )
    return list(r.scalars().all())


async def latest_verifier_confidence_by_candidate(
    session: AsyncSession,
    candidate_ids: list[uuid.UUID],
) -> dict[uuid.UUID, float | None]:
    if not candidate_ids:
        return {}
    r = await session.execute(
        select(m.VerificationEvent)
        .where(m.VerificationEvent.candidate_id.in_(candidate_ids))
        .order_by(desc(m.VerificationEvent.verified_at))
    )
    events = list(r.scalars().all())
    out: dict[uuid.UUID, float | None] = {}
    for ev in events:
        if ev.candidate_id in out:
            continue
        out[ev.candidate_id] = float(ev.confidence) if ev.confidence is not None else None
    return out


async def count_verifications_by_pattern_for_domain(
    session: AsyncSession,
    domain: str,
) -> dict[str, tuple[int, int]]:
    """Return {pattern_code: (valid_count, catch_all_count)} from verification history at domain."""
    from sqlalchemy import case

    d = domain.strip().lower()
    stmt = (
        select(
            m.ContactCandidate.pattern_code,
            func.count(
                case((m.VerificationEvent.status == "valid", 1), else_=None)
            ).label("valid_count"),
            func.count(
                case((m.VerificationEvent.status == "catch_all", 1), else_=None)
            ).label("catch_all_count"),
        )
        .join(m.VerificationEvent, m.VerificationEvent.candidate_id == m.ContactCandidate.id)
        .where(
            m.ContactCandidate.domain == d,
            m.ContactCandidate.pattern_code.isnot(None),
            m.VerificationEvent.status.in_(["valid", "catch_all"]),
        )
        .group_by(m.ContactCandidate.pattern_code)
    )
    r = await session.execute(stmt)
    return {
        row[0]: (int(row[1]), int(row[2]))
        for row in r.all()
        if row[0]
    }


async def list_people_in_list(
    session: AsyncSession,
    list_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[m.Person], int]:
    count_r = await session.execute(
        select(func.count()).select_from(m.ListEntry).where(m.ListEntry.list_id == list_id)
    )
    total = int(count_r.scalar_one() or 0)
    stmt = (
        select(m.Person)
        .join(m.ListEntry, m.ListEntry.person_id == m.Person.id)
        .where(m.ListEntry.list_id == list_id)
        .options(
            selectinload(m.Person.employments).selectinload(m.Employment.company),
        )
        .order_by(m.Person.full_name)
        .limit(limit)
        .offset(offset)
    )
    r = await session.execute(stmt)
    return list(r.scalars().unique().all()), total


async def list_email_patterns_for_domain(
    session: AsyncSession,
    domain: str,
) -> list[m.CompanyEmailPattern]:
    d = domain.strip().lower()
    r = await session.execute(
        select(m.CompanyEmailPattern)
        .where(m.CompanyEmailPattern.domain == d)
        .order_by(desc(m.CompanyEmailPattern.confidence), m.CompanyEmailPattern.pattern_code)
    )
    return list(r.scalars().all())
