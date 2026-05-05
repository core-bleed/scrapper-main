"""Bulk email-only verification Celery task (Week 4)."""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.tasks import celery_app

logger = logging.getLogger(__name__)

ARTIFACT_DIR = Path("/tmp/sdr_jobs")
ARTIFACT_COLUMNS = ["email", "status", "confidence", "provider", "error"]


async def _run_bulk_verify(job_id: str, emails: list[str]) -> None:
    import httpx

    from app.config import get_settings
    from app.core.verifiers.factory import get_verifier
    from app.db import models as m
    from app.db.engine import async_session_factory

    settings = get_settings()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_session_factory() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if not job:
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.progress_total = len(emails)
            job.attempt_count = (job.attempt_count or 0) + 1

    results: list[dict] = []
    errors = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        verifier = get_verifier(settings, client=client)
        for idx, email in enumerate(emails):
            try:
                result = await verifier.verify(email.strip())
                results.append({
                    "email": email,
                    "status": result.status,
                    "confidence": f"{result.confidence:.4f}" if result.confidence is not None else "",
                    "provider": result.provider,
                    "error": "",
                })
            except Exception as exc:
                logger.warning("Verify %s failed: %s", email, exc)
                results.append({
                    "email": email,
                    "status": "unknown",
                    "confidence": "",
                    "provider": "",
                    "error": str(exc),
                })
                errors += 1

            from app.db.engine import async_session_factory as _sf
            async with _sf() as session:
                async with session.begin():
                    job = await session.get(m.Job, uuid.UUID(job_id))
                    if job:
                        job.progress_current = idx + 1

    artifact_path = ARTIFACT_DIR / f"{job_id}_verify.csv"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=ARTIFACT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(results)
    artifact_path.write_text(buf.getvalue(), encoding="utf-8")

    from app.db.engine import async_session_factory as _sf2
    async with _sf2() as session:
        async with session.begin():
            job = await session.get(m.Job, uuid.UUID(job_id))
            if job:
                job.status = "succeeded"
                job.completed_at = datetime.now(timezone.utc)
                job.artifact_path = str(artifact_path)
                job.result_summary = {"total": len(emails), "errors": errors}


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


@celery_app.task(bind=True, name="sdr.tasks.bulk_verify")
def bulk_verify_task(self, job_id: str, emails: list[str]) -> None:
    """Sync Celery task — bridges to async via asyncio.run()."""
    try:
        asyncio.run(_run_bulk_verify(job_id, emails))
    except Exception as exc:
        logger.error("Bulk verify job %s failed: %s", job_id, exc)
        asyncio.run(_fail_job(job_id, str(exc)))
        raise
