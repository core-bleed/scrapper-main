"""Update company_email_patterns from verification wins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models as m


async def record_valid_pattern(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    domain: str,
    pattern_code: str | None,
    delta_confidence: float = 0.12,
    max_confidence: float = 0.99,
) -> None:
    """Boost confidence for a pattern after a *valid* verification."""
    if not pattern_code:
        return
    d = domain.strip().lower()
    r = await session.execute(
        select(m.CompanyEmailPattern).where(
            m.CompanyEmailPattern.company_id == company_id,
            m.CompanyEmailPattern.pattern_code == pattern_code,
        )
    )
    row = r.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row:
        ev = int(row.evidence_count or 0) + 1
        base = float(row.confidence or 0)
        new_c = min(max_confidence, max(base, 0.1) + delta_confidence)
        row.evidence_count = ev
        row.confidence = new_c
        row.last_observed_at = now
        row.domain = d
    else:
        session.add(
            m.CompanyEmailPattern(
                id=uuid.uuid4(),
                company_id=company_id,
                domain=d,
                pattern_code=pattern_code,
                confidence=min(max_confidence, 0.5 + delta_confidence),
                evidence_count=1,
                last_observed_at=now,
            )
        )
    await session.flush()
