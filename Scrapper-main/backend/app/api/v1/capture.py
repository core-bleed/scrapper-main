from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import CapturePersonRequest, CapturePersonResponse
from app.core.resolvers import identity_resolver as ir
from app.core.schemas import infer_seniority, is_c_suite_title
from app.db import repository as repo
from app.db.queries import employment_title_rank

router = APIRouter(prefix="/capture", tags=["capture"])


@router.post("/person", response_model=CapturePersonResponse)
async def capture_person(
    body: CapturePersonRequest,
    session: AsyncSession = Depends(get_db),
) -> CapturePersonResponse:
    c = body.company
    p = body.person
    e = body.employment
    src = body.source

    cm = await ir.resolve_or_create_company(
        session,
        name=c.name,
        primary_domain=c.primary_domain,
        website=c.website,
        linkedin_url=c.linkedin_url,
        industry=c.industry,
        location=c.location,
        team_size=c.team_size,
        founded_year=c.founded_year,
        raw_data=None,
    )

    pm = await ir.resolve_or_create_person(
        session,
        full_name=p.full_name,
        company_id=cm.company.id,
        first_name=p.first_name,
        last_name=p.last_name,
        linkedin_url=p.linkedin_url,
        headline=p.headline,
        location=p.location,
        raw_data=p.raw_data,
    )

    seniority = infer_seniority(e.title)
    title_rank = employment_title_rank(seniority)
    is_cs = is_c_suite_title(e.title)

    emp, _ = await repo.upsert_employment(
        session,
        person_id=pm.person.id,
        company_id=cm.company.id,
        title=e.title,
        department=e.department,
        is_current=e.is_current,
        seniority=seniority,
        is_c_suite=is_cs,
        title_rank=title_rank,
    )

    payload = dict(src.payload)
    payload.setdefault("capture", {"person": p.model_dump(), "company": c.model_dump(), "employment": e.model_dump()})

    obs = await repo.add_source_observation(
        session,
        source_type=src.source_type,
        source_url=src.source_url,
        person_id=pm.person.id,
        company_id=cm.company.id,
        payload=payload,
    )

    return CapturePersonResponse(
        person_id=pm.person.id,
        company_id=cm.company.id,
        employment_id=emp.id,
        source_observation_id=obs.id,
        person_created=pm.created,
        company_created=cm.created,
    )
