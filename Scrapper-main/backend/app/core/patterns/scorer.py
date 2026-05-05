"""Pre-verification ranking: boost patterns known for the company."""

from __future__ import annotations

from app.core.patterns.generator import GeneratedCandidate


def score_candidates(
    candidates: list[GeneratedCandidate],
    *,
    pattern_weights: dict[str, float],
    default_weight: float = 0.35,
) -> list[tuple[GeneratedCandidate, float]]:
    """Assign pre-verify scores using learned pattern confidence (0..1)."""
    scored: list[tuple[GeneratedCandidate, float]] = []
    for c in candidates:
        w = pattern_weights.get(c.pattern_code, default_weight)
        scored.append((c, float(w)))
    scored.sort(key=lambda x: (-x[1], x[0].pattern_code, x[0].email))
    return scored


def pattern_weights_from_db_rows(rows: list[tuple[str, float]]) -> dict[str, float]:
    """Rows: (pattern_code, confidence)."""
    return {code: float(conf) for code, conf in rows}
