from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import (
    CompanyDetail,
    CompanyEmailPatternOut,
    CompanyListItem,
    CompanyListResponse,
    CompanyPatternsListResponse,
    PaginationMeta,
    PersonMinimal,
)
from app.db import queries as q

router = APIRouter(prefix="/companies", tags=["companies"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def _pattern_out(p) -> CompanyEmailPatternOut:
    return CompanyEmailPatternOut(
        id=p.id,
        domain=p.domain,
        pattern_code=p.pattern_code,
        confidence=float(p.confidence),
        evidence_count=p.evidence_count,
    )


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    session: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    name: str | None = None,
    domain: str | None = None,
    industry: str | None = None,
) -> CompanyListResponse:
    total = await q.count_companies_filtered(session, name=name, domain=domain, industry=industry)
    rows = await q.list_companies_filtered(
        session,
        limit=limit,
        offset=offset,
        name=name,
        domain=domain,
        industry=industry,
    )
    items = [
        CompanyListItem(
            id=c.id,
            name=c.name,
            primary_domain=c.primary_domain,
            industry=c.industry,
            location=c.location,
        )
        for c in rows
    ]
    return CompanyListResponse(
        items=items,
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{company_id}/patterns", response_model=CompanyPatternsListResponse)
async def company_patterns_only(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CompanyPatternsListResponse:
    company = await q.get_company_with_relations(session, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    patterns = sorted(company.email_patterns, key=lambda x: (-float(x.confidence), x.pattern_code))
    return CompanyPatternsListResponse(
        company_id=company.id,
        patterns=[_pattern_out(p) for p in patterns],
    )


@router.get("/{company_id}", response_model=CompanyDetail)
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> CompanyDetail:
    company = await q.get_company_with_relations(session, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    people = await q.list_people_ids_for_company(session, company_id)
    patterns = sorted(company.email_patterns, key=lambda x: (-float(x.confidence), x.pattern_code))

    return CompanyDetail(
        id=company.id,
        name=company.name,
        normalized_name=company.normalized_name,
        primary_domain=company.primary_domain,
        website=company.website,
        linkedin_url=company.linkedin_url,
        industry=company.industry,
        location=company.location,
        team_size=company.team_size,
        founded_year=company.founded_year,
        domain_confidence=float(company.domain_confidence)
        if company.domain_confidence is not None
        else None,
        needs_domain_review=company.needs_domain_review,
        raw_data=company.raw_data,
        created_at=company.created_at,
        updated_at=company.updated_at,
        people=[
            PersonMinimal(id=p.id, full_name=p.full_name, linkedin_url=p.linkedin_url) for p in people
        ],
        email_patterns=[_pattern_out(p) for p in patterns],
    )
