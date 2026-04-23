from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import click

from app.stats import fetch_stats
from pipelines.embed import run_embedding_pipeline
from crosslist_scrapers.assist import run_assist_ingest
from crosslist_scrapers.ingest import persist_to_db, scrape_catalogs

LOGGER = logging.getLogger("crosslist.cli")
ROOT_DIR = Path(__file__).resolve().parents[3]


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


async def run_catalog_stage() -> dict[str, object]:
    scraped_payloads, counts = await scrape_catalogs()
    snapshot_path = ROOT_DIR / "data" / "cache" / "catalog_scrape_snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(scraped_payloads, indent=2))
    await persist_to_db(scraped_payloads)
    return {
        "counts": {institution: dict(subject_counts) for institution, subject_counts in counts.items()},
        "courses": sum(sum(subject_counts.values()) for subject_counts in counts.values()),
    }


async def run_articulation_stage() -> dict[str, int]:
    loaded_rows, skipped_rows = await run_assist_ingest(skip_db=False)
    return {"loaded": len(loaded_rows), "skipped": len(skipped_rows)}


async def run_stage(stage: str) -> dict[str, object]:
    if stage == "catalogs":
        return await run_catalog_stage()
    if stage == "articulations":
        return await run_articulation_stage()
    if stage == "embeddings":
        return await run_embedding_pipeline()
    raise ValueError(f"Unsupported stage: {stage}")


@click.group()
def app() -> None:
    configure_logging()


@app.command()
@click.option(
    "--stage",
    type=click.Choice(["catalogs", "articulations", "embeddings"], case_sensitive=True),
    default=None,
    help="Run a single ingest stage instead of the full pipeline.",
)
def ingest(stage: str | None) -> None:
    stages = [stage] if stage else ["catalogs", "articulations", "embeddings"]
    results: dict[str, object] = {}

    try:
        with click.progressbar(stages, label="Running ingest stages") as bar:
            for stage_name in bar:
                click.echo(f"\n[{stage_name}] starting")
                results[stage_name] = asyncio.run(run_stage(stage_name))
                click.echo(json.dumps({stage_name: results[stage_name]}, indent=2, default=str))
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@app.command()
def status() -> None:
    try:
        payload = asyncio.run(fetch_stats())
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Institutions: {payload.institutions}")
    click.echo(f"Courses: {payload.courses}")
    for institution, count in payload.courses_per_institution.items():
        click.echo(f"  {institution}: {count}")
    click.echo(f"Articulations: {payload.articulations}")
    click.echo(f"Embedded courses: {payload.embedded_courses}")
    click.echo(f"Last successful scrape run: {payload.last_successful_scrape_run or 'none'}")
