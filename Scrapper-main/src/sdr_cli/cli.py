from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from sdr_cli.config import get_settings
from sdr_cli.db import (
    get_connection,
    get_detailed_status,
    get_status_counts,
    init_db,
    search_people,
)
from sdr_cli.export import export_csv, export_xlsx

app = typer.Typer(no_args_is_help=True, help="SDR scraper — companies, people, enrichment.")
scrape_app = typer.Typer(help="Scrape public sources.")
app.add_typer(scrape_app, name="scrape")
console = Console()


def _http_client(user_agent: str) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent},
        timeout=60.0,
        follow_redirects=True,
    )


@app.callback()
def main_callback() -> None:
    pass


@scrape_app.command("yc")
def scrape_yc(
    limit: int = typer.Option(50, "--limit", "-n", help="Max companies to ingest"),
    batch: Optional[str] = typer.Option(
        None, "--batch", "-b", help="Filter by YC batch label (e.g. W24)"
    ),
) -> None:
    """Scrape Y Combinator directory + founder pages."""
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)
    from sdr_cli.scrapers.yc import scrape_yc as run_yc

    with _http_client(settings.user_agent) as client:
        stats = run_yc(conn, client, limit, batch, settings.yc_request_delay)
    console.print(
        f"[green]YC:[/green] companies={stats['companies']} founders={stats['founders']} errors={stats['errors']}"
    )


@scrape_app.command("producthunt")
def scrape_ph(
    days: int = typer.Option(30, "--days", "-d"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Scrape Product Hunt via API (set PRODUCT_HUNT_ACCESS_TOKEN)."""
    settings = get_settings()
    if not settings.product_hunt_access_token:
        console.print("[red]Set PRODUCT_HUNT_ACCESS_TOKEN in .env[/red]")
        raise typer.Exit(1)
    conn = get_connection(settings.db_path)
    init_db(conn)
    from sdr_cli.scrapers.producthunt import scrape_producthunt

    with _http_client(settings.user_agent) as client:
        stats = scrape_producthunt(
            conn, settings.product_hunt_access_token, days, limit, client=client
        )
    console.print(
        f"[green]Product Hunt:[/green] companies={stats['companies']} people={stats['people']} errors={stats['errors']}"
    )


@scrape_app.command("team-pages")
def scrape_team(
    limit: int = typer.Option(50, "--limit", "-n", help="Max companies (with domain) to crawl"),
    delay: float = typer.Option(0.5, "--delay", help="Delay between HTTP requests (seconds)"),
) -> None:
    """Crawl /team, /about, etc. for companies already in the database."""
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)
    from sdr_cli.scrapers.team_page import scrape_team_pages_for_companies

    with _http_client(settings.user_agent) as client:
        stats = scrape_team_pages_for_companies(conn, client, limit, delay)
    console.print(
        f"[green]Team pages:[/green] tried={stats['companies_tried']} people={stats['people']} "
        f"skipped_no_domain={stats['skipped']} errors={stats['errors']}"
    )


@app.command("export")
def cmd_export(
    output: Path = typer.Option(Path("export.csv"), "--output", "-o"),
    format: str = typer.Option("csv", "--format", "-f", help="csv or xlsx"),
    has_linkedin: bool = typer.Option(False, "--has-linkedin"),
    has_email: bool = typer.Option(False, "--has-email"),
    source: Optional[str] = typer.Option(None, "--source", help="Filter by person or company source"),
) -> None:
    """Export joined companies + people + work email to CSV or XLSX."""
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)
    fmt = format.lower().strip()
    if fmt == "csv":
        n = export_csv(conn, output, has_linkedin, has_email, source)
    elif fmt in ("xlsx", "excel"):
        if not str(output).lower().endswith(".xlsx"):
            output = output.with_suffix(".xlsx")
        n = export_xlsx(conn, output, has_linkedin, has_email, source)
    else:
        console.print("[red]--format must be csv or xlsx[/red]")
        raise typer.Exit(1)
    console.print(f"[green]Exported {n} rows[/green] to {output}")


@app.command("status")
def cmd_status() -> None:
    """Show table counts and coverage."""
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)
    counts = get_status_counts(conn)
    detail = get_detailed_status(conn)
    table = Table(title="SDR status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    for k, v in counts.items():
        table.add_row(k.replace("_", " ").title(), str(v))
    table.add_row("LinkedIn %", str(detail["linkedin_pct"]))
    table.add_row("Work email %", str(detail["email_pct"]))
    console.print(table)
    if detail["companies_by_source"]:
        console.print("[bold]Companies by source[/bold]", detail["companies_by_source"])
    if detail["people_by_source"]:
        console.print("[bold]People by source[/bold]", detail["people_by_source"])


@app.command("enrich")
def cmd_enrich(
    provider: str = typer.Option(..., "--provider", "-p", help="apollo or hunter"),
    limit: int = typer.Option(100, "--limit", "-n"),
) -> None:
    """Enrich people missing work email (Apollo or Hunter)."""
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)
    p = provider.lower().strip()
    if p == "apollo":
        if not settings.apollo_api_key:
            console.print("[red]Set APOLLO_API_KEY[/red]")
            raise typer.Exit(1)
        from sdr_cli.enrichers.apollo import run_enrichment

        stats = run_enrichment(conn, settings.apollo_api_key, limit)
    elif p == "hunter":
        if not settings.hunter_api_key:
            console.print("[red]Set HUNTER_API_KEY[/red]")
            raise typer.Exit(1)
        from sdr_cli.enrichers.hunter import run_enrichment as hunter_run

        stats = hunter_run(conn, settings.hunter_api_key, limit)
    else:
        console.print("[red]--provider must be apollo or hunter[/red]")
        raise typer.Exit(1)
    console.print(stats)


@app.command("verify")
def cmd_verify(
    provider: str = typer.Option("hunter", "--provider", "-p"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Verify emails via Hunter (updates contact_methods status)."""
    settings = get_settings()
    if not settings.hunter_api_key:
        console.print("[red]Set HUNTER_API_KEY[/red]")
        raise typer.Exit(1)
    conn = get_connection(settings.db_path)
    init_db(conn)
    from sdr_cli.enrichers.hunter import run_verify

    stats = run_verify(conn, settings.hunter_api_key, limit)
    console.print(stats)


@app.command("search")
def cmd_search(
    seniority: Optional[str] = typer.Option(None, "--seniority", help="founder, c_suite, vp, ..."),
    has_linkedin: bool = typer.Option(False, "--has-linkedin"),
    has_email: bool = typer.Option(False, "--has-email"),
    source: Optional[str] = typer.Option(None, "--source"),
    limit: int = typer.Option(50, "--limit", "-n"),
) -> None:
    """Search people with filters (Rich table)."""
    settings = get_settings()
    conn = get_connection(settings.db_path)
    init_db(conn)
    rows = search_people(
        conn,
        seniority=seniority,
        has_linkedin=has_linkedin,
        has_email=has_email,
        source=source,
        limit=limit,
    )
    table = Table(title=f"People ({len(rows)})")
    table.add_column("Name")
    table.add_column("Title")
    table.add_column("Company")
    table.add_column("LinkedIn")
    for r in rows:
        table.add_row(
            r["full_name"] or "",
            (r["title"] or "")[:40],
            r["company_name"] or "",
            (r["linkedin_url"] or "")[:50],
        )
    console.print(table)


if __name__ == "__main__":
    app()
