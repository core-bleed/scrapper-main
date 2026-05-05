"""Verify flow: call provider, persist verification_events, update candidate row."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.verifiers.base import VerifierProtocol, VerificationResult
from app.db import models as m
from app.db import repository as repo


async def apply_verification_to_candidate(
    session: AsyncSession,
    *,
    candidate: m.ContactCandidate,
    result: VerificationResult,
) -> m.VerificationEvent:
    """Store event and refresh candidate verification fields."""
    now = datetime.now(timezone.utc)
    ev = await repo.add_verification_event(
        session,
        candidate_id=candidate.id,
        provider=result.provider,
        status=result.status,
        confidence=result.confidence,
        verifier_score=result.confidence,
        raw_response=result.raw_response,
        latency_ms=result.latency_ms,
        verified_at=now,
    )
    candidate.verification_state = result.status
    candidate.latest_verified_at = now
    candidate.deliverability_risk = _risk_from_status(result.status)
    await session.flush()
    return ev


def _risk_from_status(status: str) -> str:
    if status == "valid":
        return "low"
    if status in ("catch_all", "unknown"):
        return "medium"
    return "high"


async def verify_email_only(
    session: AsyncSession,
    verifier: VerifierProtocol,
    *,
    email: str,
    person_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
) -> tuple[VerificationResult, m.ContactCandidate | None, m.VerificationEvent | None]:
    """
    Verify an email; if person_id+company_id given, upsert a candidate and record event.
    Otherwise return result only (no DB rows).
    """
    result = await verifier.verify(email)
    if person_id is None or company_id is None:
        return result, None, None
    norm = email.strip().lower()
    if "@" not in norm:
        return result, None, None
    local, _, domain = norm.partition("@")
    cand = await repo.upsert_contact_candidate(
        session,
        person_id=person_id,
        company_id=company_id,
        email=email.strip(),
        normalized_email=norm,
        domain=domain,
        local_part=local,
        pattern_code=None,
        generation_source="manual",
        generation_rank=0,
        pattern_confidence=None,
    )
    ev = await apply_verification_to_candidate(session, candidate=cand, result=result)
    return result, cand, ev
