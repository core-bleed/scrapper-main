from __future__ import annotations

import json
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from sdr_cli.db import domain_from_url, upsert_company, upsert_person
from sdr_cli.models import Company, Person

TEAM_PATHS = ["/team", "/about", "/about-us", "/company", "/people", "/leadership"]


def _base_url(domain: str) -> str:
    d = domain.strip().lower().rstrip("/")
    if d.startswith("http://") or d.startswith("https://"):
        parsed = urlparse(d)
        return f"{parsed.scheme}://{parsed.netloc}"
    return f"https://{d}"


def find_team_page(client: httpx.Client, domain: str, delay: float) -> tuple[str | None, str | None]:
    base = _base_url(domain)
    for path in TEAM_PATHS:
        url = urljoin(base, path)
        time.sleep(delay)
        try:
            r = client.get(url, follow_redirects=True)
            if r.status_code == 200 and len(r.text) > 500:
                return url, r.text
        except Exception:
            continue
    return None, None


def extract_people_from_page(html: str, company_id: int, source_url: str) -> list[Person]:
    soup = BeautifulSoup(html, "html.parser")
    people: list[Person] = []
    seen_li: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" not in href.lower():
            continue
        if "linkedin.com/company/" in href.lower():
            continue
        li = href.split("?")[0].rstrip("/")
        if not li.startswith("http"):
            li = "https://" + li.lstrip("/")
        key = li.lower()
        if key in seen_li:
            continue
        seen_li.add(key)

        name = a.get_text(strip=True) or None
        if not name or len(name) > 100:
            parent = a.find_parent(["h2", "h3", "h4", "div", "li"])
            if parent:
                for tag in parent.find_all(["span", "strong", "div"]):
                    t = tag.get_text(strip=True)
                    if 3 < len(t) < 80 and "linkedin" not in t.lower():
                        name = t
                        break
        if not name:
            continue

        title = None
        card = a.find_parent("div") or a.find_parent("li")
        if card:
            for line in card.stripped_strings:
                if line != name and 2 < len(line) < 120:
                    title = line
                    break

        people.append(
            Person(
                company_id=company_id,
                full_name=name,
                title=title,
                linkedin_url=li,
                source="team_page",
                source_url=source_url,
            )
        )

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("Person", "Organization"):
                continue
            if item.get("@type") == "Person":
                n = item.get("name")
                li = item.get("sameAs") or item.get("url")
                if isinstance(li, list):
                    li = next((x for x in li if "linkedin.com/in/" in x.lower()), None)
                if n and li and isinstance(li, str) and "linkedin.com/in/" in li.lower():
                    key = li.split("?")[0].lower()
                    if key in seen_li:
                        continue
                    seen_li.add(key)
                    people.append(
                        Person(
                            company_id=company_id,
                            full_name=str(n),
                            title=item.get("jobTitle"),
                            linkedin_url=li.split("?")[0],
                            source="team_page",
                            source_url=source_url,
                        )
                    )

    return people


def scrape_team_pages_for_companies(
    conn,
    client: httpx.Client,
    limit: int,
    delay: float,
) -> dict[str, int]:
    from sdr_cli.db import get_companies

    stats = {"companies_tried": 0, "people": 0, "skipped": 0, "errors": 0}
    rows = get_companies(conn)
    tried = 0
    for row in rows:
        if tried >= limit:
            break
        domain = row["domain"]
        if not domain:
            stats["skipped"] += 1
            continue
        tried += 1
        stats["companies_tried"] += 1
        url, html = find_team_page(client, domain, delay)
        if not html or not url:
            continue
        cid = row["id"]
        try:
            for person in extract_people_from_page(html, cid, url):
                upsert_person(conn, person)
                stats["people"] += 1
        except Exception:
            stats["errors"] += 1
    return stats


def scrape_team_page_domain(
    conn,
    client: httpx.Client,
    domain: str,
    delay: float,
) -> dict[str, int]:
    stats = {"people": 0, "errors": 0}
    co = Company(
        name=domain,
        website=f"https://{domain_from_url(domain) or domain}",
        source="team_page",
        source_url=None,
    )
    try:
        cid = upsert_company(conn, co)
    except Exception:
        stats["errors"] += 1
        return stats
    url, html = find_team_page(client, domain, delay)
    if not html:
        return stats
    try:
        for person in extract_people_from_page(html, cid, url):
            upsert_person(conn, person)
            stats["people"] += 1
    except Exception:
        stats["errors"] += 1
    return stats
