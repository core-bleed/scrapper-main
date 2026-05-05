from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from sdr_cli.db import upsert_company, upsert_person
from sdr_cli.models import Company, Person


YC_API_BASE = "https://api.ycombinator.com/v0.1/companies"
YC_COMPANY_BASE = "https://www.ycombinator.com/companies/"


def fetch_companies(
    client: httpx.Client,
    limit: int,
    batch: str | None,
    delay: float,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    next_url: str | None = YC_API_BASE + "?page=1"
    while next_url and len(out) < limit:
        r = client.get(next_url)
        r.raise_for_status()
        data = r.json()
        for c in data.get("companies") or []:
            if batch and (c.get("batch") or "").strip().lower() != batch.strip().lower():
                continue
            out.append(c)
            if len(out) >= limit:
                break
        next_url = data.get("nextPage")
        if len(out) < limit and next_url:
            time.sleep(delay)
    return out[:limit]


def _normalize_social(href: str | None) -> str | None:
    if not href:
        return None
    h = href.strip()
    if h.startswith("//"):
        h = "https:" + h
    return h


def parse_founders_html(html: str, company_page_url: str) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    marker = None
    for tag in soup.find_all(string=re.compile(r"Active Founders")):
        text = (tag.string or tag.get_text() or "").strip()
        if text == "Active Founders":
            marker = tag
            break
    if not marker:
        return []

    heading_el = marker.parent if hasattr(marker, "parent") else None
    root = None
    if heading_el:
        root = heading_el.find_next(
            "div",
            class_=lambda c: bool(c) and "gap-y-4" in " ".join(c),
        )
    if root is None:
        root = marker.find_parent("div")
    if root is None:
        return []
    for _ in range(4):
        if root and root.parent:
            test = root.find_all("a", href=re.compile(r"linkedin\.com/in/", re.I))
            if len(test) >= 1:
                break
            root = root.parent

    seen_li: set[str] = set()
    founders: list[dict[str, str | None]] = []

    for a in root.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" not in href.lower():
            continue
        if "linkedin.com/company/" in href.lower():
            continue
        li = _normalize_social(href)
        if not li:
            continue
        li = li.split("?")[0].rstrip("/")
        key = li.lower()
        if key in seen_li:
            continue
        seen_li.add(key)

        card = a.find_parent("div", class_=lambda c: bool(c) and "border-b" in c)
        if not card:
            card = a.find_parent("div", class_=lambda c: bool(c) and "ycdc-card-new" in c)
        if not card:
            card = a.find_parent("div")

        name = None
        title = None
        twitter = None
        for bold in card.find_all(
            "div",
            class_=lambda c: bool(c)
            and ("font-bold" in c or "text-xl" in c or "text-lg" in c),
        ):
            text = bold.get_text(strip=True)
            if text and len(text) < 120 and not text.startswith("http"):
                if name is None and "linkedin" not in text.lower():
                    name = text
                break
        if not name:
            img = card.find("img", alt=True)
            if img and img.get("alt"):
                name = img["alt"].strip()

        for sub in card.find_all("div", class_=lambda c: bool(c) and "gray-600" in c):
            t = sub.get_text(strip=True)
            if t and 2 < len(t) < 200:
                title = t
                break

        for ta in card.find_all("a", href=True):
            th = ta["href"]
            if "x.com/" in th or "twitter.com/" in th:
                twitter = _normalize_social(th)
                break

        if name:
            founders.append(
                {
                    "full_name": name,
                    "title": title,
                    "linkedin_url": li,
                    "twitter_url": twitter,
                }
            )

    return founders


def fetch_founders(
    client: httpx.Client,
    company_slug: str,
    delay: float,
) -> list[dict[str, str | None]]:
    url = urljoin(YC_COMPANY_BASE, company_slug)
    time.sleep(delay)
    r = client.get(url, follow_redirects=True)
    r.raise_for_status()
    return parse_founders_html(r.text, url)


def scrape_yc(
    conn,
    client: httpx.Client,
    limit: int,
    batch: str | None,
    delay: float,
) -> dict[str, int]:
    companies_data = fetch_companies(client, limit, batch, delay)
    stats = {"companies": 0, "founders": 0, "errors": 0}
    for raw in companies_data:
        slug = raw.get("slug") or ""
        name = raw.get("name") or slug
        website = raw.get("website")
        one_liner = raw.get("oneLiner") or ""
        long_desc = raw.get("longDescription") or ""
        description = long_desc.strip() or one_liner.strip() or None
        team_size = raw.get("teamSize")
        batch_val = raw.get("batch")
        tags_list = raw.get("tags") or []
        tags = ", ".join(tags_list) if tags_list else None
        industries = raw.get("industries") or []
        industry = industries[0] if industries else None
        locations = raw.get("locations") or []
        location = locations[0] if locations else None
        source_url = raw.get("url") or f"{YC_COMPANY_BASE}{slug}"

        try:
            company = Company(
                name=name,
                website=website,
                description=description,
                industry=industry,
                location=location,
                team_size=int(team_size) if team_size is not None else None,
                founded_year=None,
                batch=batch_val,
                source="yc",
                source_url=source_url,
                tags=tags,
            )
            cid = upsert_company(conn, company)
            stats["companies"] += 1
        except Exception:
            stats["errors"] += 1
            continue

        try:
            founders = fetch_founders(client, slug, delay) if slug else []
        except Exception:
            stats["errors"] += 1
            founders = []

        for f in founders:
            try:
                full = (f.get("full_name") or "").strip()
                if not full:
                    continue
                person = Person(
                    company_id=cid,
                    full_name=full,
                    title=f.get("title"),
                    linkedin_url=f.get("linkedin_url"),
                    twitter_url=f.get("twitter_url"),
                    source="yc",
                    source_url=source_url,
                )
                upsert_person(conn, person)
                stats["founders"] += 1
            except Exception:
                stats["errors"] += 1

    return stats
