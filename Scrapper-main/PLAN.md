# SDR Research Engine — V2 Implementation Plan

## Overview

A Python CLI research tool that discovers companies and important people, prioritizes `linkedin_url` as the primary identity key, enriches work emails selectively, stores provenance-rich data in PostgreSQL, and exports filtered research lists as CSV/Excel.

This V2 plan replaces the original email-first approach with a provider-agnostic pipeline that supports both scraped and paid data sources. The goal is to support more than `1000` new contacts per month while keeping paid tooling below `$200/month`.

---

## Product Constraints

- Primary use case: research, not outbound sequencing
- Target volume: `1000+` new contacts per month
- Highest-priority field: `linkedin_url`
- Budget target: less than `$200/month`
- Must support pluggable data sources without schema changes
- Must not depend on direct LinkedIn scraping
- YC and Product Hunt are good seed sources, but not sufficient alone for long-term volume

---

## Success Metrics

- `1000+` new contact records stored per month
- `60%+` of new contacts include `linkedin_url`
- `40%+` of new contacts include a work email or verified company email pattern
- Average paid-data cost stays below `$0.20` per new stored contact
- A new source can be added by implementing a connector and updating config, without changing the database schema

---

## Core Design Decisions

1. `linkedin_url` is the primary person identity key. Email is a secondary contact method.
2. Use capability-based connectors instead of source-specific tables.
3. Separate discovery, enrichment, and verification into distinct pipeline stages.
4. Store provenance, timestamps, and confidence for every fact.
5. Spend money only after free discovery and deduplication have already run.
6. Keep provider order, budgets, and rate limits config-driven.
7. Store source-specific data in generic `observations` records instead of creating one table per provider.

---

## Recommended Launch Stack

| Layer | Default Choice | Why |
|-------|----------------|-----|
| Company seeds | `yc_api`, `producthunt_api`, `website_seed` | Low-cost, structured, easy to normalize |
| Free person discovery | `yc_company_page`, `producthunt_makers`, `team_page` | Extract names, titles, and public links before paying |
| LinkedIn resolution | `proxycurl` as optional fallback | Only use when free sources miss `linkedin_url` |
| Email lookup + verification | `hunter` | Strongest fit for `name + domain -> work email -> verification` |
| Storage | PostgreSQL | Good fit for dedup, provenance, and exportable search |
| Export | CSV + XLSX | Researcher-friendly output |

### Recommended Budget Bundles

| Bundle | Estimated Monthly Cost | Strength | Weakness | Recommendation |
|--------|------------------------|----------|----------|----------------|
| Free sources + Hunter Starter | `$49` | Cheapest path to prove workflow | Thin credit headroom for `1000+` contacts; weak fallback for missing LinkedIn | Only if free sources already give most LinkedIn URLs |
| Free sources + Hunter Growth | `$149` | Good email throughput for `1000+` contacts | LinkedIn coverage still depends on free discovery | Good default starting point |
| Free sources + Hunter Growth + Proxycurl Starter | `$198` | Best balance of scale + LinkedIn-first coverage under budget | Must gate Proxycurl usage carefully | Recommended ceiling bundle |
| Free sources + PDL Pro + Hunter Starter | `$147` starting | Strong API/data-platform direction | Entry-tier volume is not a clear fit for `1000+` monthly contacts | Not the default launch stack |
| Apollo-based workflow | Pricing/access to confirm | Strong people-search workflow if available | API/export terms and automation fit must be confirmed before committing | Build adapter support, decide later |

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Rich scraping/data ecosystem |
| CLI | Typer + Rich | Clean command surface for researchers |
| HTTP | httpx | Good sync/async support |
| HTML parsing | BeautifulSoup or selectolax | Team/about/contact page scraping |
| Browser fallback | Playwright (optional) | For JS-rendered company pages |
| Data models | Pydantic v2 | Validation and normalized schemas |
| Database | SQLAlchemy 2.0 + asyncpg | ORM plus solid Postgres support |
| Migrations | Alembic | Schema versioning |
| Dedup | RapidFuzz | Fast fuzzy matching for name fallback |
| Retry/rate limiting | tenacity + custom limiter | Provider reliability and quota control |
| Export | stdlib csv + xlsxwriter | CSV + Excel output |
| Config | pydantic-settings + YAML | Env vars for secrets, YAML for provider policy |
| Testing | pytest + pytest-asyncio + pytest-cov | Standard stack |
| Linting | ruff | Fast formatting/linting |
| Type check | mypy | Catch provider/model mismatches |
| Build | hatchling | Modern packaging |

