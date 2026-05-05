"""Recheck stale verification candidates for a person (Week 4)."""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.tasks import celery_app

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path("/tmp/sdr_jobs")

FRESHNESS_DAYS: dict[str, int] = {
    "valid": 30,
    "catch_all": 14,
    "unknown": 7,
    "invalid": 30,
    "pending": 1,
}


def _is_stale(candidate) -> bool:
    state = candidate.verification_state or "pending"
    threshold = timedelta(days=FRESHNESS_DAYS.get(state, 7))
    if candidate.latest_verified_at is None:
        return True
    verified_at = candidate.latest_verified_at
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - verified_at) > threshold


async def _run_recheck_person(job_id: str, person_id_str: str) -> None:
    import httpx
    from sqlalchemy import select

    from app.config import get_settings
    from app.core.ranking import contact_ranker as ranker
    from app.core.verifiers.factory import get_verifier
    from app.core.verifiers.service import apply_verification_to_candidate
    from app.db import models as m
    from app.db import queries as q
    from app.db import repository as repo
    from app.db.engine import async_session_factory

    settings = get_settings()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    person_id = uuid.UUID(person_id_str)

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if not job:
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.attempt_count = (job.attempt_count or 0) + 1

    async with async_session_factory() as session:
        r = await session.execute(
            select(m.ContactCandidate)
            .where(m.ContactCandidate.person_id == person_id)
            .order_by(m.ContactCandidate.generation_rank)
        )
        all_candidates = list(r.scalars().all())

    stale = [c for c in all_candidates if _is_stale(c)]

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if job:
                job.progress_total = len(stale)

    results: list[dict] = []
    errors = 0

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        verifier = get_verifier(settings, client=http_client)
        for idx, cand in enumerate(stale):
            old_status = cand.verification_state or "unknown"
            try:
                async with async_session_factory() as session:
                    async with session.begin():
                        live = await session.get(m.ContactCandidate, cand.id)
                        if not live:
                            continue
                        result = await verifier.verify(live.email)
                        await apply_verification_to_candidate(session, candidate=live, result=result)
                results.append({
                    "email": cand.email,
                    "old_status": old_status,
                    "new_status": result.status,
                    "new_confidence": f"{result.confidence:.4f}" if result.confidence else "",
                    "error": "",
                })
            except Exception as exc:
                logger.warning("Recheck %s failed: %s", cand.email, exc)
                results.append({
                    "email": cand.email,
                    "old_status": old_status,
                    "new_status": "",
                    "new_confidence": "",
                    "error": str(exc),
                })
                errors += 1

            async with async_session_factory() as session:
                async with session.begin():
                    job = await session.get(m.Job, uuid.UUID(job_id))
                    if job:
                        job.progress_current = idx + 1

    # Re-rank per (person, company) pair
    async with async_session_factory() as session:
        async with session.begin():
            r = await session.execute(
                select(m.ContactCandidate)
                .where(m.ContactCandidate.person_id == person_id)
            )
            refreshed = list(r.scalars().all())

            by_company: dict[uuid.UUID, list[m.ContactCandidate]] = {}
            for c in refreshed:
                by_company.setdefault(c.company_id, []).append(c)

            for company_id, cands in by_company.items():
                emp_r = await session.execute(
                    select(m.Employment).where(
                        m.Employment.person_id == person_id,
                        m.Employment.company_id == company_id,
                    )
                )
                emp = emp_r.scalar_one_or_none()
                company = await session.get(m.Company, company_id)
                dom_conf = float(company.domain_confidence) if company and company.domain_confidence else 0.5
                vc_map = await q.latest_verifier_confidence_by_candidate(session, [c.id for c in cands])

                for c in cands:
                    fs = ranker.candidate_rank_score(
                        verification_state=c.verification_state,
                        verifier_confidence=vc_map.get(c.id),
                        pattern_confidence=float(c.pattern_confidence) if c.pattern_confidence else None,
                        domain_confidence=dom_conf,
                        is_c_suite=emp.is_c_suite if emp else False,
                    )
                    c.final_score = Decimal(str(fs))

                pick = ranker.pick_best(
                    cands,
                    domain_confidence=dom_conf,
                    is_c_suite=emp.is_c_suite if emp else False,
                    last_verifier_confidence=vc_map,
                )
                if pick and emp:
                    await repo.update_employment_best_candidate(
                        session, emp,
                        best_candidate_id=pick.candidate_id,
                        best_status=pick.verification_state,
                        best_score=pick.score,
                    )

    artifact_path = ARTIFACT_DIR / f"{job_id}_recheck.csv"
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["email", "old_status", "new_status", "new_confidence", "error"],
    )
    writer.writeheader()
    writer.writerows(results)
    artifact_path.write_text(buf.getvalue(), encoding="utf-8")

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if job:
                job.status = "succeeded"
                job.completed_at = datetime.now(timezone.utc)
                job.artifact_path = str(artifact_path)
                job.result_summary = {
                    "stale_found": len(stale),
                    "rechecked": len(results),
                    "errors": errors,
                }


async def _fail_job(job_id: str, error: str) -> None:
    from app.db import models as m
    from app.db.engine import async_session_factory

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = error[:1000]


@celery_app.task(bind=True, name="sdr.tasks.recheck_person")
def recheck_person_task(self, job_id: str, person_id: str) -> None:
    """Sync Celery task — bridges to async via asyncio.run()."""
    try:
        asyncio.run(_run_recheck_person(job_id, person_id))
    except Exception as exc:
        logger.error("Recheck job %s failed: %s", job_id, exc)
        asyncio.run(_fail_job(job_id, str(exc)))
        raise
