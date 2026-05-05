from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import (
    CompanyBrief,
    ContactCandidateOut,
    EmploymentBrief,
    PaginationMeta,
    PersonDetail,
    PersonListItem,
    PersonListResponse,
    SourceObservationOut,
)
from app.db import models as m
from app.db import queries as q

router = APIRouter(prefix="/people", tags=["people"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def _pick_current_employment(person: m.Person) -> m.Employment | None:
    if not person.employments:
        return None
    current = [e for e in person.employments if e.is_current]
    pool = current if current else list(person.employments)
    return max(pool, key=lambda e: (e.title_rank, e.updated_at or e.created_at))


def _person_list_item(person: m.Person) -> PersonListItem:
    emp = _pick_current_employment(person)
    company_name = None
    title = None
    seniority = None
    if emp:
        title = emp.title
        seniority = emp.seniority
        if emp.company:
            company_name = emp.company.name
    return PersonListItem(
        id=person.id,
        full_name=person.full_name,
        linkedin_url=person.linkedin_url,
        headline=person.headline,
        location=person.location,
        current_title=title,
        current_company_name=company_name,
        seniority=seniority,
    )


def _employment_brief(emp: m.Employment) -> EmploymentBrief:
    cb = None
    if emp.company:
        cb = CompanyBrief(
            id=emp.company.id,
            name=emp.company.name,
            primary_domain=emp.company.primary_domain,
        )
    return EmploymentBrief(
        id=emp.id,
        company_id=emp.company_id,
        title=emp.title,
        seniority=emp.seniority,
        is_current=emp.is_current,
        is_c_suite=emp.is_c_suite,
        company=cb,
    )


def _candidate_out(c: m.ContactCandidate) -> ContactCandidateOut:
    return ContactCandidateOut(
        id=c.id,
        person_id=c.person_id,
        company_id=c.company_id,
        email=c.email,
        normalized_email=c.normalized_email,
        pattern_code=c.pattern_code,
        generation_source=c.generation_source,
        verification_state=c.verification_state,
        final_score=float(c.final_score) if c.final_score is not None else None,
        is_best_current=c.is_best_current,
    )


def _source_out(o: m.SourceObservation) -> SourceObservationOut:
    return SourceObservationOut(
        id=o.id,
        source_type=o.source_type,
        source_url=o.source_url,
        person_id=o.person_id,
        company_id=o.company_id,
        payload=o.payload,
        observed_at=o.observed_at,
    )


@router.get("", response_model=PersonListResponse)
async def list_people(
    session: AsyncSession = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    name: str | None = None,
    title: str | None = None,
    seniority: str | None = None,
    company: str | None = None,
) -> PersonListResponse:
    total = await q.count_people_filtered(
        session, name=name, title=title, seniority=seniority, company=company
    )
    rows = await q.list_people_filtered(
        session,
        limit=limit,
        offset=offset,
        name=name,
        title=title,
        seniority=seniority,
        company=company,
    )
    return PersonListResponse(
        items=[_person_list_item(p) for p in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    person_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> PersonDetail:
    person = await q.get_person_with_relations(session, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    sources = await q.list_source_observations_for_person(session, person_id)
    emps = sorted(
        person.employments,
        key=lambda e: (not e.is_current, -(e.title_rank or 0)),
    )

    return PersonDetail(
        id=person.id,
        full_name=person.full_name,
        first_name=person.first_name,
        last_name=person.last_name,
        linkedin_url=person.linkedin_url,
        headline=person.headline,
        location=person.location,
        raw_data=person.raw_data,
        created_at=person.created_at,
        updated_at=person.updated_at,
        employments=[_employment_brief(e) for e in emps],
        contact_candidates=[_candidate_out(c) for c in person.contact_candidates],
        source_observations=[_source_out(s) for s in sources],
    )
