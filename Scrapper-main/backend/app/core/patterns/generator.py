"""Generate candidate work emails from name + domain (pattern engine)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.enrichers.apollo import split_name
from app.core.schemas import normalize_domain


def _slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _first_initial(first: str | None) -> str:
    if not first:
        return ""
    return first[0].lower()


def _last_initial(last: str | None) -> str:
    if not last:
        return ""
    return last[0].lower()


@dataclass(frozen=True)
class GeneratedCandidate:
    email: str
    local_part: str
    pattern_code: str


def generate_candidates(full_name: str, domain: str) -> list[GeneratedCandidate]:
    """Return deduplicated candidate emails with stable pattern_code labels."""
    d = normalize_domain(domain)
    if not d:
        return []

    first, last = split_name(full_name.strip())
    fn = (first or "").strip().lower()
    ln = (last or "").strip().lower()
    if not fn and not ln:
        return []

    fi = _first_initial(fn)
    li = _last_initial(ln)

    rows: list[tuple[str, str]] = []

    def add(pattern_code: str, local: str) -> None:
        local = local.lower().strip()
        if not local or ".." in local or local.startswith(".") or local.endswith("."):
            return
        rows.append((pattern_code, local))

    if fn and ln:
        add("first.last", f"{fn}.{ln}")
        add("flast", f"{fi}{ln}")
        add("f.last", f"{fi}.{ln}")
        add("first_last", f"{fn}_{ln}")
        add("first-last", f"{fn}-{ln}")
        add("firstlast", f"{fn}{ln}")
        add("last.first", f"{ln}.{fn}")
        add("lastfirst", f"{ln}{fn}")
        add("firstl", f"{fn}{li}")
        add("f_last", f"{fi}_{ln}")
        add("last_f", f"{ln}_{fi}")
    if fn:
        add("first", fn)
        add("first_initial", fi)
    if ln:
        add("last", ln)

    seen: set[str] = set()
    out: list[GeneratedCandidate] = []
    for pattern_code, local in rows:
        if local in seen:
            continue
        seen.add(local)
        out.append(GeneratedCandidate(email=f"{local}@{d}", local_part=local, pattern_code=pattern_code))

    return out
