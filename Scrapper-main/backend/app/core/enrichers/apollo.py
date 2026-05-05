from __future__ import annotations

import httpx

from app.core.schemas import ContactMethod
from app.db.legacy_sqlite import add_contact_method, get_people_without_work_email

APOLLO_MATCH_URL = "https://api.apollo.io/api/v1/people/match"


def enrich_person(
    api_key: str,
    first_name: str | None,
    last_name: str | None,
    domain: str,
    *,
    client: httpx.Client | None = None,
) -> dict | None:
    """Call Apollo people match. Returns dict with email, linkedin_url, title or None."""
    fn = (first_name or "").strip()
    ln = (last_name or "").strip()
    payload: dict = {"domain": domain}
    if fn:
        payload["first_name"] = fn
    if ln:
        payload["last_name"] = ln

    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }
    own = client is None
    if own:
        client = httpx.Client(timeout=30.0)
    try:
        r = client.post(APOLLO_MATCH_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        person = data.get("person")
        if not person:
            return None
        email = person.get("email")
        li = person.get("linkedin_url")
        title = person.get("title")
        return {
            "email": email,
            "linkedin_url": li,
            "title": title,
        }
    finally:
        if own:
            client.close()


def split_name(full_name: str) -> tuple[str | None, str | None]:
    parts = full_name.strip().split(None, 1)
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def run_enrichment(
    conn,
    api_key: str,
    limit: int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, int]:
    stats = {"processed": 0, "emails": 0, "errors": 0}
    rows = get_people_without_work_email(conn, limit)
    own = client is None
    if own:
        client = httpx.Client(timeout=60.0)
    try:
        for row in rows:
            pid = row["id"]
            domain = row["company_domain"]
            full = row["full_name"]
            fn, ln = split_name(full)
            try:
                result = enrich_person(api_key, fn, ln, domain, client=client)
                stats["processed"] += 1
                if result and result.get("email"):
                    add_contact_method(
                        conn,
                        ContactMethod(
                            person_id=pid,
                            method_type="work_email",
                            value=result["email"],
                            status="discovered",
                            provider="apollo",
                            confidence_score=None,
                        ),
                    )
                    stats["emails"] += 1
            except Exception:
                stats["errors"] += 1
    finally:
        if own:
            client.close()
    return stats
