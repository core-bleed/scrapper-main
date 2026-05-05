from sdr_cli.db import add_contact_method, export_rows_query, upsert_company, upsert_person
from sdr_cli.models import Company, ContactMethod, Person


def test_upsert_company_and_person(db_conn):
    cid = upsert_company(
        db_conn,
        Company(
            name="Acme",
            website="https://acme.com",
            source="test",
        ),
    )
    assert cid > 0
    pid = upsert_person(
        db_conn,
        Person(
            company_id=cid,
            full_name="Jane Doe",
            title="CEO",
            linkedin_url="https://www.linkedin.com/in/janedoe",
            source="test",
        ),
    )
    assert pid > 0
    add_contact_method(
        db_conn,
        ContactMethod(
            person_id=pid,
            method_type="work_email",
            value="jane@acme.com",
            provider="test",
        ),
    )
    rows = export_rows_query(db_conn)
    assert len(rows) == 1
    assert rows[0].work_email == "jane@acme.com"


def test_person_dedup_by_linkedin(db_conn):
    cid = upsert_company(
        db_conn,
        Company(name="Acme", domain="acme.com", source="t"),
    )
    upsert_person(
        db_conn,
        Person(company_id=cid, full_name="Jane Doe", linkedin_url="https://linkedin.com/in/j", source="t"),
    )
    upsert_person(
        db_conn,
        Person(
            company_id=cid,
            full_name="Jane D.",
            title="Founder",
            linkedin_url="https://linkedin.com/in/j",
            source="t",
        ),
    )
    n = db_conn.execute("SELECT COUNT(*) AS c FROM people").fetchone()["c"]
    assert n == 1
