"""Layered domain resolution: DB → verified candidates → cache → website → heuristic."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.resolvers import identity_resolver as ir
from app.core.schemas import normalize_domain
from app.db import models as m


def _slug_domain_guess(company_name: str) -> str | None:
    """Very low-confidence guess: alnum slug + .com."""
    s = company_name.lower()
    s = re.sub(r"\s+(inc|llc|ltd|corp|corporation|company|co)\.?\s*$", "", s, flags=re.I)
    slug = re.sub(r"[^a-z0-9]+", "", s)
    if len(slug) < 2:
        return None
    return f"{slug}.com"


@dataclass(frozen=True)
class DomainResolution:
    domain: str | None
    confidence: float
    source: str
    needs_review: bool


async def _domain_from_verified_candidates(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> tuple[str, float] | None:
    r = await session.execute(
        select(m.ContactCandidate.domain)
        .where(
            m.ContactCandidate.company_id == company_id,
            m.ContactCandidate.verification_state == "valid",
        )
        .limit(5)
    )
    rows = [row[0] for row in r.all() if row[0]]
    if not rows:
        return None
    domain = rows[0].strip().lower()
    return domain, 0.88


async def _from_cache(
    session: AsyncSession,
    normalized_company_name: str,
) -> tuple[str, float, str] | None:
    r = await session.execute(
        select(m.DomainResolutionCache)
        .where(m.DomainResolutionCache.normalized_company_name == normalized_company_name)
        .order_by(m.DomainResolutionCache.updated_at.desc())
        .limit(1)
    )
    row = r.scalar_one_or_none()
    if not row or not row.resolved_domain:
        return None
    conf = float(row.confidence) if row.confidence is not None else 0.75
    src = row.resolution_source or "cache"
    return row.resolved_domain.strip().lower(), conf, src


async def resolve_for_company(
    session: AsyncSession,
    company: m.Company,
    *,
    persist_cache: bool = True,
) -> DomainResolution:
    """Resolve canonical email domain for a company row."""
    if company.primary_domain:
        d = normalize_domain(company.primary_domain)
        if d:
            conf = float(company.domain_confidence) if company.domain_confidence is not None else 0.92
            needs = conf < 0.70 or bool(company.needs_domain_review)
            return DomainResolution(
                domain=d,
                confidence=conf,
                source="company_record",
                needs_review=needs,
            )

    verified = await _domain_from_verified_candidates(session, company.id)
    if verified:
        d, conf = verified
        needs = conf < 0.70
        return DomainResolution(domain=d, confidence=conf, source="verified_candidate", needs_review=needs)

    nn = ir.normalize_display_name(company.name) or ""
    if nn:
        cached = await _from_cache(session, nn)
        if cached:
            d, conf, src = cached
            return DomainResolution(
                domain=d,
                confidence=conf,
                source=f"domain_cache:{src}",
                needs_review=conf < 0.70,
            )

    web_dom = normalize_domain(company.website)
    if web_dom:
        return DomainResolution(
            domain=web_dom,
            confidence=0.82,
            source="website",
            needs_review=False,
        )

    guess = _slug_domain_guess(company.name or "")
    if guess:
        return DomainResolution(
            domain=guess,
            confidence=0.38,
            source="heuristic",
            needs_review=True,
        )

    return DomainResolution(domain=None, confidence=0.0, source="none", needs_review=True)


async def persist_resolution(
    session: AsyncSession,
    company: m.Company,
    resolution: DomainResolution,
) -> None:
    """Write back domain + cache row when we have a domain."""
    if not resolution.domain:
        return
    d = normalize_domain(resolution.domain)
    if not d:
        return
    company.primary_domain = company.primary_domain or d
    company.domain_confidence = resolution.confidence
    company.domain_source = resolution.source
    company.needs_domain_review = resolution.needs_review

    nn = ir.normalize_display_name(company.name) or ""
    if nn:
        r = await session.execute(
            select(m.DomainResolutionCache).where(
                m.DomainResolutionCache.normalized_company_name == nn,
            )
        )
        row = r.scalar_one_or_none()
        if row:
            row.resolved_domain = d
            row.resolution_source = resolution.source
            row.confidence = resolution.confidence
        else:
            session.add(
                m.DomainResolutionCache(
                    id=uuid.uuid4(),
                    company_name=company.name,
                    normalized_company_name=nn,
                    resolved_domain=d,
                    resolution_source=resolution.source,
                    confidence=resolution.confidence,
                )
            )
    await session.flush()
