from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import (
    CandidateGeneratedOut,
    FindAndVerifyRequest,
    FindAndVerifyResponse,
    FindEmailRequest,
    FindEmailResponse,
)
from app.config import Settings, get_settings
from app.core import contact_intel as ci

router = APIRouter(tags=["contacts"])


def _row(r: ci.CandidateRowOut) -> CandidateGeneratedOut:
    return CandidateGeneratedOut(
        email=r.email,
        pattern_code=r.pattern_code,
        generation_rank=r.generation_rank,
        pattern_confidence=r.pattern_confidence,
        final_score=r.final_score,
        verification_state=r.verification_state,
        candidate_id=r.candidate_id,
    )


@router.post("/find-email", response_model=FindEmailResponse)
async def find_email(
    body: FindEmailRequest,
    session: AsyncSession = Depends(get_db),
) -> FindEmailResponse:
    try:
        out = await ci.find_email_workflow(
            session,
            person_id=body.person_id,
            employment_id=body.employment_id,
            persist_domain=body.persist_domain,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return FindEmailResponse(
        person_id=out.person_id,
        employment_id=out.employment_id,
        company_id=out.company_id,
        domain=out.domain,
        domain_confidence=out.domain_confidence,
        candidates=[_row(c) for c in out.candidates],
    )


@router.post("/find-and-verify", response_model=FindAndVerifyResponse)
async def find_and_verify(
    body: FindAndVerifyRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> FindAndVerifyResponse:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            out = await ci.find_and_verify_workflow(
                session,
                settings,
                person_id=body.person_id,
                employment_id=body.employment_id,
                http_client=client,
                persist_domain=body.persist_domain,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return FindAndVerifyResponse(
        person_id=out.person_id,
        employment_id=out.employment_id,
        company_id=out.company_id,
        domain=out.domain,
        verified=[_row(c) for c in out.verified],
        best=_row(out.best) if out.best else None,
    )
