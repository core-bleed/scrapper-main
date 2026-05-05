from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.v1.schemas import ListCreate, ListEntryCreate, ListOut, PaginationMeta, PersonListItem
from app.db import models as m
from app.db import queries as q
from app.db import repository as repo

router = APIRouter(prefix="/lists", tags=["lists"])


@router.post("", response_model=ListOut)
async def create_list(
    body: ListCreate,
    session: AsyncSession = Depends(get_db),
) -> ListOut:
    lead_list = m.LeadList(
        id=uuid.uuid4(),
        name=body.name.strip(),
        description=body.description,
    )
    session.add(lead_list)
    await session.flush()
    await session.refresh(lead_list)
    return ListOut(
        id=lead_list.id,
        name=lead_list.name,
        description=lead_list.description,
        entry_count=0,
        created_at=lead_list.created_at,
        updated_at=lead_list.updated_at,
    )


@router.get("", response_model=list[ListOut])
async def list_lists(session: AsyncSession = Depends(get_db)) -> list[ListOut]:
    rows = await q.list_lead_lists_with_counts(session)
    return [
        ListOut(
            id=lst.id,
            name=lst.name,
            description=lst.description,
            entry_count=cnt,
            created_at=lst.created_at,
            updated_at=lst.updated_at,
        )
        for lst, cnt in rows
    ]


@router.post("/{list_id}/entries", status_code=201)
async def add_list_entry(
    list_id: uuid.UUID,
    body: ListEntryCreate,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    lst = await q.get_lead_list(session, list_id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")

    person = await repo.get_person_by_id(session, body.person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    existing = await q.get_list_entry(session, list_id, body.person_id)
    if existing:
        return {"status": "already_added", "entry_id": str(existing.id)}

    entry = m.ListEntry(
        id=uuid.uuid4(),
        list_id=list_id,
        person_id=body.person_id,
    )
    session.add(entry)
    await session.flush()
    return {"status": "created", "entry_id": str(entry.id)}


@router.get("/{list_id}/entries")
async def get_list_entries(
    list_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
) -> dict:
    lst = await q.get_lead_list(session, list_id)
    if not lst:
        raise HTTPException(status_code=404, detail="List not found")
    limit = min(max(limit, 1), 200)
    people, total = await q.list_people_in_list(session, list_id, limit=limit, offset=offset)

    def _item(person: m.Person) -> PersonListItem:
        emp = next((e for e in person.employments if e.is_current), None)
        if emp is None and person.employments:
            emp = max(person.employments, key=lambda e: (e.title_rank, e.updated_at or e.created_at))
        return PersonListItem(
            id=person.id,
            full_name=person.full_name,
            linkedin_url=person.linkedin_url,
            headline=person.headline,
            location=person.location,
            current_title=emp.title if emp else None,
            current_company_name=emp.company.name if emp and emp.company else None,
            seniority=emp.seniority if emp else None,
        )

    return {
        "items": [_item(p) for p in people],
        "meta": PaginationMeta(total=total, limit=limit, offset=offset),
    }


@router.delete("/{list_id}/entries/{person_id}", status_code=204)
async def remove_list_entry(
    list_id: uuid.UUID,
    person_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> None:
    entry = await q.get_list_entry(session, list_id, person_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await session.delete(entry)
