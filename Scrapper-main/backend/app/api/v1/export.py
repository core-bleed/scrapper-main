"""Export endpoint (Week 8)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import ExportRequest
from app.core.export import build_export_rows, rows_to_csv, rows_to_xlsx
from app.db import models as m

router = APIRouter(tags=["export"])


@router.post("/export")
async def export_leads(
    body: ExportRequest,
    session: AsyncSession = Depends(get_db),
) -> Response:
    if not body.list_id and not body.person_ids:
        raise HTTPException(
            status_code=422,
            detail="Provide either list_id or person_ids",
        )

    if body.list_id:
        r = await session.execute(
            select(m.ListEntry.person_id).where(m.ListEntry.list_id == body.list_id)
        )
        person_ids = list(r.scalars().all())
        if not person_ids:
            raise HTTPException(status_code=404, detail="List not found or has no entries")
    else:
        person_ids = body.person_ids or []

    person_ids = person_ids[:5000]
    rows = await build_export_rows(session, person_ids)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if body.format == "xlsx":
        content = rows_to_xlsx(rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="sdr_export_{ts}.xlsx"'},
        )
    content = rows_to_csv(rows)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sdr_export_{ts}.csv"'},
    )
