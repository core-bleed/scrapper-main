import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from sdr_cli.models import Company, ContactMethod, ExportRow, Person


def domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return None
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            domain TEXT UNIQUE,
            website TEXT,
            description TEXT,
            industry TEXT,
            location TEXT,
            team_size INTEGER,
            founded_year INTEGER,
            batch TEXT,
            source TEXT NOT NULL,
            source_url TEXT,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL REFERENCES companies(id),
            full_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            title TEXT,
            seniority TEXT,
            linkedin_url TEXT UNIQUE,
            twitter_url TEXT,
            headline TEXT,
            location TEXT,
            is_decision_maker INTEGER DEFAULT 0,
            source TEXT NOT NULL,
            source_url TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(company_id, full_name)
        );

        CREATE TABLE IF NOT EXISTS contact_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL REFERENCES people(id),
            method_type TEXT NOT NULL,
            value TEXT NOT NULL,
            status TEXT DEFAULT 'discovered',
            provider TEXT NOT NULL,
            confidence_score REAL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(person_id, method_type, value)
        );

        CREATE INDEX IF NOT EXISTS idx_people_company ON people(company_id);
        CREATE INDEX IF NOT EXISTS idx_contact_person ON contact_methods(person_id);
        """
    )
    conn.commit()


def upsert_company(conn: sqlite3.Connection, company: Company) -> int:
    c = company.model_copy()
    domain = c.domain
    cur = conn.cursor()
    if domain:
        cur.execute(
            """
            INSERT INTO companies (
                name, domain, website, description, industry, location,
                team_size, founded_year, batch, source, source_url, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(domain) DO UPDATE SET
                name = excluded.name,
                website = COALESCE(excluded.website, companies.website),
                description = COALESCE(excluded.description, companies.description),
                industry = COALESCE(excluded.industry, companies.industry),
                location = COALESCE(excluded.location, companies.location),
                team_size = COALESCE(excluded.team_size, companies.team_size),
                founded_year = COALESCE(excluded.founded_year, companies.founded_year),
                batch = COALESCE(excluded.batch, companies.batch),
                source = excluded.source,
                source_url = COALESCE(excluded.source_url, companies.source_url),
                tags = COALESCE(excluded.tags, companies.tags),
                updated_at = datetime('now')
            """,
            (
                c.name,
                domain,
                c.website,
                c.description,
                c.industry,
                c.location,
                c.team_size,
                c.founded_year,
                c.batch,
                c.source,
                c.source_url,
                c.tags,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO companies (
                name, domain, website, description, industry, location,
                team_size, founded_year, batch, source, source_url, tags
            ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                c.name,
                c.website,
                c.description,
                c.industry,
                c.location,
                c.team_size,
                c.founded_year,
                c.batch,
                c.source,
                c.source_url,
                c.tags,
            ),
        )
    conn.commit()
    if domain:
        row = cur.execute("SELECT id FROM companies WHERE domain = ?", (domain,)).fetchone()
    else:
        row = cur.execute("SELECT id FROM companies WHERE id = ?", (cur.lastrowid,)).fetchone()
    assert row is not None
    return int(row["id"])


def upsert_person(conn: sqlite3.Connection, person: Person) -> int:
    p = person.model_copy()
    cur = conn.cursor()
    linkedin = p.linkedin_url
    if linkedin:
        cur.execute(
            """
            INSERT INTO people (
                company_id, full_name, first_name, last_name, title, seniority,
                linkedin_url, twitter_url, headline, location, is_decision_maker,
                source, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(linkedin_url) DO UPDATE SET
                company_id = excluded.company_id,
                full_name = excluded.full_name,
                first_name = COALESCE(excluded.first_name, people.first_name),
                last_name = COALESCE(excluded.last_name, people.last_name),
                title = COALESCE(excluded.title, people.title),
                seniority = COALESCE(excluded.seniority, people.seniority),
                twitter_url = COALESCE(excluded.twitter_url, people.twitter_url),
                headline = COALESCE(excluded.headline, people.headline),
                location = COALESCE(excluded.location, people.location),
                is_decision_maker = CASE
                    WHEN excluded.is_decision_maker > people.is_decision_maker
                    THEN excluded.is_decision_maker ELSE people.is_decision_maker END,
                source = excluded.source,
                source_url = COALESCE(excluded.source_url, people.source_url),
                updated_at = datetime('now')
            """,
            (
                p.company_id,
                p.full_name,
                p.first_name,
                p.last_name,
                p.title,
                p.seniority,
                linkedin,
                p.twitter_url,
                p.headline,
                p.location,
                p.is_decision_maker,
                p.source,
                p.source_url,
            ),
        )
        conn.commit()
        row = cur.execute(
            "SELECT id FROM people WHERE linkedin_url = ?", (linkedin,)
        ).fetchone()
    else:
        cur.execute(
            """
            INSERT INTO people (
                company_id, full_name, first_name, last_name, title, seniority,
                linkedin_url, twitter_url, headline, location, is_decision_maker,
                source, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_id, full_name) DO UPDATE SET
                title = COALESCE(excluded.title, people.title),
                seniority = COALESCE(excluded.seniority, people.seniority),
                linkedin_url = COALESCE(excluded.linkedin_url, people.linkedin_url),
                twitter_url = COALESCE(excluded.twitter_url, people.twitter_url),
                headline = COALESCE(excluded.headline, people.headline),
                location = COALESCE(excluded.location, people.location),
                is_decision_maker = CASE
                    WHEN excluded.is_decision_maker > people.is_decision_maker
                    THEN excluded.is_decision_maker ELSE people.is_decision_maker END,
                source = excluded.source,
                source_url = COALESCE(excluded.source_url, people.source_url),
                updated_at = datetime('now')
            """,
            (
                p.company_id,
                p.full_name,
                p.first_name,
                p.last_name,
                p.title,
                p.seniority,
                p.twitter_url,
                p.headline,
                p.location,
                p.is_decision_maker,
                p.source,
                p.source_url,
            ),
        )
        conn.commit()
        row = cur.execute(
            "SELECT id FROM people WHERE company_id = ? AND full_name = ?",
            (p.company_id, p.full_name),
        ).fetchone()
    assert row is not None
    return int(row["id"])


def add_contact_method(conn: sqlite3.Connection, cm: ContactMethod) -> None:
    conn.execute(
        """
        INSERT INTO contact_methods (person_id, method_type, value, status, provider, confidence_score)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(person_id, method_type, value) DO UPDATE SET
            status = excluded.status,
            confidence_score = COALESCE(excluded.confidence_score, contact_methods.confidence_score)
        """,
        (
            cm.person_id,
            cm.method_type,
            cm.value,
            cm.status,
            cm.provider,
            cm.confidence_score,
        ),
    )
    conn.commit()


def get_companies(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    q = "SELECT * FROM companies ORDER BY id"
    if limit is not None:
        q += f" LIMIT {int(limit)}"
    return list(conn.execute(q))


def get_people(conn: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    q = "SELECT * FROM people ORDER BY id"
    if limit is not None:
        q += f" LIMIT {int(limit)}"
    return list(conn.execute(q))


def get_status_counts(conn: sqlite3.Connection) -> dict[str, int]:
    companies = conn.execute("SELECT COUNT(*) AS c FROM companies").fetchone()["c"]
    people = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
    contacts = conn.execute("SELECT COUNT(*) AS c FROM contact_methods").fetchone()["c"]
    with_li = conn.execute(
        "SELECT COUNT(*) AS c FROM people WHERE linkedin_url IS NOT NULL AND linkedin_url != ''"
    ).fetchone()["c"]
    with_email = conn.execute(
        """
        SELECT COUNT(DISTINCT person_id) AS c FROM contact_methods
        WHERE method_type = 'work_email'
        """
    ).fetchone()["c"]
    return {
        "companies": companies,
        "people": people,
        "contact_methods": contacts,
        "people_with_linkedin": with_li,
        "people_with_work_email": with_email,
    }


def get_detailed_status(conn: sqlite3.Connection) -> dict[str, dict[str, int]]:
    by_src_co = {
        r["source"]: r["c"]
        for r in conn.execute(
            "SELECT source, COUNT(*) AS c FROM companies GROUP BY source"
        )
    }
    by_src_pe = {
        r["source"]: r["c"]
        for r in conn.execute("SELECT source, COUNT(*) AS c FROM people GROUP BY source")
    }
    total_p = conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"] or 0
    with_li = conn.execute(
        "SELECT COUNT(*) AS c FROM people WHERE linkedin_url IS NOT NULL AND linkedin_url != ''"
    ).fetchone()["c"] or 0
    with_em = conn.execute(
        """
        SELECT COUNT(DISTINCT person_id) AS c FROM contact_methods
        WHERE method_type = 'work_email'
        """
    ).fetchone()["c"] or 0
    return {
        "companies_by_source": by_src_co,
        "people_by_source": by_src_pe,
        "linkedin_pct": round(100.0 * with_li / total_p, 1) if total_p else 0.0,
        "email_pct": round(100.0 * with_em / total_p, 1) if total_p else 0.0,
    }


def search_people(
    conn: sqlite3.Connection,
    seniority: str | None = None,
    has_linkedin: bool = False,
    has_email: bool = False,
    source: str | None = None,
    limit: int = 50,
) -> list[sqlite3.Row]:
    joins = [
        "SELECT p.*, c.name AS company_name, c.domain AS company_domain, c.batch AS company_batch, c.source AS company_source",
        "FROM people p JOIN companies c ON c.id = p.company_id",
        "WHERE 1=1",
    ]
    params: list = []
    if seniority:
        joins.append("AND p.seniority = ?")
        params.append(seniority)
    if has_linkedin:
        joins.append("AND p.linkedin_url IS NOT NULL AND p.linkedin_url != ''")
    if has_email:
        joins.append(
            """AND EXISTS (
            SELECT 1 FROM contact_methods cm
            WHERE cm.person_id = p.id AND cm.method_type = 'work_email'
        )"""
        )
    if source:
        joins.append("AND (p.source = ? OR c.source = ?)")
        params.extend([source, source])
    joins.append("ORDER BY p.id DESC")
    joins.append(f"LIMIT {int(limit)}")
    sql = " ".join(joins)
    return list(conn.execute(sql, params))


def export_rows_query(
    conn: sqlite3.Connection,
    has_linkedin: bool = False,
    has_email: bool = False,
    source: str | None = None,
) -> list[ExportRow]:
    sql = """
        SELECT
            c.name AS company_name,
            c.domain AS company_domain,
            c.batch AS company_batch,
            c.source AS company_source,
            p.full_name AS person_name,
            p.title,
            p.seniority,
            p.linkedin_url,
            p.twitter_url,
            (SELECT cm.value FROM contact_methods cm
             WHERE cm.person_id = p.id AND cm.method_type = 'work_email'
             ORDER BY cm.id DESC LIMIT 1) AS work_email,
            (SELECT cm.status FROM contact_methods cm
             WHERE cm.person_id = p.id AND cm.method_type = 'work_email'
             ORDER BY cm.id DESC LIMIT 1) AS email_status
        FROM people p
        JOIN companies c ON c.id = p.company_id
        WHERE 1=1
    """
    params: list = []
    if has_linkedin:
        sql += " AND p.linkedin_url IS NOT NULL AND p.linkedin_url != ''"
    if has_email:
        sql += """ AND EXISTS (
            SELECT 1 FROM contact_methods cm2
            WHERE cm2.person_id = p.id AND cm2.method_type = 'work_email'
        )"""
    if source:
        sql += " AND (p.source = ? OR c.source = ?)"
        params.extend([source, source])
    sql += " ORDER BY c.name, p.full_name"
    rows = []
    for r in conn.execute(sql, params):
        rows.append(
            ExportRow(
                company_name=r["company_name"],
                company_domain=r["company_domain"],
                company_batch=r["company_batch"],
                company_source=r["company_source"],
                person_name=r["person_name"],
                title=r["title"],
                seniority=r["seniority"],
                linkedin_url=r["linkedin_url"],
                twitter_url=r["twitter_url"],
                work_email=r["work_email"],
                email_status=r["email_status"],
            )
        )
    return rows


def get_people_without_work_email(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT p.*, c.domain AS company_domain
            FROM people p
            JOIN companies c ON c.id = p.company_id
            WHERE c.domain IS NOT NULL AND c.domain != ''
            AND NOT EXISTS (
                SELECT 1 FROM contact_methods cm
                WHERE cm.person_id = p.id AND cm.method_type = 'work_email'
            )
            ORDER BY p.id
            LIMIT ?
            """,
            (limit,),
        )
    )


def merge_duplicate_people(conn: sqlite3.Connection) -> int:
    """Merge rows that share the same normalized linkedin_url (shouldn't happen); no-op if schema enforces unique."""
    return 0