---

## High-Level Architecture

The system should be organized around capabilities, not vendors.

### Pipeline Stages

1. Company discovery
2. Company normalization + deduplication
3. Target-role selection
4. Person discovery
5. LinkedIn/public-profile resolution
6. Contact enrichment
7. Email verification
8. Search + export

### Data Flow

```text
Company source -> Normalize company -> Dedup company -> Discover people
    -> Resolve linkedin_url -> Enrich work email -> Verify selected emails
    -> Search / export / review
```

### Capability Interfaces

- `CompanySource`: returns normalized company candidates
- `PersonSource`: takes a company and returns person candidates
- `ProfileResolver`: fills `linkedin_url` or other public profile URLs
- `ContactEnricher`: adds emails or generic company contact methods
- `Verifier`: verifies a contact method
- `CostAwareProvider`: exposes pricing, rate limits, and budget metadata

This keeps the code open to:

- scraped sources like YC pages, team pages, blog pages, sitemap pages
- paid sources like Proxycurl, Apollo, People Data Labs, Hunter
- future manual imports like CSV uploads or API payload replays

---

## Project Structure

```text
sdr_scraper/
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── PLAN.md
├── PRD.md
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── src/
│   └── sdr_cli/
│       ├── __init__.py
│       ├── config.py
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── sources.py
│       │   ├── sync.py
│       │   ├── discover.py
│       │   ├── resolve.py
│       │   ├── enrich.py
│       │   ├── verify.py
│       │   ├── search.py
│       │   ├── export.py
│       │   └── status.py
│       ├── connectors/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── company/
│       │   │   ├── __init__.py
│       │   │   ├── yc_api.py
│       │   │   ├── producthunt_api.py
│       │   │   └── website_seed.py
│       │   ├── person/
│       │   │   ├── __init__.py
│       │   │   ├── yc_company_page.py
│       │   │   ├── producthunt_makers.py
│       │   │   └── team_page.py
│       │   ├── resolver/
│       │   │   ├── __init__.py
│       │   │   ├── company_socials.py
│       │   │   ├── proxycurl.py
│       │   │   ├── apollo.py
│       │   │   └── pdl.py
│       │   ├── contact/
│       │   │   ├── __init__.py
│       │   │   └── hunter.py
│       │   └── verifier/
│       │       ├── __init__.py
│       │       └── hunter.py
│       ├── pipelines/
│       │   ├── __init__.py
│       │   ├── company_sync.py
│       │   ├── person_discovery.py
│       │   ├── linkedin_resolution.py
│       │   ├── email_enrichment.py
│       │   ├── email_verification.py
│       │   └── export_pipeline.py
│       ├── policies/
│       │   ├── __init__.py
│       │   ├── budget.py
│       │   ├── targeting.py
│       │   └── waterfall.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── models.py
│       │   └── repository.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── company.py
│       │   ├── person.py
│       │   ├── employment.py
│       │   ├── contact_method.py
│       │   └── observation.py
│       └── utils/
│           ├── __init__.py
│           ├── domains.py
│           ├── html.py
│           ├── rate_limit.py
│           └── metrics.py
└── tests/
    ├── test_cli/
    ├── test_connectors/
    ├── test_pipelines/
    ├── test_db/
    └── conftest.py
```

---

## Database Schema

The schema should model core entities, not vendors.

### Table: `companies`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | VARCHAR(500) | NOT NULL |
| normalized_name | VARCHAR(500) | Lowercase, stripped |
| domain | VARCHAR(500) | Canonical domain, unique when present |
| website | VARCHAR(1000) | |
| description | TEXT | |
| industry | VARCHAR(200) | |
| location | VARCHAR(500) | |
| country | VARCHAR(100) | |
| team_size | INTEGER | |
| founded_year | INTEGER | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**Indexes**: `domain` unique, `normalized_name`, `industry`, `location`

### Table: `people`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| full_name | VARCHAR(500) | Display name |
| first_name | VARCHAR(200) | |
| last_name | VARCHAR(200) | |
| linkedin_url | VARCHAR(1000) | Primary identity key when known |
| public_profile_url | VARCHAR(1000) | Non-LinkedIn fallback |
| headline | VARCHAR(500) | Public profile headline |
| location | VARCHAR(500) | |
| is_key_person | BOOLEAN | Heuristic flag |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**Indexes**: `linkedin_url` unique when present, `full_name`

