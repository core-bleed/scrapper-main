from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import CompanyEmailPatternOut, DomainPatternsResponse
from app.core.schemas import normalize_domain
from app.db import queries as q

router = APIRouter(prefix="/domains", tags=["domains"])


def _pattern_out(p) -> CompanyEmailPatternOut:
    return CompanyEmailPatternOut(
        id=p.id,
        domain=p.domain,
        pattern_code=p.pattern_code,
        confidence=float(p.confidence),
        evidence_count=p.evidence_count,
    )


@router.get("/{domain}/patterns", response_model=DomainPatternsResponse)
async def domain_patterns(
    domain: str,
    session: AsyncSession = Depends(get_db),
) -> DomainPatternsResponse:
    d = normalize_domain(domain)
    if not d:
        raise HTTPException(status_code=400, detail="Invalid domain")
    rows = await q.list_email_patterns_for_domain(session, d)
    return DomainPatternsResponse(
        domain=d,
        patterns=[_pattern_out(p) for p in rows],
    )
