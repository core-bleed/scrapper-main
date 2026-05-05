# SDR Scraper & Outbound Platform

This repository contains two complementary pieces:

1. **Legacy CLI (`sdr`)** — A lean **SQLite**-backed tool that scrapes public startup directories and team pages, optionally enriches with [Apollo](https://www.apollo.io/) and [Hunter](https://hunter.io/), and exports CSV/XLSX. Designed for fast time-to-value: one database file and minimal moving parts.

2. **Backend (`backend/`)** — A **FastAPI** service with **PostgreSQL** (canonical lead graph), **Redis**, and **Alembic** migrations. It includes **domain resolution**, a **pattern-based email generator**, **pluggable verification** (own API stub, Hunter, MillionVerifier), **ranking**, and **pattern learning** from valid verifications. Operator UI and Chrome extension are planned; see `PLAN.md` / `PRD.md`.

---

## Table of contents

- [Repository layout](#repository-layout)
- [Backend (Docker + API)](#backend-docker--api)
- [Backend documentation](docs/BACKEND.md)
- [Legacy CLI (SQLite)](#legacy-cli-sqlite)
  - [What the CLI does](#what-the-cli-does)
  - [CLI features](#cli-features)
  - [Requirements](#requirements)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [CLI quick start](#cli-quick-start)
  - [CLI reference](#cli-reference)
  - [Data model](#data-model)
  - [Sources and behavior](#sources-and-behavior)
  - [Enrichment](#enrichment)
  - [Export format](#export-format)
  - [Typical workflows](#typical-workflows)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Legal and responsible use](#legal-and-responsible-use)
- [Maintaining this README](#maintaining-this-readme)

---

## Repository layout

```text
sdr_scraper/
├── docker-compose.yml      # Postgres (host :5433), Redis, backend API
├── .env.example            # Copy to .env — CLI + backend variables
├── pyproject.toml          # Root package: CLI (`sdr_cli` under src/)
├── README.md               # This file
├── docs/
│   └── BACKEND.md          # Backend API, layout, capture, migrations (detailed)
├── PRD.md / PLAN.md        # Product context and roadmap
├── backend/
│   ├── app/
│   │   ├── main.py         # FastAPI app
│   │   ├── config.py
│   │   ├── api/            # v1: health, capture, resolve, contacts, verify, people, companies, domains, lists
│   │   ├── db/             # SQLAlchemy models, engine, queries, repository
│   │   └── core/           # Schemas, resolvers, patterns, verifiers, ranking, contact_intel, scrapers, enrichers
│   ├── alembic/            # Migrations
│   ├── scripts/
│   │   └── migrate_sqlite.py
│   ├── tests/              # Backend pytest (e.g. pattern generator)
│   ├── Dockerfile
│   └── pyproject.toml
├── src/sdr_cli/            # Typer CLI + SQLite (`import sdr_cli`, command still `sdr`)
├── frontend/               # Placeholder (dashboard, later)
├── extension/              # Placeholder (Chrome extension, later)
└── tests/                  # CLI tests (pytest)
```

---

## Backend (Docker + API)

**Full backend guide:** [docs/BACKEND.md](docs/BACKEND.md) (stack, env vars, migrations, **API v1** reference, capture/dedup behavior, OpenAPI links).

### Stack

| Piece | Technology |
|-------|------------|
| API | FastAPI, Uvicorn |
| Database | PostgreSQL 16, SQLAlchemy 2 async, asyncpg |
| Migrations | Alembic (sync URL uses psycopg) |
| Cache / broker | Redis 7 (reserved for Celery/jobs later) |

### Run with Docker Compose

From the repo root:

```bash
docker compose up -d
```

- **API:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Health:** `GET /health` and `GET /api/v1/health` → `{"status":"ok"}`
- **Interactive docs:** [Swagger UI](http://127.0.0.1:8000/docs), [ReDoc](http://127.0.0.1:8000/redoc)

### API v1 (summary)

All JSON routes are under **`/api/v1`**. See [docs/BACKEND.md](docs/BACKEND.md) for parameters and bodies.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/capture/person` | Upsert person, company, employment + source observation |
| POST | `/api/v1/resolve/person` | Resolve company email domain (layered resolver; optional persist to company + cache) |
| POST | `/api/v1/find-email` | Generate pattern candidates, score with learned patterns, upsert `contact_candidates` (no external verify) |
| POST | `/api/v1/find-and-verify` | Find-email + verify top **7** + re-rank + set employment best candidate + pattern learning on **valid** |
| POST | `/api/v1/verify-email` | Verify one address via configured provider; optional `person_id` + `company_id` to store candidate + event |
| GET | `/api/v1/people` | Paginated people (filters: name, title, seniority, company) |
| GET | `/api/v1/people/{id}` | Person detail + employments, candidates, sources |
| GET | `/api/v1/companies` | Paginated companies (filters: name, domain, industry) |
| GET | `/api/v1/companies/{id}/patterns` | Email patterns for that company only |
| GET | `/api/v1/companies/{id}` | Company + people + email patterns |
| GET | `/api/v1/domains/{domain}/patterns` | All learned patterns rows for a domain (any company) |
| POST | `/api/v1/lists` | Create list |
| GET | `/api/v1/lists` | Lists with entry counts |
| POST | `/api/v1/lists/{id}/entries` | Add person to list |
| DELETE | `/api/v1/lists/{id}/entries/{person_id}` | Remove person from list |

- **Postgres** is published on host port **5433** (not `5432`) so it does not conflict with a local PostgreSQL install.
- Inside the Docker network, the backend uses `postgres:5432` via `DATABASE_URL`.

The backend image runs **`alembic upgrade head`** before starting Uvicorn, so tables are created on first boot.

### Environment variables (backend)

See **`.env.example`**. When running tools on the **host** against Compose Postgres, point at port **5433**:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | e.g. `postgresql+asyncpg://sdr:sdr@localhost:5433/sdr` |
| `REDIS_URL` | e.g. `redis://localhost:6379/0` |
| `VERIFIER_PROVIDER` | `own_api` (default), `hunter`, or `millionverifier` — see **`.env.example`** |
| `OWN_VERIFIER_URL`, `OWN_VERIFIER_API_KEY` | Custom verifier HTTP POST (`{"email":...}`); stub returns `unknown` if URL unset |
| `MILLIONVERIFIER_API_KEY`, `HUNTER_API_KEY` | Used when `VERIFIER_PROVIDER` matches; Hunter key also used by CLI enrich/verify |

### Migrate legacy SQLite → PostgreSQL

If you have an existing **`sdr.db`** from the CLI:

```bash
cd backend
export DATABASE_URL=postgresql+asyncpg://sdr:sdr@localhost:5433/sdr   # adjust if needed
export PYTHONPATH=.
python scripts/migrate_sqlite.py --sqlite ../sdr.db
```

The script maps SQLite integer IDs to stable UUIDs, creates **companies**, **people**, **employments**, and turns `work_email` rows into **contact_candidates**. Re-runs skip rows that already exist (idempotent for typical use).

### Local backend without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .
# Ensure PostgreSQL is running and DATABASE_URL is set
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Legacy CLI (SQLite)

### What the CLI does

1. **Discovers companies** from Y Combinator and Product Hunt.
2. **Extracts people** (names, titles, LinkedIn / X) from source pages or generic team/about URLs.
3. **Stores everything in SQLite** with deduplication by domain and LinkedIn URL (and by company + name when LinkedIn is missing).
4. **Optionally finds work emails** via Apollo or Hunter when the company has a domain.
5. **Exports** CSV or XLSX with company + person + best-known work email.

The design goal is **fast time-to-value**: one database file, no Postgres required for the CLI path.

### CLI features

| Area | Details |
|------|---------|
| **Storage** | SQLite with WAL, foreign keys, `companies`, `people`, `contact_methods` |
| **HTTP** | [httpx](https://www.python-httpx.org/) with configurable `User-Agent` and delays |
| **Parsing** | [Beautiful Soup 4](https://www.crummy.com/software/BeautifulSoup/) |
| **Models** | [Pydantic v2](https://docs.pydantic.dev/) (`src/sdr_cli/models.py`) |
| **CLI** | [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) |
| **Export** | CSV and XLSX ([openpyxl](https://openpyxl.readthedocs.io/)) |

---

## Requirements

- **Python 3.11+** for the CLI and backend
- Network access for scraping and API calls
- **Docker** (optional) for Postgres + Redis + API via Compose
- Optional API keys: Product Hunt, Apollo, Hunter (see [Configuration](#configuration))

---

## Installation

### CLI (repo root)

```bash
cd sdr_scraper
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
sdr --help
```

The installable Python package is **`sdr_cli`** (`import sdr_cli`); the Typer entry point remains the **`sdr`** shell command. After pulling renames, run `pip install -e .` again so the `sdr` script points at `sdr_cli.cli:app`.

### Backend only

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

---

## Configuration

Environment variables load from **`.env`** in the working directory ([pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) / [python-dotenv](https://github.com/theskumar/python-dotenv)).

```bash
cp .env.example .env
```

### CLI (SQLite)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SDR_DB_PATH` | No | `./sdr.db` | SQLite database path (parents created if needed). |
| `APOLLO_API_KEY` | For Apollo enrich | — | Apollo API key. |
| `HUNTER_API_KEY` | For Hunter enrich/verify | — | Hunter API key. |
| `PRODUCT_HUNT_ACCESS_TOKEN` | For `scrape producthunt` | — | Product Hunt API v2 OAuth token. |
| `SDR_YC_REQUEST_DELAY` | No | `0.5` | Delay (seconds) between YC-related requests. |
| `SDR_USER_AGENT` | No | `Mozilla/5.0 (compatible; SDR-Scraper/0.1)` | Outbound `User-Agent`. |

### Backend (PostgreSQL / Redis)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://sdr:sdr@localhost:5433/sdr` |
| `REDIS_URL` | Redis URL for future jobs/cache |
| `VERIFIER_PROVIDER`, `OWN_VERIFIER_*`, `MILLIONVERIFIER_API_KEY`, `HUNTER_API_KEY` | Email verification for `/verify-email` and `/find-and-verify` (see `.env.example`) |

> Scraping YC does **not** require API keys. Only variables used by the command you run need to be set.

---

## CLI quick start

```bash
# 1. Ingest YC companies + founders (no API key)
sdr scrape yc --limit 50

# 2. Inspect counts and coverage
sdr status

# 3. Export everything to CSV
sdr export --format csv -o leads.csv

# 4. Export only rows that have a LinkedIn URL
sdr export --format csv -o with_li.csv --has-linkedin
```

---

## CLI reference

Global pattern: `sdr <command> [options]`. Subcommands under `scrape`: `sdr scrape <source> [options]`.

### `sdr scrape yc`

Fetches companies from the public YC JSON API (`https://api.ycombinator.com/v0.1/companies`), then loads each company’s directory page and parses the **Active Founders** section for names, titles, LinkedIn, and X links.

| Option | Short | Description |
|--------|-------|-------------|
| `--limit` | `-n` | Maximum number of companies to process (default: `50`). |
| `--batch` | `-b` | Optional filter: batch label (e.g. `W24`, `S24`), case-insensitive. |

```bash
sdr scrape yc --limit 200 --batch W24
```

### `sdr scrape producthunt`

Product Hunt **GraphQL** API; requires `PRODUCT_HUNT_ACCESS_TOKEN`.

| Option | Short | Description |
|--------|-------|-------------|
| `--days` | `-d` | Posts after *now − days* (default: `30`). |
| `--limit` | `-n` | Cap on posts (default: `50`, max 50 per API request). |

```bash
sdr scrape producthunt --days 7 --limit 30
```

### `sdr scrape team-pages`

For up to `--limit` companies **in the database** with a non-empty `domain`, tries `/team`, `/about`, `/about-us`, `/company`, `/people`, `/leadership` and extracts people from LinkedIn links and JSON-LD `Person` blocks.

| Option | Short | Description |
|--------|-------|-------------|
| `--limit` | `-n` | Max companies to try (default: `50`). |
| `--delay` | — | Seconds between HTTP attempts (default: `0.5`). |

```bash
sdr scrape team-pages --limit 100 --delay 0.75
```

### `sdr export`

Joined view: companies + people + latest `work_email` from `contact_methods`.

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output path (default: `export.csv`). |
| `--format` | `-f` | `csv` or `xlsx`. |
| `--has-linkedin` | — | Only rows with LinkedIn URL. |
| `--has-email` | — | Only rows with `work_email`. |
| `--source` | — | Person or company `source` (e.g. `yc`). |

### `sdr status`

Aggregate counts, LinkedIn %, email %, and per-source breakdowns.

### `sdr enrich`

People without `work_email` whose company has a **domain**; up to `--limit` rows.

| Option | Short | Description |
|--------|-------|-------------|
| `--provider` | `-p` | `apollo` or `hunter` (required). |
| `--limit` | `-n` | Max people (default: `100`). |

### `sdr verify`

Hunter email verifier on Hunter-sourced work emails.

| Option | Short | Description |
|--------|-------|-------------|
| `--provider` | `-p` | `hunter` (default). |
| `--limit` | `-n` | Max rows (default: `50`). |

### `sdr search`

Rich table preview with filters.

| Option | Short | Description |
|--------|-------|-------------|
| `--seniority` | — | e.g. `founder`, `c_suite`, `vp`, `director`, `head`. |
| `--has-linkedin` | — | Require LinkedIn. |
| `--has-email` | — | Require `work_email`. |
| `--source` | — | Person or company source. |
| `--limit` | `-n` | Max rows (default: `50`). |

### Shell completion

```bash
sdr --install-completion
```

---

## Data model

### SQLite (CLI)

- **`companies`** — `domain` unique when present.
- **`people`** — `company_id`; `linkedin_url` unique when set; `UNIQUE(company_id, full_name)` when LinkedIn absent.
- **`contact_methods`** — `UNIQUE(person_id, method_type, value)`; typical `method_type`: `work_email`.

Pydantic models: `src/sdr_cli/models.py`. Persistence: `src/sdr_cli/db.py` (raw SQL, no ORM).

### PostgreSQL (backend)

Canonical schema in **`backend/app/db/models.py`**, including: `companies`, `people`, `employments`, `contact_candidates`, `verification_events`, `company_email_patterns`, `source_observations`, `domain_resolution_cache`, `lists`, `list_entries`, `jobs`. Migrations live under **`backend/alembic/versions/`**.

**Intelligence (backend):** `contact_candidates` hold generated emails and verification state; `verification_events` append-only provider results; `company_email_patterns` gain confidence when a candidate verifies **valid**. Domain resolution order is documented in **`docs/BACKEND.md`**.

Scraper/enricher logic used by the backend lives under **`backend/app/core/`** (ported from `sdr_cli`); the CLI package is **`src/sdr_cli`**.

---

## Sources and behavior

### Y Combinator (`source=yc`)

1. **API:** Paginated JSON from `api.ycombinator.com` (no auth). Optional **`--batch`** filters in memory.
2. **HTML:** **Active Founders** block; markup can change—see `tests/test_yc.py`.

### Product Hunt (`source=producthunt`)

Official **GraphQL** API with bearer token. Makers often lack LinkedIn; enrichment helps.

### Team pages (`source=team_page`)

Best-effort crawl of common paths. Respect site terms and robots in production; this tool does not implement a robots parser.

---

## Enrichment

### Apollo (`--provider apollo`)

- `POST https://api.apollo.io/api/v1/people/match` with **`X-Api-Key`**.
- See [Apollo docs](https://docs.apollo.io/).

### Hunter (`--provider hunter`)

- Finder: `GET https://api.hunter.io/v2/email-finder`
- Verifier: `GET https://api.hunter.io/v2/email-verifier` (`sdr verify`)

See [Hunter API](https://hunter.io/api-documentation).

---

## Export format

CSV / XLSX columns:

| Column | Description |
|--------|-------------|
| `company_name` | Display name |
| `company_domain` | Normalized domain |
| `company_batch` | e.g. YC batch |
| `company_source` | `yc`, `producthunt`, `team_page`, … |
| `person_name` | Full name |
| `title` | Job title |
| `seniority` | Inferred bucket |
| `linkedin_url` | Profile URL |
| `twitter_url` | X/Twitter URL |
| `work_email` | Latest work email |
| `email_status` | Status on contact method |

XLSX: bold headers, frozen row, heuristic column widths.

---

## Typical workflows

### Cold start (YC only)

```bash
sdr scrape yc --limit 100
sdr status
sdr export -o yc_leads.csv --format csv
```

### Product Hunt

```bash
sdr scrape producthunt --days 14 --limit 40
sdr status
```

### Enrich then export

```bash
sdr enrich --provider apollo --limit 150
sdr export -o enriched.xlsx --format xlsx --has-email --has-linkedin
```

### YC + team pages

```bash
sdr scrape yc --limit 50
sdr scrape team-pages --limit 50
sdr search --has-linkedin --limit 30
```

---

## Development

### CLI tests (repo root)

```bash
pip install -e ".[dev]"
pytest -v
pytest --cov=sdr_cli --cov-report=term-missing
```

### Backend

```bash
cd backend && pip install -e ".[dev]"
pytest tests/ -v                    # optional: pattern generator / ranker smoke tests
# Run API with reload (Postgres required)
PYTHONPATH=. uvicorn app.main:app --reload
```

Keep **[docs/BACKEND.md](docs/BACKEND.md)** in sync with new routes and behavior; then skim this README’s [Backend](#backend-docker--api) summary and [Maintaining this README](#maintaining-this-readme).

---

## Troubleshooting

| Symptom | Things to check |
|---------|------------------|
| **Port 5433 / Postgres** | Compose maps Postgres to **5433** on the host. Use `localhost:5433` in `DATABASE_URL` for host-side tools. |
| **Backend won’t start** | `docker compose logs backend`; ensure Postgres healthcheck passed; Alembic errors usually mean DB unreachable. |
| `Set PRODUCT_HUNT_ACCESS_TOKEN` | Valid PH v2 token in `.env`. |
| `Set APOLLO_API_KEY` / `HUNTER_API_KEY` | Required for CLI `enrich` / `verify`; backend verification uses `VERIFIER_PROVIDER` + keys (see `.env.example`). |
| YC founder count low | YC HTML changed; run `pytest tests/test_yc.py`; increase `SDR_YC_REQUEST_DELAY`. |
| `scrape producthunt` errors | Token, GraphQL schema, rate limits. |
| Team pages empty | Blocking, JS-only sites, or unusual URLs. |
| Duplicate people | Dedup by LinkedIn or `(company_id, full_name)`; name variants = separate rows. |
| SQLite database locked | Close other users of `SDR_DB_PATH`; WAL reduces contention. |

---

## Legal and responsible use

- Respect **terms of service**, **robots.txt**, and **applicable law**. Intended for **public** data and **compliant** outreach.
- Do not use for spam or non-consented contact where required; seek counsel for regulated contexts.
- Use a truthful **`SDR_USER_AGENT`** and reasonable delays.
- **Never commit `.env`** (it is gitignored).

---

## Maintaining this README

When you change the project, keep this file aligned so newcomers and your future self do not have to read the codebase.

| Change | Update in README |
|--------|-------------------|
| New Compose service or port | [Backend](#backend-docker--api), [Troubleshooting](#troubleshooting), `.env.example` |
| New env var | [Configuration](#configuration) tables and `.env.example` |
| New CLI command or option | [CLI reference](#cli-reference) |
| Rename/move CLI package under `src/` | [Repository layout](#repository-layout), `pyproject.toml` `[project.scripts]`, tests’ `import` lines, this README |
| New PostgreSQL table or major API area | [Data model](#data-model), [docs/BACKEND.md](docs/BACKEND.md), backend section |
| New or changed HTTP API | [docs/BACKEND.md](docs/BACKEND.md), [API v1 summary](#api-v1-summary) |
| Domain / patterns / verification behavior | [docs/BACKEND.md](docs/BACKEND.md) (detailed); keep README summary table accurate |
| New migration workflow | [Backend](#backend-docker--api), [docs/BACKEND.md](docs/BACKEND.md) |
| User-facing scripts | [Repository layout](#repository-layout) and the command snippet |

**Single source of truth:** `.env.example` lists variable names; this README explains behavior. Avoid duplicating long prose in multiple docs—link to `PRD.md` / `PLAN.md` for roadmap.

---

## License and support

Project metadata: root `pyproject.toml` (CLI) and `backend/pyproject.toml` (backend). Product goals: `PRD.md`, `PLAN.md`. Third-party API issues: those providers’ support channels.