### Table: `employments`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| company_id | UUID | FK -> companies |
| person_id | UUID | FK -> people |
| title | VARCHAR(300) | Current or observed title |
| seniority | VARCHAR(100) | founder, c_suite, vp, head, director |
| department | VARCHAR(100) | sales, growth, product, engineering, etc. |
| is_current | BOOLEAN | Default true for current matching role |
| is_decision_maker | BOOLEAN | Derived by targeting policy |
| confidence_score | FLOAT | Match confidence |
| source_rank | INTEGER | Lower is better |
| created_at | TIMESTAMPTZ | |

**Indexes**: `company_id + person_id`, `title`, `is_decision_maker`

### Table: `contact_methods`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| person_id | UUID | FK -> people |
| method_type | VARCHAR(50) | work_email, generic_email, website, twitter, phone |
| value | VARCHAR(1000) | Raw value |
| normalized_value | VARCHAR(1000) | Lowercase / normalized |
| status | VARCHAR(50) | discovered, inferred, verified, invalid |
| provider | VARCHAR(100) | hunter, proxycurl, scraper, manual |
| confidence_score | FLOAT | Provider or heuristic confidence |
| is_primary | BOOLEAN | Best value for method type |
| verified_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

**Indexes**: `normalized_value` unique when appropriate, `method_type`, `status`

### Table: `observations`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| entity_type | VARCHAR(50) | company, person, employment, contact_method |
| entity_id | UUID | FK-like reference |
| provider | VARCHAR(100) | yc_api, producthunt_api, team_page, hunter, proxycurl |
| capability | VARCHAR(50) | company_source, person_source, resolver, enricher, verifier |
| source_record_id | VARCHAR(500) | Provider-side id if any |
| source_url | VARCHAR(1000) | Web page or API source URL |
| acquisition_method | VARCHAR(100) | api, html_scrape, manual_import |
| observed_at | TIMESTAMPTZ | When observed from source |
| cost_usd | NUMERIC(10, 4) | Estimated per-record spend |
| raw_payload | JSONB | Raw payload or extracted blob |
| parsed_payload | JSONB | Normalized subset for audit |

**Indexes**: `entity_type + entity_id`, `provider`, `observed_at`

### Table: `pipeline_runs`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| command | VARCHAR(200) | CLI command that triggered run |
| provider | VARCHAR(100) | Optional provider |
| status | VARCHAR(50) | running, success, failed |
| started_at | TIMESTAMPTZ | |
| finished_at | TIMESTAMPTZ | |
| input_count | INTEGER | |
| created_count | INTEGER | |
| updated_count | INTEGER | |
| skipped_count | INTEGER | |
| cost_usd | NUMERIC(10, 2) | Total run cost |
| notes | TEXT | |

**Indexes**: `started_at`, `provider`, `status`

---

## CLI Commands

```text
sdr sources list
sdr sync companies --source yc_api --limit 500
sdr sync companies --source producthunt_api --days 30
sdr discover people --provider yc_company_page --only-missing-people
sdr discover people --provider team_page --only-missing-linkedin
sdr resolve linkedin --provider proxycurl --only-missing-linkedin --limit 200
sdr enrich email --provider hunter --only-with-name-and-domain --limit 500
sdr verify email --provider hunter --status inferred --limit 250
sdr search --has-linkedin --title founder --company-source yc_api
sdr export --format xlsx --output leads.xlsx --has-linkedin
sdr status
sdr run pipeline monthly_research
```

### Why These Commands

- `sync companies` handles seed ingestion
- `discover people` extracts decision-makers from free sources first
- `resolve linkedin` is paid fallback only when needed
- `enrich email` and `verify email` stay separate so we can control spend
- `run pipeline` gives a config-driven monthly batch mode

---

## Config Design

All provider order, targeting, and budget decisions should live in config, not code.

