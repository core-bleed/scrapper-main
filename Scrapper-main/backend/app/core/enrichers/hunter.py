from __future__ import annotations

import httpx

from app.core.enrichers.apollo import split_name
from app.core.schemas import ContactMethod
from app.db.legacy_sqlite import add_contact_method, get_people_without_work_email

HUNTER_FIND_URL = "https://api.hunter.io/v2/email-finder"
HUNTER_VERIFY_URL = "https://api.hunter.io/v2/email-verifier"


def find_email(
    api_key: str,
    domain: str,
    first_name: str | None,
    last_name: str | None,
    *,
    client: httpx.Client | None = None,
) -> dict | None:
    params = {
        "domain": domain,
        "api_key": api_key,
    }
    if first_name:
        params["first_name"] = first_name
    if last_name:
        params["last_name"] = last_name

    own = client is None
    if own:
        client = httpx.Client(timeout=30.0)
    try:
        r = client.get(HUNTER_FIND_URL, params=params)
        r.raise_for_status()
        data = r.json().get("data") or {}
        email = data.get("email")
        score = data.get("score")
        if not email:
            return None
        return {"email": email, "score": score}
    finally:
        if own:
            client.close()


def verify_email(api_key: str, email: str, *, client: httpx.Client | None = None) -> dict | None:
    params = {"email": email, "api_key": api_key}
    own = client is None
    if own:
        client = httpx.Client(timeout=30.0)
    try:
        r = client.get(HUNTER_VERIFY_URL, params=params)
        r.raise_for_status()
        data = r.json().get("data") or {}
        return {
            "status": data.get("status"),
            "result": data.get("result"),
            "score": data.get("score"),
        }
    finally:
        if own:
            client.close()


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
                result = find_email(api_key, domain, fn, ln, client=client)
                stats["processed"] += 1
                if result and result.get("email"):
                    add_contact_method(
                        conn,
                        ContactMethod(
                            person_id=pid,
                            method_type="work_email",
                            value=result["email"],
                            status="discovered",
                            provider="hunter",
                            confidence_score=float(result["score"])
                            if result.get("score") is not None
                            else None,
                        ),
                    )
                    stats["emails"] += 1
            except Exception:
                stats["errors"] += 1
    finally:
        if own:
            client.close()
    return stats


def run_verify(
    conn,
    api_key: str,
    limit: int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, int]:
    """Verify existing work emails via Hunter and update status."""
    stats = {"processed": 0, "updated": 0, "errors": 0}
    rows = list(
        conn.execute(
            """
            SELECT id, person_id, value FROM contact_methods
            WHERE method_type = 'work_email' AND provider = 'hunter'
            ORDER BY id LIMIT ?
            """,
            (limit,),
        )
    )
    own = client is None
    if own:
        client = httpx.Client(timeout=60.0)
    try:
        for row in rows:
            email = row["value"]
            try:
                info = verify_email(api_key, email, client=client)
                stats["processed"] += 1
                if info and info.get("result"):
                    status = str(info.get("result") or info.get("status") or "verified")
                    conn.execute(
                        "UPDATE contact_methods SET status = ? WHERE id = ?",
                        (status, row["id"]),
                    )
                    conn.commit()
                    stats["updated"] += 1
            except Exception:
                stats["errors"] += 1
    finally:
        if own:
            client.close()
    return stats
