"""Unit tests for pattern generator (no DB). Run: cd backend && pytest tests/"""

from app.core.patterns.generator import generate_candidates


def test_generate_candidates_jane_smith():
    c = generate_candidates("Jane Smith", "example.com")
    emails = {x.email for x in c}
    assert "jane.smith@example.com" in emails
    assert "jsmith@example.com" in emails
    assert "jane@example.com" in emails


def test_empty_domain():
    assert generate_candidates("Jane Smith", "") == []


def test_ranker_status_weight():
    from app.core.ranking.contact_ranker import candidate_rank_score, status_weight

    assert status_weight("valid") == 1.0
    assert status_weight("catch_all") == 0.65
    s = candidate_rank_score(
        verification_state="valid",
        verifier_confidence=1.0,
        pattern_confidence=1.0,
        domain_confidence=1.0,
        is_c_suite=False,
    )
    assert s > 0.9