```yaml
providers:
  company_sources:
    - name: yc_api
      enabled: true
    - name: producthunt_api
      enabled: true
    - name: website_seed
      enabled: false

  person_sources:
    - name: yc_company_page
      enabled: true
    - name: producthunt_makers
      enabled: true
    - name: team_page
      enabled: true

  resolvers:
    - name: proxycurl
      enabled: false
    - name: apollo
      enabled: false
    - name: pdl
      enabled: false

  contact_enrichers:
    - name: hunter_email_finder
      enabled: true
    - name: hunter_domain_search
      enabled: true

  verifiers:
    - name: hunter_verifier
      enabled: true

budget:
  monthly_usd_cap: 200
  max_cost_per_contact_usd: 0.20

policies:
  target_titles:
    - founder
    - co-founder
    - ceo
    - cto
    - coo
    - vp
    - head
    - director
  only_pay_for_missing_linkedin: true
  verify_only_export_candidates: true
  min_person_confidence: 0.65
  min_company_confidence: 0.70
```

---

## Build Phases

### Phase 1: Foundation and Provider Framework

**Files**: `pyproject.toml`, `.env.example`, `src/sdr_cli/config.py`, `src/sdr_cli/connectors/base.py`, `src/sdr_cli/connectors/registry.py`, `src/sdr_cli/db/engine.py`, `src/sdr_cli/db/models.py`, `src/sdr_cli/db/repository.py`, `alembic/*`, `src/sdr_cli/cli/app.py`, `src/sdr_cli/cli/status.py`

**What happens**:
1. Create the project scaffold and dependencies
2. Add base provider interfaces and registry
3. Create the six core tables
4. Add budget and targeting policy modules
5. Add a minimal CLI with `sources list` and `status`

**Test**:
- Migrations create all tables
- `sdr sources list` prints registered providers
- `sdr status` runs against an empty database

**User action needed**:
- Create a Postgres database
- Set `DATABASE_URL`

---

### Phase 2: Company Discovery Connectors

**Files**: `src/sdr_cli/connectors/company/yc_api.py`, `src/sdr_cli/connectors/company/producthunt_api.py`, `src/sdr_cli/connectors/company/website_seed.py`, `src/sdr_cli/pipelines/company_sync.py`, `src/sdr_cli/cli/sync.py`

**What happens**:
1. Implement `yc_api` for company seeds
2. Implement `producthunt_api` for company seeds
3. Add a generic `website_seed` connector for future scraped lists, RSS, or manual feeds
4. Normalize domains and deduplicate companies
5. Write provider observations for every inserted company

**Test**:
- Running the same sync twice does not duplicate companies
- Company source changes do not require schema changes
- Product Hunt companies and YC companies merge on domain when appropriate

**Notes**:
- Product Hunt should be treated as a seed source, not the long-term backbone for all monthly volume

---

### Phase 3: Free Person Discovery Connectors

**Files**: `src/sdr_cli/connectors/person/yc_company_page.py`, `src/sdr_cli/connectors/person/producthunt_makers.py`, `src/sdr_cli/connectors/person/team_page.py`, `src/sdr_cli/pipelines/person_discovery.py`, `src/sdr_cli/cli/discover.py`

**What happens**:
1. Parse YC company pages for founder names and titles
2. Pull Product Hunt makers when available
3. Crawl company `/team`, `/about`, `/company`, `/contact`, sitemap pages, and JSON-LD `sameAs` fields
4. Create `people`, `employments`, and `observations`
5. Flag likely decision-makers using deterministic title rules

**Test**:
- Founder pages create people records with title + source URL
- Team pages can add or improve titles without duplicating people
- `discover people --only-missing-people` skips already-covered companies

---

### Phase 4: Paid Profile Resolution Adapters

**Files**: `src/sdr_cli/connectors/resolver/proxycurl.py`, `src/sdr_cli/connectors/resolver/apollo.py`, `src/sdr_cli/connectors/resolver/pdl.py`, `src/sdr_cli/pipelines/linkedin_resolution.py`, `src/sdr_cli/cli/resolve.py`

**What happens**:
1. Implement provider adapters behind one `ProfileResolver` interface
2. Resolve missing `linkedin_url` only after free discovery has already run
3. Track per-record cost and provider yield
4. Support config-driven provider priority, budget caps, and rate limits

**Test**:
- Resolver runs only on records missing `linkedin_url`
- Budget policy can stop the run before monthly cap is exceeded
- Provider outputs map into shared tables with no schema drift

**User action needed**:
- Choose which paid provider(s) to enable
- Add API keys only for providers being used

---

### Phase 5: Email Enrichment and Verification

**Files**: `src/sdr_cli/connectors/contact/hunter.py`, `src/sdr_cli/connectors/verifier/hunter.py`, `src/sdr_cli/pipelines/email_enrichment.py`, `src/sdr_cli/pipelines/email_verification.py`, `src/sdr_cli/cli/enrich.py`, `src/sdr_cli/cli/verify.py`

