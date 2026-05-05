"""Dedup: LinkedIn URL match first, then fuzzy person name + company scope."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.schemas import normalize_domain
from app.db import models as m


def normalize_linkedin_url(url: str | None) -> str | None:
    if not url or not str(url).strip():
        return None
    raw = str(url).strip()
    if not raw.lower().startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if not parsed.netloc:
        return None
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or ""
    # Drop tracking query params; keep meaningful path only
    clean = urlunparse(("https", netloc, path, "", "", ""))
    return clean


def normalize_display_name(name: str | None) -> str | None:
    if not name or not str(name).strip():
        return None
    s = str(name).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s or None


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class CompanyMatch:
    company: m.Company
    created: bool


@dataclass
class PersonMatch:
    person: m.Person
    created: bool


async def find_company_by_domain(
    session: AsyncSession,
    domain: str | None,
) -> m.Company | None:
    d = normalize_domain(domain)
    if not d:
        return None
    r = await session.execute(select(m.Company).where(m.Company.primary_domain == d))
    return r.scalar_one_or_none()


async def find_company_by_normalized_name(
    session: AsyncSession,
    name: str,
) -> m.Company | None:
    nn = normalize_display_name(name)
    if not nn:
        return None
    r = await session.execute(
        select(m.Company).where(m.Company.normalized_name == nn).limit(5)
    )
    rows = r.scalars().all()
    if len(rows) == 1:
        return rows[0]
    if not rows:
        return None
    # Prefer exact name match (case-insensitive)
    for c in rows:
        if normalize_display_name(c.name) == nn:
            return c
    return rows[0]


async def fuzzy_find_company_by_name(
    session: AsyncSession,
    name: str,
    *,
    threshold: float = 0.88,
    limit_scan: int = 200,
) -> m.Company | None:
    """Fallback: scan recent companies' names (bounded) for fuzzy match."""
    nn = normalize_display_name(name)
    if not nn:
        return None
    r = await session.execute(
        select(m.Company).order_by(m.Company.updated_at.desc()).limit(limit_scan)
    )
    best: m.Company | None = None
    best_score = threshold
    for c in r.scalars():
        cn = normalize_display_name(c.name)
        if not cn:
            continue
        score = _name_similarity(nn, cn)
        if score >= best_score:
            best_score = score
            best = c
    return best


async def resolve_or_create_company(
    session: AsyncSession,
    *,
    name: str,
    primary_domain: str | None = None,
    website: str | None = None,
    linkedin_url: str | None = None,
    industry: str | None = None,
    location: str | None = None,
    team_size: str | None = None,
    founded_year: int | None = None,
    raw_data: dict | None = None,
) -> CompanyMatch:
    domain = normalize_domain(primary_domain or website)
    existing: m.Company | None = None
    if domain:
        existing = await find_company_by_domain(session, domain)
    if existing is None:
        existing = await find_company_by_normalized_name(session, name)
    if existing is None:
        existing = await fuzzy_find_company_by_name(session, name)

    if existing:
        if domain and not existing.primary_domain:
            existing.primary_domain = domain
        if website and not existing.website:
            existing.website = website
        if linkedin_url and not existing.linkedin_url:
            existing.linkedin_url = linkedin_url
        if industry:
            existing.industry = industry
        if location:
            existing.location = location
        if team_size:
            existing.team_size = team_size
        if founded_year is not None:
            existing.founded_year = founded_year
        if raw_data:
            merged = dict(existing.raw_data or {})
            merged.update(raw_data)
            existing.raw_data = merged
        if name and len(name) > len(existing.name or ""):
            existing.name = name
        existing.normalized_name = normalize_display_name(existing.name)
        return CompanyMatch(company=existing, created=False)

    company = m.Company(
        id=uuid.uuid4(),
        name=name.strip(),
        normalized_name=normalize_display_name(name),
        primary_domain=domain,
        website=website,
        linkedin_url=linkedin_url,
        industry=industry,
        location=location,
        team_size=team_size,
        founded_year=founded_year,
        raw_data=raw_data,
    )
    session.add(company)
    await session.flush()
    return CompanyMatch(company=company, created=True)


async def find_person_by_linkedin(
    session: AsyncSession,
    linkedin_url: str | None,
) -> m.Person | None:
    norm = normalize_linkedin_url(linkedin_url)
    if not norm:
        return None
    r = await session.execute(select(m.Person).where(m.Person.linkedin_url == norm))
    return r.scalar_one_or_none()


async def find_person_by_name_at_company(
    session: AsyncSession,
    full_name: str,
    company_id: uuid.UUID,
    *,
    threshold: float = 0.9,
) -> m.Person | None:
    nn = normalize_display_name(full_name)
    if not nn:
        return None
    q = (
        select(m.Person)
        .join(m.Employment, m.Employment.person_id == m.Person.id)
        .where(
            m.Employment.company_id == company_id,
        )
        .options(selectinload(m.Person.employments))
    )
    r = await session.execute(q)
    candidates = r.scalars().unique().all()
    best: m.Person | None = None
    best_score = threshold
    for p in candidates:
        pn = normalize_display_name(p.full_name) or ""
        score = _name_similarity(nn, pn)
        if score >= best_score:
            best_score = score
            best = p
    return best


async def resolve_or_create_person(
    session: AsyncSession,
    *,
    full_name: str,
    company_id: uuid.UUID,
    first_name: str | None = None,
    last_name: str | None = None,
    linkedin_url: str | None = None,
    headline: str | None = None,
    location: str | None = None,
    raw_data: dict | None = None,
) -> PersonMatch:
    norm_li = normalize_linkedin_url(linkedin_url)
    existing: m.Person | None = None
    if norm_li:
        existing = await find_person_by_linkedin(session, norm_li)
    if existing is None:
        existing = await find_person_by_name_at_company(session, full_name, company_id)

    if existing:
        if norm_li:
            existing.linkedin_url = norm_li
        if first_name:
            existing.first_name = first_name
        if last_name:
            existing.last_name = last_name
        if headline:
            existing.headline = headline
        if location:
            existing.location = location
        if full_name and len(full_name.strip()) > 0:
            existing.full_name = full_name.strip()
        existing.normalized_full_name = normalize_display_name(existing.full_name)
        if raw_data:
            merged = dict(existing.raw_data or {})
            merged.update(raw_data)
            existing.raw_data = merged
        return PersonMatch(person=existing, created=False)

    person = m.Person(
        id=uuid.uuid4(),
        full_name=full_name.strip(),
        first_name=first_name,
        last_name=last_name,
        normalized_full_name=normalize_display_name(full_name),
        linkedin_url=norm_li,
        headline=headline,
        location=location,
        raw_data=raw_data,
    )
    session.add(person)
    await session.flush()
    return PersonMatch(person=person, created=True)
