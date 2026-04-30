"""IkerKeta CLI — command-line interface for the data acquisition pipeline.

Usage:
    ikerketa sources          List configured data sources
    ikerketa fetch <source>   Fetch data from a specific source
    ikerketa status           Show pipeline status
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ikerketa.config import load_sources_config, settings
from ikerketa.logging_setup import setup_logging

app = typer.Typer(
    name="ikerketa",
    help="IkerKeta — Agronomic Data Acquisition Pipeline for NKZ-BioOrchestrator",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """Initialize logging on every CLI invocation."""
    setup_logging()
    settings.ensure_dirs()


@app.command()
def sources() -> None:
    """List all configured data sources and their status."""
    config = load_sources_config()

    table = Table(title="IkerKeta Data Sources")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Domain", style="yellow")
    table.add_column("Priority", style="magenta")
    table.add_column("Auth", style="red")
    table.add_column("Enabled", style="bold")

    for key, src in config.get("sources", {}).items():
        enabled = src.get("enabled", True)
        table.add_row(
            src.get("name", key),
            src.get("type", "?"),
            src.get("domain", "?"),
            src.get("priority", "?"),
            src.get("auth", "none"),
            "✓" if enabled else "✗",
        )

    console.print(table)


@app.command()
def status() -> None:
    """Show pipeline status: data directories and file counts."""
    table = Table(title="Pipeline Status")
    table.add_column("Directory", style="cyan")
    table.add_column("Files", style="green", justify="right")
    table.add_column("Path", style="dim")

    for label, path in [
        ("Raw", settings.data_raw_dir),
        ("Processed", settings.data_processed_dir),
        ("Reports", settings.data_reports_dir),
    ]:
        if path.exists():
            files = [f for f in path.iterdir() if f.is_file() and f.name != ".gitkeep"]
            table.add_row(label, str(len(files)), str(path))
        else:
            table.add_row(label, "—", f"{path} (not created)")

    console.print(table)


@app.command()
def fetch(
    source: str = typer.Argument(help="Source name from sources.yaml (e.g., 'agrovoc', 'eppo')"),
    limit: int = typer.Option(10, help="Maximum records to fetch"),
) -> None:
    """Fetch data from a specific source connector."""
    config = load_sources_config()
    source_config = config.get("sources", {}).get(source)

    if source_config is None:
        console.print(f"[red]Error:[/red] Source '{source}' not found in sources.yaml")
        console.print(f"Available: {', '.join(config.get('sources', {}).keys())}")
        raise typer.Exit(1)

    if not source_config.get("enabled", True):
        console.print(f"[yellow]Warning:[/yellow] Source '{source}' is disabled in sources.yaml")
        raise typer.Exit(1)

    console.print(f"[cyan]Fetching from {source_config.get('name', source)}...[/cyan]")
    console.print(f"[dim]Limit: {limit} records[/dim]")

    # Import the connector dynamically
    try:
        module = __import__(f"ikerketa.connectors.{source}", fromlist=[source])
        connector_cls = getattr(module, "Connector", None)
        if connector_cls is None:
            console.print(f"[red]Error:[/red] No 'Connector' class found in ikerketa.connectors.{source}")
            raise typer.Exit(1)

        with connector_cls() as conn:
            result = conn.run(limit=limit)

        if result.error:
            console.print(f"[red]Error:[/red] {result.error}")
            raise typer.Exit(1)

        console.print(f"[green]✓[/green] Fetched {len(result.entities)} entities, {len(result.relationships)} relationships")
        console.print(f"[dim]Duration: {result.duration_seconds:.2f}s[/dim]")

        if result.validation:
            v = result.validation
            console.print(f"[dim]Validation: {v.valid_records}/{v.total_records} valid ({v.success_rate:.0%})[/dim]")

    except ImportError:
        console.print(f"[yellow]Connector '{source}' not yet implemented[/yellow]")
        raise typer.Exit(1)


@app.command()
def pipeline(
    sources_list: list[str] = typer.Option(None, "--source", "-s", help="Sources to run (repeatable). Omit for all enabled."),
    limit: int = typer.Option(10, help="Maximum records per connector"),
    no_export: bool = typer.Option(False, "--no-export", help="Skip JSON-LD and Parquet export"),
) -> None:
    """Run the full pipeline: fetch → transform → crossref → dedup → export."""
    from ikerketa.pipeline import run_pipeline
    from ikerketa.report import generate_report

    console.print("[cyan]Starting IkerKeta pipeline...[/cyan]")
    console.print(f"[dim]Sources: {sources_list or 'all enabled'} | Limit: {limit}[/dim]")

    result = run_pipeline(sources=sources_list, limit=limit, export=not no_export)

    # Display results
    table = Table(title="Pipeline Results")
    table.add_column("Source", style="cyan")
    table.add_column("Entities", style="green", justify="right")
    table.add_column("Relationships", style="blue", justify="right")
    table.add_column("Duration", style="dim", justify="right")
    table.add_column("Status", style="bold")

    for cr in result.connector_results:
        status_str = "✓" if not cr.error else f"✗ {cr.error[:40]}"
        style = "" if not cr.error else "red"
        table.add_row(
            cr.source_name.value,
            str(len(cr.entities)),
            str(len(cr.relationships)),
            f"{cr.duration_seconds:.2f}s",
            status_str,
            style=style,
        )

    console.print(table)
    console.print()
    console.print(f"[bold]Entities:[/bold] {result.entities_before_dedup} → {result.entities_after_dedup} (dedup removed {result.entities_before_dedup - result.entities_after_dedup})")
    console.print(f"[bold]Cross-ref enriched:[/bold] {result.crossref_matches}")
    console.print(f"[bold]Relationships:[/bold] {result.relationships_total}")
    console.print(f"[bold]Duration:[/bold] {result.total_duration_seconds:.2f}s")

    if result.errors:
        console.print(f"\n[yellow]Warnings/Errors ({len(result.errors)}):[/yellow]")
        for err in result.errors:
            console.print(f"  [dim]• {err}[/dim]")

    # Generate quality report
    report = generate_report(result)
    console.print(f"\n[green]✓ Quality report saved to data/reports/[/green]")


@app.command()
def report() -> None:
    """Show the latest quality report."""
    reports_dir = settings.data_reports_dir
    if not reports_dir.exists():
        console.print("[yellow]No reports found. Run 'pipeline' first.[/yellow]")
        raise typer.Exit(1)

    import json

    reports = sorted(reports_dir.glob("quality_report_*.json"), reverse=True)
    if not reports:
        console.print("[yellow]No reports found. Run 'pipeline' first.[/yellow]")
        raise typer.Exit(1)

    latest = reports[0]
    with latest.open() as f:
        data = json.load(f)

    console.print(f"[cyan]Latest Report:[/cyan] {latest.name}")
    console.print(f"[dim]{data.get('report_timestamp', '')}[/dim]\n")

    # Summary
    summary = data.get("summary", {})
    console.print(f"[bold]Sources:[/bold] {summary.get('connectors_success', 0)}/{summary.get('connectors_run', 0)} succeeded")
    console.print(f"[bold]Entities:[/bold] {summary.get('entities_before_dedup', 0)} → {summary.get('entities_after_dedup', 0)}")
    console.print(f"[bold]Relationships:[/bold] {summary.get('relationships_total', 0)}")
    console.print(f"[bold]Cross-ref enriched:[/bold] {summary.get('crossref_enriched', 0)}")

    # Completeness
    completeness = data.get("field_completeness_pct", {})
    if completeness:
        console.print("\n[bold]Field Completeness:[/bold]")
        for field_name, pct in sorted(completeness.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            console.print(f"  {field_name:20s} {bar} {pct}%")


if __name__ == "__main__":
    app()