**What happens**:
1. Use Hunter Email Finder when name + domain are known
2. Use Hunter Domain Search when company-level email evidence is stronger than person-level lookup
3. Store every email as a `contact_method`
4. Verify only shortlisted or export-ready contacts
5. Mark statuses as `discovered`, `inferred`, `verified`, or `invalid`

**Test**:
- Email enrichment does not run on people missing both name and company domain
- Verifier only touches configured statuses
- Email history remains auditable through `observations`

**Notes**:
- Hunter is the email layer, not the primary decision-maker discovery layer

---

### Phase 6: Search, Ranking, and Export

**Files**: `src/sdr_cli/cli/search.py`, `src/sdr_cli/cli/export.py`, `src/sdr_cli/pipelines/export_pipeline.py`

**What happens**:
1. Support filters like company source, title, location, has-linkedin, has-email, decision-maker flag
2. Rank results by confidence + source freshness + presence of `linkedin_url`
3. Export CSV/XLSX with both core data and provenance columns

**Test**:
- `sdr search --has-linkedin` returns people-level rows
- Exported files include company, person, title, LinkedIn, email, source provider, and confidence

---

### Phase 7: Ops, Metrics, and Documentation

**Files**: `README.md`, `CLAUDE.md`, `PRD.md`, `src/sdr_cli/utils/metrics.py`, policy docs

**What happens**:
1. Add provider yield dashboards in `status`
2. Track monthly spend and cost per stored contact
3. Add clear setup docs and sample configs
4. Document how to add a new connector

**Test**:
- `sdr status` shows record counts, source counts, verification counts, and estimated cost
- Documentation is enough for adding a new provider without touching the schema

---

## Targeting Rules

The default researcher target is "any important person," not just founders.

### Default High-Priority Titles

- Founder
- Co-founder
- CEO
- CTO
- COO
- VP
- Head of
- Director

### Decision-Maker Heuristic

Prioritize people who satisfy at least one:

- founder or co-founder title
- C-suite title
- VP / Head / Director in revenue, product, or engineering functions
- strongest public-profile evidence among all company contacts

---

## Accounts You Need to Create

| Service | Use | Estimated Cost | When |
|---------|-----|----------------|------|
| PostgreSQL | Storage | local/free | Phase 1 |
| Product Hunt | Seed company source | free, subject to API terms | Phase 2 |
| Hunter | Email lookup + verification | `$49` or `$149` | Phase 5 |
| Proxycurl | Optional LinkedIn fallback | `$49` starter | Phase 4 |
| People Data Labs | Optional future provider | `$98` starting | Phase 4 |
| Apollo | Optional future provider | confirm current pricing/access | Phase 4 |

---

## Risks and Anti-Patterns

- Do not make email the primary identity key
- Do not create one table per provider
- Do not pay for profile resolution before dedup + title filtering
- Do not depend on YC + Product Hunt alone to sustain `1000+` new contacts every month
- Do not let LLMs invent people, titles, or emails
- Do not skip provenance fields
- Do not scrape LinkedIn directly
- Do not ignore API terms, especially on sources like Product Hunt

---

## Key Design Decisions

1. **Capability-based connectors over source-specific tables**: the database models core entities once, and providers write observations into shared structures.
2. **`linkedin_url` over email as identity**: person-level identity should survive email changes and provider differences.
3. **Observations over provider-specific schema**: provider payloads go into `observations.raw_payload`, so new sources do not force migrations.
4. **Free discovery before paid enrichment**: use scraped/public data first, then spend only on unresolved, high-value records.
5. **Hunter as email layer, not people discovery**: Hunter is best used after we already know who the person is.
6. **Config-driven waterfall**: provider order, rate limits, and spend caps must be adjustable without code changes.

---

## Final Recommendation

For the first real version:

- Build the generalized connector architecture first
- Enable `yc_api`, `producthunt_api`, `yc_company_page`, and `team_page` immediately
- Use `hunter` as the core paid email layer
- Add `proxycurl` as a selective LinkedIn fallback only after measuring free-source coverage
- Track yield, confidence, and cost per provider from day one

The best practical launch path under the stated constraints is:

`free sources + Hunter Growth + optional Proxycurl Starter`

That keeps the system within the monthly budget ceiling while preserving room to add new scraped or paid sources later with minimal code churn.
