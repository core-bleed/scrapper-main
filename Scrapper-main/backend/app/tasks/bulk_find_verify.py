"""Bulk find-and-verify Celery task (Week 4)."""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.tasks import celery_app

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path("/tmp/sdr_jobs")
ARTIFACT_COLUMNS = [
    "full_name", "company_name", "company_domain", "title",
    "best_email", "email_status", "email_score", "pattern_code", "error",
]


async def _process_row(row: dict, settings, http_client: httpx.AsyncClient) -> dict:
    from app.db.engine import async_session_factory
    from app.core.resolvers.identity_resolver import (
        resolve_or_create_company,
        resolve_or_create_person,
    )
    from app.core.schemas import infer_seniority, is_c_suite_title
    from app.db import repository as repo
    from app.db.queries import employment_title_rank
    from app.core import contact_intel as ci

    full_name = (row.get("full_name") or "").strip()
    company_name = (row.get("company_name") or "").strip()
    company_domain = (row.get("company_domain") or "").strip() or None
    title = (row.get("title") or "").strip() or None
    first_name = (row.get("first_name") or "").strip() or None
    last_name = (row.get("last_name") or "").strip() or None
    linkedin_url = (row.get("linkedin_url") or "").strip() or None

    if not full_name or not company_name:
        raise ValueError("full_name and company_name are required")

    async with async_session_factory() as session:
        async with session.begin():
            cm = await resolve_or_create_company(
                session,
                name=company_name,
                primary_domain=company_domain,
            )
            pm = await resolve_or_create_person(
                session,
                full_name=full_name,
                company_id=cm.company.id,
                first_name=first_name,
                last_name=last_name,
                linkedin_url=linkedin_url,
            )
            seniority = infer_seniority(title)
            is_cs = is_c_suite_title(title)
            emp, _ = await repo.upsert_employment(
                session,
                person_id=pm.person.id,
                company_id=cm.company.id,
                title=title,
                department=None,
                is_current=True,
                seniority=seniority,
                is_c_suite=is_cs,
                title_rank=employment_title_rank(seniority),
            )
            person_id = pm.person.id
            employment_id = emp.id

    async with async_session_factory() as session:
        async with session.begin():
            outcome = await ci.find_and_verify_workflow(
                session,
                settings,
                person_id=person_id,
                employment_id=employment_id,
                http_client=http_client,
            )

    best = outcome.best
    return {
        "full_name": full_name,
        "company_name": company_name,
        "company_domain": outcome.domain,
        "title": title or "",
        "best_email": best.email if best else "",
        "email_status": best.verification_state if best else "",
        "email_score": f"{best.final_score:.4f}" if best and best.final_score is not None else "",
        "pattern_code": best.pattern_code if best else "",
        "error": "",
    }


async def _mark_job_failed(job_id: str, error: str) -> None:
    from app.db.engine import async_session_factory
    from app.db import models as m

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = error[:1000]


async def _run_bulk_find_verify(job_id: str, rows: list[dict]) -> None:
    from app.db.engine import async_session_factory
    from app.db import models as m
    from app.config import get_settings

    settings = get_settings()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if not job:
                logger.error("Job %s not found", job_id)
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.progress_total = len(rows)
            job.attempt_count = (job.attempt_count or 0) + 1

    results: list[dict] = []
    errors = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        for idx, row in enumerate(rows):
            try:
                result = await _process_row(row, settings, client)
            except Exception as exc:
                logger.warning("Row %d failed: %s", idx, exc)
                result = {
                    "full_name": row.get("full_name", ""),
                    "company_name": row.get("company_name", ""),
                    "company_domain": row.get("company_domain", ""),
                    "title": row.get("title", ""),
                    "best_email": "",
                    "email_status": "",
                    "email_score": "",
                    "pattern_code": "",
                    "error": str(exc),
                }
                errors += 1
            results.append(result)

            async with async_session_factory() as session:
                async with session.begin():
                    job = await session.get(m.Job, uuid.UUID(job_id))
                    if job:
                        job.progress_current = idx + 1

    artifact_path = ARTIFACT_DIR / f"{job_id}.csv"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ARTIFACT_COLUMNS, extrasaction="ignore")
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
                    "total": len(rows),
                    "succeeded": len(rows) - errors,
                    "errors": errors,
                }


@celery_app.task(bind=True, name="sdr.tasks.bulk_find_verify")
def bulk_find_verify_task(self, job_id: str, rows: list[dict]) -> None:
    """Sync Celery task — bridges to async via asyncio.run()."""
    try:
        asyncio.run(_run_bulk_find_verify(job_id, rows))
    except Exception as exc:
        logger.error("Bulk find-verify job %s failed: %s", job_id, exc)
        asyncio.run(_mark_job_failed(job_id, str(exc)))
        raise
