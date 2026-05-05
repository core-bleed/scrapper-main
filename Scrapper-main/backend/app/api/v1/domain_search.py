"""Domain search + pattern rebuild API (Week 7)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.api.v1.schemas import (
    CompanyBrief,
    CompanyEmailPatternOut,
    DomainPatternsResponse,
    DomainSearchRequest,
    DomainSearchResponse,
    DomainSearchPerson,
)
from app.core.schemas import normalize_domain
from app.db import models as m
from app.db.queries import (
    count_verifications_by_pattern_for_domain,
    list_email_patterns_for_domain,
)

router = APIRouter(tags=["domain_search"])


@router.post("/domain-search", response_model=DomainSearchResponse)
async def domain_search(
    body: DomainSearchRequest,
    session: AsyncSession = Depends(get_db),
) -> DomainSearchResponse:
    domain = normalize_domain(body.domain)
    if not domain:
        raise HTTPException(status_code=400, detail="Invalid domain")

    company_r = await session.execute(
        select(m.Company).where(m.Company.primary_domain == domain)
    )
    company = company_r.scalar_one_or_none()
    company_out = (
        CompanyBrief(id=company.id, name=company.name, primary_domain=company.primary_domain)
        if company
        else None
    )

    if not company:
        return DomainSearchResponse(domain=domain, company=None, people=[], total=0)

    count_r = await session.execute(
        select(func.count(m.Person.id.distinct()))
        .join(m.Employment, m.Employment.person_id == m.Person.id)
        .where(m.Employment.company_id == company.id)
    )
    total = int(count_r.scalar_one() or 0)

    stmt = (
        select(m.Person)
        .join(m.Employment, m.Employment.person_id == m.Person.id)
        .where(m.Employment.company_id == company.id)
        .options(selectinload(m.Person.employments))
        .order_by(m.Person.full_name)
        .distinct()
        .limit(body.limit)
        .offset(body.offset)
    )
    rows = list((await session.execute(stmt)).scalars().unique().all())

    people: list[DomainSearchPerson] = []
    for p in rows:
        emp = next(
            (e for e in p.employments if e.company_id == company.id and e.is_current),
            next((e for e in p.employments if e.company_id == company.id), None),
        )
        best_email = None
        best_status = None
        if emp and emp.best_candidate_id:
            cand = await session.get(m.ContactCandidate, emp.best_candidate_id)
            if cand:
                best_email = cand.email
                best_status = cand.verification_state

        people.append(DomainSearchPerson(
            id=p.id,
            full_name=p.full_name,
            linkedin_url=p.linkedin_url,
            current_title=emp.title if emp else None,
            seniority=emp.seniority if emp else None,
            best_email=best_email,
            best_status=best_status,
        ))

    return DomainSearchResponse(
        domain=domain,
        company=company_out,
        people=people,
        total=total,
    )


@router.post("/domains/{domain}/rebuild-patterns", response_model=DomainPatternsResponse)
async def rebuild_patterns(
    domain: str,
    session: AsyncSession = Depends(get_db),
) -> DomainPatternsResponse:
    d = normalize_domain(domain)
    if not d:
        raise HTTPException(status_code=400, detail="Invalid domain")

    company_r = await session.execute(
        select(m.Company).where(m.Company.primary_domain == d)
    )
    company = company_r.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail=f"No company found for domain {d!r}")

    pattern_counts = await count_verifications_by_pattern_for_domain(session, d)
    now = datetime.now(timezone.utc)

    for pattern_code, (valid_count, catch_all_count) in pattern_counts.items():
        total = valid_count + catch_all_count
        confidence = (valid_count + catch_all_count * 0.5) / max(total, 1)

        existing_r = await session.execute(
            select(m.CompanyEmailPattern).where(
                m.CompanyEmailPattern.company_id == company.id,
                m.CompanyEmailPattern.pattern_code == pattern_code,
            )
        )
        existing = existing_r.scalar_one_or_none()
        if existing:
            existing.confidence = Decimal(str(round(confidence, 4)))
            existing.evidence_count = total
            existing.last_observed_at = now
        else:
            session.add(m.CompanyEmailPattern(
                id=uuid.uuid4(),
                company_id=company.id,
                domain=d,
                pattern_code=pattern_code,
                confidence=Decimal(str(round(confidence, 4))),
                evidence_count=total,
                last_observed_at=now,
            ))

    await session.flush()
    patterns = await list_email_patterns_for_domain(session, d)
    return DomainPatternsResponse(
        domain=d,
        patterns=[
            CompanyEmailPatternOut(
                id=p.id,
                domain=p.domain,
                pattern_code=p.pattern_code,
                confidence=float(p.confidence),
                evidence_count=p.evidence_count,
            )
            for p in patterns
        ],
    )
