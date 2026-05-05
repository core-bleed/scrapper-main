"""Bulk job submission + recheck API (Week 4)."""
from __future__ import annotations

import csv
import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import BulkJobResponse, RecheckResponse
from app.db import models as m

router = APIRouter(tags=["bulk"])

MAX_ROWS = 1000


def _parse_csv_bytes(data: bytes, required_cols: list[str]) -> list[dict]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV has no headers")
    headers = [h.strip().lower() for h in reader.fieldnames]
    missing = [c for c in required_cols if c not in headers]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}. Found: {headers}")
    rows: list[dict] = []
    for row in reader:
        clean = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        rows.append(clean)
        if len(rows) >= MAX_ROWS:
            break
    return rows


@router.post("/bulk/find-and-verify", response_model=BulkJobResponse)
async def bulk_find_and_verify(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
) -> BulkJobResponse:
    data = await file.read()
    try:
        rows = _parse_csv_bytes(data, required_cols=["full_name"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=400, detail="CSV is empty")

    sample = rows[0]
    if not sample.get("company_name") and not sample.get("company_domain"):
        raise HTTPException(
            status_code=400,
            detail="CSV must have a 'company_name' or 'company_domain' column",
        )

    job = m.Job(
        id=uuid.uuid4(),
        job_type="bulk_find_and_verify",
        status="queued",
        progress_total=len(rows),
        input_params={"rows": rows, "row_count": len(rows)},
    )
    session.add(job)
    await session.flush()
    job_id = job.id

    from app.tasks.bulk_find_verify import bulk_find_verify_task
    bulk_find_verify_task.delay(str(job_id), rows)

    return BulkJobResponse(job_id=job_id, total_rows=len(rows))


@router.post("/bulk/verify", response_model=BulkJobResponse)
async def bulk_verify(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
) -> BulkJobResponse:
    data = await file.read()
    try:
        rows = _parse_csv_bytes(data, required_cols=["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    emails = [r["email"] for r in rows if r.get("email")]
    if not emails:
        raise HTTPException(status_code=400, detail="No valid emails found in CSV")

    job = m.Job(
        id=uuid.uuid4(),
        job_type="bulk_verify",
        status="queued",
        progress_total=len(emails),
        input_params={"emails": emails},
    )
    session.add(job)
    await session.flush()
    job_id = job.id

    from app.tasks.bulk_verify import bulk_verify_task
    bulk_verify_task.delay(str(job_id), emails)

    return BulkJobResponse(job_id=job_id, total_rows=len(emails))


@router.post("/recheck/person/{person_id}", response_model=RecheckResponse)
async def recheck_person(
    person_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> RecheckResponse:
    person = await session.get(m.Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    job = m.Job(
        id=uuid.uuid4(),
        job_type="recheck_person",
        status="queued",
        input_params={"person_id": str(person_id)},
    )
    session.add(job)
    await session.flush()
    job_id = job.id

    from app.tasks.recheck import recheck_person_task
    recheck_person_task.delay(str(job_id), str(person_id))

    return RecheckResponse(job_id=job_id)
