from sdr_cli.models import Company, Person, infer_seniority, normalize_domain


def test_normalize_domain():
    assert normalize_domain("https://www.Example.com/path") == "example.com"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("") is None


def test_infer_seniority():
    assert infer_seniority("Co-Founder & CEO") == "founder"
    assert infer_seniority("VP Sales") == "vp"
    assert infer_seniority("Director of Eng") == "director"


def test_company_domain_from_website():
    c = Company(name="Acme", website="https://www.acme.ai", source="t")
    assert c.domain == "acme.ai"


def test_person_seniority_inferred():
    p = Person(
        company_id=1,
        full_name="Jane Doe",
        title="Founder",
        source="t",
    )
    assert p.seniority == "founder"
    assert p.is_decision_maker == 1
