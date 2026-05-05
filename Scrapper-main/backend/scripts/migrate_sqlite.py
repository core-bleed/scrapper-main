#!/usr/bin/env python3
"""Copy legacy SQLite `sdr.db` into PostgreSQL using the canonical ORM models."""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import infer_seniority, normalize_domain
from app.db import models as m
from app.db.engine import async_session_factory


def company_uuid(old_id: int) -> UUID:
    return uuid5(NAMESPACE_DNS, f"sdr-scraper:company:{old_id}")


def person_uuid(old_id: int) -> UUID:
    return uuid5(NAMESPACE_DNS, f"sdr-scraper:person:{old_id}")


async def main(sqlite_path: Path) -> None:
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row

    async with async_session_factory() as session:
        await _migrate(sqlite_conn, session)
        await session.commit()

    sqlite_conn.close()


async def _migrate(sqlite_conn: sqlite3.Connection, session: AsyncSession) -> None:
    companies = list(sqlite_conn.execute("SELECT * FROM companies ORDER BY id"))
    for row in companies:
        old_id = int(row["id"])
        cid = company_uuid(old_id)
        if await session.get(m.Company, cid):
            continue
        domain = normalize_domain(row["domain"])
        raw = {
            "sqlite_id": old_id,
            "batch": row["batch"],
            "source": row["source"],
            "source_url": row["source_url"],
            "tags": row["tags"],
            "description": row["description"],
        }
        team_size = str(row["team_size"]) if row["team_size"] is not None else None
        session.add(
            m.Company(
                id=cid,
                name=row["name"] or "",
                normalized_name=(row["name"] or "").strip().lower() or None,
                primary_domain=domain,
                website=row["website"],
                industry=row["industry"],
                location=row["location"],
                team_size=team_size,
                founded_year=row["founded_year"],
                domain_source=row["source"],
                raw_data=raw,
            )
        )

    await session.flush()

    people = list(sqlite_conn.execute("SELECT * FROM people ORDER BY id"))
    for row in people:
        old_id = int(row["id"])
        pid = person_uuid(old_id)
        if await session.get(m.Person, pid):
            continue
        seniority = row["seniority"] or infer_seniority(row["title"])
        raw_p = {
            "sqlite_id": old_id,
            "twitter_url": row["twitter_url"],
            "source": row["source"],
            "source_url": row["source_url"],
            "is_decision_maker": row["is_decision_maker"],
        }
        session.add(
            m.Person(
                id=pid,
                full_name=row["full_name"] or "",
                first_name=row["first_name"],
                last_name=row["last_name"],
                normalized_full_name=(row["full_name"] or "").strip().lower() or None,
                linkedin_url=row["linkedin_url"],
                headline=row["headline"],
                location=row["location"],
                raw_data=raw_p,
            )
        )

        company_old_id = int(row["company_id"])
        cid = company_uuid(company_old_id)
        if not await session.get(m.Company, cid):
            continue
        is_cs = seniority in ("c_suite", "founder")
        session.add(
            m.Employment(
                person_id=pid,
                company_id=cid,
                title=row["title"],
                seniority=seniority,
                is_current=True,
                is_c_suite=is_cs,
            )
        )

    await session.flush()

    cms = list(
        sqlite_conn.execute(
            "SELECT * FROM contact_methods WHERE method_type = 'work_email' ORDER BY id"
        )
    )
    for cm in cms:
        person_old = int(cm["person_id"])
        pid = person_uuid(person_old)
        pr = sqlite_conn.execute(
            "SELECT company_id FROM people WHERE id = ?", (person_old,)
        ).fetchone()
        if not pr:
            continue
        cid = company_uuid(int(pr["company_id"]))
        if not await session.get(m.Person, pid) or not await session.get(m.Company, cid):
            continue
        email = (cm["value"] or "").strip().lower()
        if not email or "@" not in email:
            continue
        dup = await session.execute(
            select(m.ContactCandidate.id).where(
                m.ContactCandidate.person_id == pid,
                m.ContactCandidate.normalized_email == email,
            )
        )
        if dup.scalar_one_or_none():
            continue
        local, _, dom = email.partition("@")
        status = (cm["status"] or "unknown").lower().replace(" ", "_")
        session.add(
            m.ContactCandidate(
                person_id=pid,
                company_id=cid,
                email=cm["value"],
                normalized_email=email,
                domain=dom,
                local_part=local,
                generation_source=(cm["provider"] or "import"),
                verification_state=status if status in ("valid", "invalid", "unknown") else "unknown",
            )
        )

    print(
        f"Migrated: companies={len(companies)} people={len(people)} "
        f"work_email_rows={len(cms)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=REPO_ROOT / "sdr.db",
        help="Path to legacy SQLite database",
    )
    args = parser.parse_args()
    if not args.sqlite.exists():
        print(f"SQLite file not found: {args.sqlite}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(args.sqlite))
