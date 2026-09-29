"""Typer command-line interface. A thin consumer of the `CloudLens` public API."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import typer

from cloudlens import CloudLens

app = typer.Typer(help="CloudLens: multi-cloud resource management and cost optimization.")

DEFAULT_CONFIG_PATH = "config.yaml"
EXAMPLE_CONFIG_PATH = "config.example.yaml"


@app.command()
def init(config: str = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c")) -> None:
    """Create config.yaml from config.example.yaml."""
    dest = Path(config)
    if dest.exists():
        typer.echo(f"{dest} already exists -- not overwriting.")
        raise typer.Exit(code=1)
    example = Path(EXAMPLE_CONFIG_PATH)
    if not example.exists():
        typer.echo(f"{example} not found. Run this command from the project root.")
        raise typer.Exit(code=1)
    shutil.copy(example, dest)
    typer.echo(f"Created {dest} from {example}. Edit it, then run `cloudlens sync`.")


@app.command()
def sync(config: str = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c")) -> None:
    """Fetch and store resource and cost data from all enabled providers."""
    cl = CloudLens(config_path=config)
    summary = cl.sync()
    for provider, count in summary.items():
        typer.echo(f"  {provider}: {count} resources")
    typer.echo("Sync complete.")


@app.command()
def analyze(config: str = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c")) -> None:
    """Run all optimization rules and budget checks against stored data."""
    cl = CloudLens(config_path=config)
    recommendations = cl.analyze()
    typer.echo(f"Generated {len(recommendations)} recommendations.")
    typer.echo(f"Total potential monthly savings: ${cl.total_potential_savings():,.2f}")


@app.command()
def report(config: str = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c")) -> None:
    """Print a summary of costs, top recommendations and budget status."""
    cl = CloudLens(config_path=config)

    typer.echo("=" * 70)
    typer.echo("COST SUMMARY BY PROVIDER")
    typer.echo("=" * 70)
    cost_summary = cl.get_cost_summary(group_by="provider")
    for _, row in cost_summary.iterrows():
        typer.echo(f"  {row['provider']:<12} ${row['total_cost']:>12,.2f}")

    typer.echo()
    typer.echo("=" * 70)
    typer.echo("TOP RECOMMENDATIONS (by estimated monthly saving)")
    typer.echo("=" * 70)
    recs = sorted(cl.get_recommendations(), key=lambda r: r.estimated_monthly_saving, reverse=True)[:10]
    if not recs:
        typer.echo("  No recommendations yet -- run `cloudlens analyze` first.")
    for rec in recs:
        typer.echo(
            f"  [{rec.severity.value.upper():<6}] {rec.title:<45} "
            f"save ${rec.estimated_monthly_saving:>9,.2f}/mo  ({rec.provider}/{rec.rule_id})"
        )
    typer.echo(f"\n  Total potential monthly savings: ${cl.total_potential_savings():,.2f}")

    typer.echo()
    typer.echo("=" * 70)
    typer.echo("BUDGET STATUS")
    typer.echo("=" * 70)
    for status in cl.get_budget_status():
        flag = " EXCEEDS FORECAST" if status.forecast_exceeds_budget else ""
        typer.echo(
            f"  {status.project:<16} ${status.spent:>10,.2f} / ${status.monthly_limit:>10,.2f} "
            f"({status.percent_used:>5.1f}%)  forecast ${status.forecast_month_end:>10,.2f}{flag}"
        )


@app.command()
def export(
    format: str = typer.Option("csv", "--format", help="Export format (only 'csv' supported)"),
    output: str = typer.Option("recommendations.csv", "--output", "-o"),
    config: str = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c"),
) -> None:
    """Export current recommendations to a file."""
    if format != "csv":
        typer.echo(f"Unsupported format: {format!r}. Only 'csv' is supported.")
        raise typer.Exit(code=1)

    cl = CloudLens(config_path=config)
    recs = cl.get_recommendations()

    with open(output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "id",
                "resource_id",
                "provider",
                "rule_id",
                "severity",
                "title",
                "description",
                "current_monthly_cost",
                "estimated_monthly_saving",
                "suggested_action",
                "created_at",
            ]
        )
        for rec in recs:
            writer.writerow(
                [
                    rec.id,
                    rec.resource_id,
                    rec.provider,
                    rec.rule_id,
                    rec.severity.value,
                    rec.title,
                    rec.description,
                    rec.current_monthly_cost,
                    rec.estimated_monthly_saving,
                    rec.suggested_action,
                    rec.created_at.isoformat(),
                ]
            )
    typer.echo(f"Exported {len(recs)} recommendations to {output}")


@app.command()
def demo(config: str = typer.Option(DEFAULT_CONFIG_PATH, "--config", "-c")) -> None:
    """Run the full pipeline (init if needed, sync, analyze, report) on sample data."""
    dest = Path(config)
    if not dest.exists():
        example = Path(EXAMPLE_CONFIG_PATH)
        if example.exists():
            shutil.copy(example, dest)
            typer.echo(f"Created {dest} from {example}.")

    cl = CloudLens(config_path=config)
    cl.config.demo_mode = True  # this command always runs on sample data, regardless of config.yaml

    typer.echo("Running sync...")
    summary = cl.sync()
    for provider, count in summary.items():
        typer.echo(f"  {provider}: {count} resources")

    typer.echo("Running analysis...")
    recs = cl.analyze()
    typer.echo(f"  {len(recs)} recommendations generated")

    typer.echo()
    report(config=config)


if __name__ == "__main__":
    app()
