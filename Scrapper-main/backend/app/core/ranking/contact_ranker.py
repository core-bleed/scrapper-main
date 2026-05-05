"""Post-verification candidate scoring and best pick."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.db import models as m

STATUS_WEIGHT: dict[str, float] = {
    "valid": 1.0,
    "catch_all": 0.65,
    "unknown": 0.35,
    "pending": 0.2,
    "invalid": 0.0,
}


def status_weight(state: str | None) -> float:
    if not state:
        return STATUS_WEIGHT["pending"]
    return STATUS_WEIGHT.get(state, STATUS_WEIGHT["unknown"])


def candidate_rank_score(
    *,
    verification_state: str | None,
    verifier_confidence: float | None,
    pattern_confidence: float | None,
    domain_confidence: float | None,
    is_c_suite: bool,
) -> float:
    """Composite score in ~[0, 1] for ranking; catch-all still ranks above unknown."""
    sw = status_weight(verification_state)
    vc = verifier_confidence if verifier_confidence is not None else 0.5
    pc = pattern_confidence if pattern_confidence is not None else 0.35
    dc = domain_confidence if domain_confidence is not None else 0.5
    # Weight verifier + pattern + domain; status is multiplicative driver
    mix = 0.45 * vc + 0.35 * pc + 0.20 * dc
    base = sw * (0.55 + 0.45 * mix)
    if is_c_suite:
        base = min(1.0, base + 0.04)
    return round(base, 4)


@dataclass
class RankedPick:
    candidate_id: uuid.UUID
    score: float
    verification_state: str | None


def pick_best(
    candidates: list[m.ContactCandidate],
    *,
    domain_confidence: float | None,
    is_c_suite: bool,
    last_verifier_confidence: dict[uuid.UUID, float | None] | None = None,
) -> RankedPick | None:
    """Pick best candidate using stored fields + optional per-id verifier confidence."""
    if not candidates:
        return None
    last_vc = last_verifier_confidence or {}
    best: RankedPick | None = None
    for c in candidates:
        vc = last_vc.get(c.id)
        score = candidate_rank_score(
            verification_state=c.verification_state,
            verifier_confidence=vc,
            pattern_confidence=float(c.pattern_confidence)
            if c.pattern_confidence is not None
            else None,
            domain_confidence=domain_confidence,
            is_c_suite=is_c_suite,
        )
        if best is None or score > best.score:
            best = RankedPick(candidate_id=c.id, score=score, verification_state=c.verification_state)
    return best
