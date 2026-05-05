from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import VerifyEmailRequest, VerifyEmailResponse
from app.config import Settings, get_settings
from app.core.verifiers.factory import get_verifier
from app.core.verifiers.service import verify_email_only

router = APIRouter(tags=["verify"])


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    body: VerifyEmailRequest,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VerifyEmailResponse:
    if "@" not in body.email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if (body.person_id is None) ^ (body.company_id is None):
        raise HTTPException(
            status_code=400,
            detail="person_id and company_id must both be set or both omitted",
        )
    async with httpx.AsyncClient(timeout=60.0) as client:
        verifier = get_verifier(settings, client=client)
        result, cand, ev = await verify_email_only(
            session,
            verifier,
            email=body.email.strip(),
            person_id=body.person_id,
            company_id=body.company_id,
        )
    return VerifyEmailResponse(
        email=result.email,
        status=result.status,
        provider=result.provider,
        confidence=result.confidence,
        candidate_id=cand.id if cand else None,
        verification_event_id=ev.id if ev else None,
    )
