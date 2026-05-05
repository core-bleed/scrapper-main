from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import ResolvePersonRequest, ResolvePersonResponse
from app.core.contact_intel import resolve_person_workflow

router = APIRouter(prefix="/resolve", tags=["resolve"])


@router.post("/person", response_model=ResolvePersonResponse)
async def resolve_person(
    body: ResolvePersonRequest,
    session: AsyncSession = Depends(get_db),
) -> ResolvePersonResponse:
    try:
        out = await resolve_person_workflow(
            session,
            person_id=body.person_id,
            employment_id=body.employment_id,
            persist=body.persist,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ResolvePersonResponse(
        person_id=out.person_id,
        employment_id=out.employment_id,
        company_id=out.company_id,
        domain=out.domain,
        confidence=out.confidence,
        source=out.source,
        needs_review=out.needs_review,
    )
