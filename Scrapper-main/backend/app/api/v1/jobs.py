"""Jobs monitoring API (Week 4)."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import JobDetail, JobListResponse, JobOut, PaginationMeta
from app.db import models as m

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    job_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> JobListResponse:
    limit = min(max(limit, 1), 100)
    conds = []
    if job_type:
        conds.append(m.Job.job_type == job_type)
    if status:
        conds.append(m.Job.status == status)

    count_q = select(func.count()).select_from(m.Job)
    list_q = select(m.Job).order_by(m.Job.created_at.desc()).limit(limit).offset(offset)
    if conds:
        where = and_(*conds)
        count_q = count_q.where(where)
        list_q = list_q.where(where)

    total = int((await session.execute(count_q)).scalar_one() or 0)
    rows = list((await session.execute(list_q)).scalars().all())

    return JobListResponse(
        items=[JobOut.model_validate(j) for j in rows],
        meta=PaginationMeta(total=total, limit=limit, offset=offset),
    )


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> JobDetail:
    job = await session.get(m.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobDetail.model_validate(job)


@router.get("/{job_id}/results")
async def get_job_results(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> FileResponse:
    job = await session.get(m.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.artifact_path:
        raise HTTPException(status_code=400, detail="No results available — job may not be complete")
    path = Path(job.artifact_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Result file not found on disk")
    return FileResponse(
        str(path),
        media_type="text/csv",
        filename=f"sdr_job_{job_id}.csv",
    )


@router.delete("/{job_id}", status_code=204)
async def cancel_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Response:
    job = await session.get(m.Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from datetime import datetime, timezone
    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    try:
        from app.tasks import celery_app
        celery_app.control.revoke(str(job_id), terminate=True)
    except Exception:
        pass
    return Response(status_code=204)
