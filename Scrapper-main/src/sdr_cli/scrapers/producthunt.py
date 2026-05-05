from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx

from sdr_cli.db import upsert_company, upsert_person
from sdr_cli.models import Company, Person

PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"

POSTS_QUERY = """
query Posts($first: Int!, $postedAfter: DateTime) {
  posts(first: $first, postedAfter: $postedAfter, order: NEWEST) {
    edges {
      node {
        name
        tagline
        website
        url
        createdAt
        makers {
          name
          username
          twitterUsername
          url
        }
      }
    }
  }
}
"""


def fetch_posts(
    access_token: str,
    days: int,
    limit: int,
    *,
    client: httpx.Client | None = None,
) -> list[dict]:
    after_dt = datetime.now(timezone.utc) - timedelta(days=days)
    posted_after = after_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    variables = {"first": min(max(limit, 1), 50), "postedAfter": posted_after}
    payload = {"query": POSTS_QUERY, "variables": variables}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    own = client is None
    if own:
        client = httpx.Client(timeout=60.0)
    try:
        r = client.post(PH_GRAPHQL, headers=headers, json=payload)
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise RuntimeError(json.dumps(body["errors"]))
        edges = body.get("data", {}).get("posts", {}).get("edges") or []
        out: list[dict] = []
        for e in edges:
            n = e.get("node")
            if n:
                out.append(n)
        return out[:limit]
    finally:
        if own:
            client.close()


def scrape_producthunt(
    conn,
    access_token: str,
    days: int,
    limit: int,
    *,
    client: httpx.Client | None = None,
) -> dict[str, int]:
    stats = {"companies": 0, "people": 0, "errors": 0}
    try:
        posts = fetch_posts(access_token, days, limit, client=client)
    except Exception:
        stats["errors"] += 1
        return stats

    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=60.0)

    try:
        for post in posts:
            name = (post.get("name") or "").strip() or "Unknown"
            tagline = post.get("tagline")
            website = post.get("website") or ""
            url = post.get("url") or ""
            try:
                co = Company(
                    name=name,
                    website=website if website else None,
                    description=tagline,
                    source="producthunt",
                    source_url=url,
                )
                cid = upsert_company(conn, co)
                stats["companies"] += 1
            except Exception:
                stats["errors"] += 1
                continue

            makers = post.get("makers") or []
            if not isinstance(makers, list):
                continue
            for node in makers:
                pname = (node.get("name") or "").strip()
                if not pname:
                    continue
                tw = node.get("twitterUsername")
                twitter_url = f"https://x.com/{tw}" if tw else None
                try:
                    pe = Person(
                        company_id=cid,
                        full_name=pname,
                        twitter_url=twitter_url,
                        source="producthunt",
                        source_url=url,
                    )
                    upsert_person(conn, pe)
                    stats["people"] += 1
                except Exception:
                    stats["errors"] += 1
    finally:
        if own_client:
            client.close()

    return stats
