from sdr_cli.scrapers.yc import parse_founders_html

FIXTURE_HTML = """
<html><body>
<div class="max-w-ycdc-page">
  <h3>Active Founders</h3>
  <div class="flex flex-col gap-y-4">
    <div class="flex flex-col gap-2 border-b border-gray-100">
      <div class="ycdc-card-new">
        <div class="hidden gap-4 md:flex">
          <div class="min-w-0 flex-1">
            <div class="flex flex-row items-center gap-x-2">
              <div class="text-xl font-bold">Hamza Al-Ali</div>
              <a href="https://x.com/hamzawy998">x</a>
              <a href="https://www.linkedin.com/in/hamzawy998" aria-label="LinkedIn profile">in</a>
            </div>
            <div class="text-gray-600">Founder &amp; CEO</div>
          </div>
        </div>
      </div>
    </div>
    <div class="flex flex-col gap-2 border-b border-gray-100">
      <div class="text-lg font-bold">Sanad Kiswani</div>
      <a href="https://www.linkedin.com/in/sanadkiswani">in</a>
      <div class="text-sm text-gray-600">Founder</div>
    </div>
  </div>
</div>
</body></html>
"""


def test_parse_founders_html_extracts_names_and_linkedin():
    founders = parse_founders_html(FIXTURE_HTML, "https://example.com")
    by_li = {f["linkedin_url"].rstrip("/").lower(): f for f in founders}
    assert "https://www.linkedin.com/in/hamzawy998".lower() in [k.lower() for k in by_li]
    h = by_li.get("https://www.linkedin.com/in/hamzawy998") or next(
        v for k, v in by_li.items() if "hamzawy998" in k
    )
    assert "Hamza" in (h.get("full_name") or "")
    assert h.get("title") and "Founder" in h["title"]
