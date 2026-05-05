# Backend documentation

FastAPI service for the **personal outbound intelligence platform**: canonical lead graph in PostgreSQL, async SQLAlchemy, Alembic migrations. The legacy **CLI** remains SQLite-based; this backend is the source of truth when you use Compose or run the API locally.

For product context and roadmap, see [`PRD.md`](../PRD.md) and [`PLAN.md`](../PLAN.md) in the repo root. The root [`README.md`](../README.md) covers the whole monorepo (CLI + Docker + env vars).

---

## Table of contents

- [Stack](#stack)
- [Project layout](#project-layout)
- [Configuration](#configuration)
- [Run the API](#run-the-api)
- [Database and migrations](#database-and-migrations)
- [SQLite → PostgreSQL migration](#sqlite--postgresql-migration)
- [HTTP API (v1)](#http-api-v1)
- [Capture and identity resolution](#capture-and-identity-resolution)
- [Domain resolution](#domain-resolution)
- [Pattern engine, verification, and ranking](#pattern-engine-verification-and-ranking)
- [OpenAPI / interactive docs](#openapi--interactive-docs)
- [Development notes](#development-notes)

---

## Stack

| Layer | Technology |
|-------|------------|
| HTTP API | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| ORM | [SQLAlchemy 2.0](https://docs.sqlalchemy.org/) (async), [asyncpg](https://magicstack.github.io/asyncpg/) |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) (sync URL via `psycopg` in `alembic/env.py`) |
| Validation / settings | [Pydantic v2](https://docs.pydantic.dev/), [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Broker / cache (reserved) | [Redis](https://redis.io/) — wired in Compose; Celery/jobs in a later phase |

---

## Project layout

```text
backend/
├── app/
│   ├── main.py              # FastAPI app factory, /health
│   ├── config.py            # Settings from environment
│   ├── api/
│   │   ├── deps.py          # get_db (async session, commit on success)
│   │   └── v1/
│   │       ├── router.py    # Mounts v1 routes under /v1
│   │       ├── health.py
│   │       ├── capture.py   # POST /capture/person
│   │       ├── resolve.py   # POST /resolve/person
│   │       ├── contacts.py  # POST /find-email, /find-and-verify
│   │       ├── verify.py    # POST /verify-email
│   │       ├── people.py    # GET /people, GET /people/{id}
│   │       ├── companies.py # GET /companies, /companies/{id}, /companies/{id}/patterns
│   │       ├── domains.py   # GET /domains/{domain}/patterns
│   │       ├── lists.py     # Lists CRUD + entries
│   │       └── schemas.py   # Pydantic request/response models for v1
│   ├── db/
│   │   ├── engine.py        # Async engine + session factory
│   │   ├── models.py        # ORM models (PostgreSQL schema)
│   │   ├── repository.py    # Shared writes (employment upsert, observations)
│   │   └── queries.py       # List/filter/detail queries
│   └── core/
│       ├── schemas.py       # normalize_domain, infer_seniority, legacy DTOs
│       ├── resolvers/
│       │   ├── identity_resolver.py   # Person/company dedup for capture
│       │   └── domain_resolver.py     # Layered company email domain resolution
│       ├── patterns/      # generator, scorer, learner (company_email_patterns)
│       ├── verifiers/       # base, own_api, hunter, millionverifier, factory, service
│       ├── ranking/
│       │   └── contact_ranker.py      # Post-verify scores + best pick
│       ├── contact_intel.py           # resolve / find-email / find-and-verify orchestration
│       ├── scrapers/        # Ported from CLI (YC, Product Hunt, team pages)
│       └── enrichers/       # Apollo, Hunter (ported)
├── alembic/                 # env.py + versions/
├── scripts/
│   └── migrate_sqlite.py    # One-off SQLite → Postgres import
├── Dockerfile
└── pyproject.toml
```

The HTTP entrypoint is `app.main:app`. All versioned JSON APIs live under **`/api/v1`**.

---

## Configuration

Settings load from the environment and optional **`.env`** in the **current working directory** when the process starts (see `Settings` in `app/config.py`).

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://sdr:sdr@localhost:5433/sdr` |
| `REDIS_URL` | Redis URL (future jobs/cache) |
| `VERIFIER_PROVIDER` | `own_api` (default), `hunter`, or `millionverifier` — drives `/verify-email` and `/find-and-verify` |
| `OWN_VERIFIER_URL`, `OWN_VERIFIER_API_KEY` | Optional custom verifier: `POST` JSON `{"email":"..."}`; if URL unset, `own_api` returns `unknown` |
| `MILLIONVERIFIER_API_KEY` | [MillionVerifier](https://developer.millionverifier.com/) single-check API when provider is `millionverifier` |
| `HUNTER_API_KEY` | [Hunter](https://hunter.io/api-documentation) email verifier when provider is `hunter` |
| `APOLLO_API_KEY`, `PRODUCT_HUNT_ACCESS_TOKEN`, `SDR_YC_REQUEST_DELAY`, `SDR_USER_AGENT` | Used by ported scrapers/enrichers when invoked from the backend |
| `SDR_DB_PATH` | Default SQLite path for `scripts/migrate_sqlite.py` |

**Compose note:** Postgres is exposed on host port **5433** (`docker-compose.yml`). Inside the Docker network the backend uses `postgres:5432`.

Authoritative list of names: **`.env.example`** at the repo root.

---

## Run the API

### Docker Compose (recommended)

From the repo root:

```bash
docker compose up -d
```

The backend image runs **`alembic upgrade head`** before Uvicorn starts.

- API base: `http://127.0.0.1:8000`
- Liveness: `GET /health` → `{"status":"ok"}`

### Local (without rebuilding the image)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+asyncpg://sdr:sdr@localhost:5433/sdr   # match your Postgres
alembic upgrade head
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Database and migrations

- **Schema:** ORM definitions in `app/db/models.py` (companies, people, employments, contact_candidates, verification_events, company_email_patterns, source_observations, domain_resolution_cache, lists, list_entries, jobs).
- **Migrations:** `backend/alembic/versions/`. Apply with:

```bash
cd backend
alembic upgrade head
```

Generate new revisions after model changes (from `backend/` with `DATABASE_URL` set):

```bash
alembic revision --autogenerate -m "describe change"
```

Review autogenerated SQL before applying in production.

---

## SQLite → PostgreSQL migration

If you have a legacy **`sdr.db`** from the CLI:

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://sdr:sdr@localhost:5433/sdr
export PYTHONPATH=.
python scripts/migrate_sqlite.py --sqlite ../sdr.db
```

The script maps integer IDs to stable UUIDs and is idempotent for typical re-runs. Details are in the root README.

---

## HTTP API (v1)

Base path: **`/api/v1`**.

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | JSON `{"status":"ok"}` |

There is also **`GET /health`** on the app root (same payload).

### Capture

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/capture/person` | Upsert company, person, employment, and append a `source_observations` row |

**Request body** (JSON):

- **`person`** — `full_name` (required), optional `first_name`, `last_name`, `linkedin_url`, `headline`, `location`, `raw_data`.
- **`company`** — `name` (required), optional `primary_domain`, `website`, `linkedin_url`, `industry`, `location`, `team_size`, `founded_year`.
- **`employment`** — optional `title`, `department`, `is_current` (default `true`).
- **`source`** — `source_type` (required), optional `source_url`, `payload` (object, default `{}`).

**Response:** `person_id`, `company_id`, `employment_id`, `source_observation_id`, `person_created`, `company_created`.

### People

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/people` | Paginated list with optional filters |
| GET | `/api/v1/people/{person_id}` | Full person detail |

**Query parameters** (`GET /people`):

| Parameter | Description |
|-----------|-------------|
| `limit` | Page size (default `50`, max `100`) |
| `offset` | Offset (default `0`) |
| `name` | `ILIKE` filter on `people.full_name` |
| `title` | `ILIKE` on current/relevant `employments.title` |
| `seniority` | Exact match on `employments.seniority` |
| `company` | `ILIKE` on `companies.name` (joins employments) |

**Person detail** includes: person fields, **employments** (with company summary), **contact_candidates**, and **source_observations** for that person.

### Companies

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/companies` | Paginated list with optional filters |
| GET | `/api/v1/companies/{company_id}` | Company detail |

**Query parameters** (`GET /companies`):

| Parameter | Description |
|-----------|-------------|
| `limit` | Page size (default `50`, max `100`) |
| `offset` | Offset |
| `name` | `ILIKE` on `companies.name` |
| `domain` | `ILIKE` on `primary_domain` |
| `industry` | `ILIKE` on `industry` |

**Company detail** includes linked **people** (distinct via employments) and **company_email_patterns**.

### Lists

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/lists` | Create a list (`name`, optional `description`) |
| GET | `/api/v1/lists` | All lists with `entry_count` |
| POST | `/api/v1/lists/{list_id}/entries` | Add a person; body `{"person_id":"<uuid>"}` — idempotent if already present |
| DELETE | `/api/v1/lists/{list_id}/entries/{person_id}` | Remove person from list (404 if entry missing) |

### Resolve (domain)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/resolve/person` | Resolve a **work email domain** for the person’s current (or specified) employment’s company |

**Request body (JSON):**

| Field | Description |
|-------|-------------|
| `person_id` | Required UUID |
| `employment_id` | Optional; default = current employment (highest `title_rank`, prefer `is_current`) |
| `persist` | Default `true` — writes `companies.primary_domain`, `domain_confidence`, `domain_source`, `needs_domain_review`, and upserts `domain_resolution_cache` when a domain is found |

**Response:** `person_id`, `employment_id`, `company_id`, `domain` (nullable), `confidence`, `source`, `needs_review`.

Resolution order is the same as in [Domain resolution](#domain-resolution).

### Contacts (find email, find and verify)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/find-email` | Resolve domain (unless already known), generate **10+** local-part patterns from the person’s name, **pre-score** using `company_email_patterns`, **upsert** `contact_candidates` (`generation_source=pattern_engine`), set preliminary `final_score` |
| POST | `/api/v1/find-and-verify` | Same as find-email, then **verify the top 7** candidates via the configured verifier, append `verification_events`, **re-rank** all candidates for that person+company, set `is_best_current`, update employment `best_candidate_id` / `best_candidate_status` / `best_candidate_score`, and **learn** patterns when status is `valid` |

**`POST /find-email` body:** `person_id`, optional `employment_id`, optional `persist_domain` (default `true`).

**`POST /find-and-verify` body:** same fields. Uses an internal HTTP client (60s timeout) for provider calls.

Errors such as missing employment or unresolved domain return **400** with a short `detail` message.

### Verify (single email)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/verify-email` | Call the active verifier for one address |

**Request body:** `email` (required). Optional **`person_id`** and **`company_id`**: if both are set, upserts a `contact_candidate` (`generation_source=manual`) and records a `verification_event`; if both are omitted, only the provider is called (no DB rows). If one of the two is set without the other → **400**.

**Response:** `email`, `status` (`valid` \| `catch_all` \| `invalid` \| `unknown` \| `pending`), `provider`, `confidence`, optional `candidate_id` / `verification_event_id`.

### Companies (patterns-only)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/companies/{company_id}/patterns` | Same pattern rows as embedded in company detail, sorted by confidence |

### Domains (patterns by domain)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/domains/{domain}/patterns` | All `company_email_patterns` where `domain` matches (normalized), sorted by confidence |

Use a normalized hostname (e.g. `example.com`); URL-encode if needed.

---

## Capture and identity resolution

Logic lives in `app/core/resolvers/identity_resolver.py` and the `POST /capture/person` handler.

1. **Company**
   - Match by normalized **`primary_domain`** / website when possible.
   - Else match by normalized company name; else a bounded fuzzy scan on recent companies.
   - On match, non-destructively merge missing fields; on miss, insert.

2. **Person**
   - If **`linkedin_url`** is present, normalize URL and match uniquely on `people.linkedin_url`.
   - Else fuzzy match **`full_name`** among people with an employment at the resolved company.
   - On match, merge fields; on miss, insert.

Employment **`seniority`**, **`is_c_suite`**, and **`title_rank`** are derived from the title using `infer_seniority()` / `is_c_suite_title()` in `app/core/schemas.py`. Each capture stores a **`source_observations`** row; the JSON **`payload`** includes a `capture` key with the submitted person/company/employment snapshot unless you override structure in `source.payload`.

---

## Domain resolution

Implemented in `app/core/resolvers/domain_resolver.py`. Used by **`POST /resolve/person`**, **`POST /find-email`**, and **`POST /find-and-verify`** (when `persist` / `persist_domain` is true, successful resolutions can update the company and cache).

1. **Company record** — If `companies.primary_domain` is set, use it (high default confidence unless `domain_confidence` is stored).
2. **Verified candidates** — Any `contact_candidates` for that company with `verification_state=valid` supplies a domain (~0.88 confidence).
3. **Domain resolution cache** — Row keyed by normalized company name (`domain_resolution_cache`).
4. **Website** — `companies.website` normalized to host (~0.82).
5. **Heuristic** — Strip common legal suffixes from the company name and guess `{slug}.com` (~0.38, **`needs_review`**).

Subjective thresholds: **`needs_review`** is set when confidence &lt; **0.70** or for heuristic hits. `persist_resolution` writes through to `companies` and upserts the cache row when a domain is chosen.

---

## Pattern engine, verification, and ranking

- **Generation** (`app/core/patterns/generator.py`) — From `full_name` + domain, emits multiple `pattern_code` variants (e.g. `first.last`, `flast`, `first`, …), deduped by local part.
- **Pre-verify scoring** (`scorer.py`) — Boosts patterns that appear in `company_email_patterns` for that company (confidence as weight; default ~0.35 for unknown patterns).
- **Verification** (`app/core/verifiers/`) — `VerifierProtocol`: `verify`, `verify_batch`, `healthcheck`. Factory reads `VERIFIER_PROVIDER` from settings. Each check appends **`verification_events`** and updates the candidate’s `verification_state`, `latest_verified_at`, `deliverability_risk`.
- **Post-verify ranking** (`app/core/ranking/contact_ranker.py`) — Combines status weights (`valid` &gt; `catch_all` &gt; `unknown` &gt; `pending` &gt; `invalid`), verifier confidence, pattern confidence, domain confidence, and a small C-suite boost. **`pick_best`** chooses the employment’s best candidate even when the best status is catch-all or unknown.
- **Learning** (`app/core/patterns/learner.py`) — On **`valid`**, increments evidence and raises confidence for that company’s `pattern_code` (creates row if missing).

Orchestration lives in **`app/core/contact_intel.py`** (`resolve_person_workflow`, `find_email_workflow`, `find_and_verify_workflow`).

---

## OpenAPI / interactive docs

With the server running:

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON:** `http://127.0.0.1:8000/openapi.json`

Use these for exact schema fields and trying requests.

---

## Development notes

- **Sessions:** `get_db` in `app/api/deps.py` yields an `AsyncSession`, commits on successful request completion, and rolls back on exceptions.
- **Tests:** CLI tests live under the repo root `tests/`. Backend unit tests (no DB) live under **`backend/tests/`** (e.g. pattern generator and ranker helpers). For integration tests against PostgreSQL, add `pytest-asyncio` and a dedicated `DATABASE_URL` fixture when needed.
- **Auth:** Intentionally none for the single-operator localhost phase (see PRD).

For changes to ports, env vars, or public API behavior, update this file and the root **`README.md`** “Maintaining this README” checklist.
