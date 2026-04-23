from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import asyncpg

from .deanza import DeAnzaScraper
from .models import InstitutionConfig, RawCourse
from .sjsu import SJSUScraper
from .ucberkeley import UCBerkeleyScraper

LOGGER = logging.getLogger("crosslist.scrapers.ingest")
ROOT_DIR = Path(__file__).resolve().parents[3]

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://crosslist:crosslist@localhost:5433/crosslist")

INSTITUTIONS: dict[str, InstitutionConfig] = {
    "deanza": InstitutionConfig(
        name="De Anza College",
        short_name="De Anza",
        kind="CC",
        catalog_url="https://www.deanza.edu/catalog/",
    ),
    "ucberkeley": InstitutionConfig(
        name="University of California, Berkeley",
        short_name="UC Berkeley",
        kind="UC",
        catalog_url="https://guide.berkeley.edu/courses/",
    ),
    "sjsu": InstitutionConfig(
        name="San Jose State University",
        short_name="SJSU",
        kind="CSU",
        catalog_url="https://catalog.sjsu.edu/content.php?catoid=15&navoid=5382",
    ),
}


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


async def scrape_catalogs() -> tuple[list[dict[str, object]], dict[str, dict[str, int]]]:
    scrapers = [DeAnzaScraper(), UCBerkeleyScraper(), SJSUScraper()]
    scraped_payloads: list[dict[str, object]] = []
    counts: dict[str, dict[str, int]] = defaultdict(dict)

    for scraper in scrapers:
        async with scraper:
            subjects = await scraper.list_subjects()
            for subject in subjects:
                try:
                    courses = await scraper.list_courses(subject)
                except Exception as exc:
                    LOGGER.warning("%s %s failed: %s", scraper.institution_name, subject.code, exc)
                    courses = []
                counts[scraper.institution_slug][subject.code] = len(courses)
                scraped_payloads.append(
                    {
                        "institution_slug": scraper.institution_slug,
                        "institution_name": scraper.institution_name,
                        "subject": subject.model_dump(),
                        "courses": [course.model_dump(mode="json") for course in courses],
                        "heuristic_hits": list(scraper.heuristic_hits),
                    }
                )

    return scraped_payloads, counts


async def persist_to_db(scraped_payloads: list[dict[str, object]]) -> None:
    connection = await asyncpg.connect(DATABASE_URL)
    run_id = uuid4()
    started_at = datetime.now(tz=UTC)
    await connection.execute(
        """
        INSERT INTO scrape_runs (id, source, started_at, status, stats)
        VALUES ($1, $2, $3, $4, $5::jsonb)
        """,
        run_id,
        "catalogs",
        started_at,
        "PARTIAL",
        json.dumps({"institutions": len(scraped_payloads)}),
    )

    try:
        for payload in scraped_payloads:
            institution_slug = payload["institution_slug"]
            institution = INSTITUTIONS[institution_slug]
            institution_id = await upsert_institution(connection, institution)
            subject = payload["subject"]
            subject_id = await upsert_subject(connection, institution_id, subject["code"], subject["name"])

            for course_data in payload["courses"]:
                await upsert_course(connection, institution_id, subject_id, RawCourse.model_validate(course_data))

        await connection.execute(
            """
            UPDATE scrape_runs
            SET finished_at = $2, status = $3, stats = $4::jsonb
            WHERE id = $1
            """,
            run_id,
            datetime.now(tz=UTC),
            "SUCCESS",
            json.dumps({"institutions": len(scraped_payloads), "source": "catalogs"}),
        )
    except Exception:
        await connection.execute(
            """
            UPDATE scrape_runs
            SET finished_at = $2, status = $3
            WHERE id = $1
            """,
            run_id,
            datetime.now(tz=UTC),
            "FAILED",
        )
        raise
    finally:
        await connection.close()


async def upsert_institution(connection: asyncpg.Connection, institution: InstitutionConfig):
    existing = await connection.fetchval(
        "SELECT id FROM institutions WHERE short_name = $1",
        institution.short_name,
    )
    if existing:
        await connection.execute(
            """
            UPDATE institutions
            SET name = $2, kind = $3, catalog_url = $4
            WHERE id = $1
            """,
            existing,
            institution.name,
            institution.kind,
            institution.catalog_url,
        )
        return existing

    institution_id = uuid4()
    await connection.execute(
        """
        INSERT INTO institutions (id, name, short_name, kind, catalog_url)
        VALUES ($1, $2, $3, $4, $5)
        """,
        institution_id,
        institution.name,
        institution.short_name,
        institution.kind,
        institution.catalog_url,
    )
    return institution_id


async def upsert_subject(connection: asyncpg.Connection, institution_id, code: str, name: str):
    existing = await connection.fetchval(
        "SELECT id FROM subjects WHERE institution_id = $1 AND code = $2",
        institution_id,
        code,
    )
    if existing:
        await connection.execute("UPDATE subjects SET name = $2 WHERE id = $1", existing, name)
        return existing

    subject_id = uuid4()
    await connection.execute(
        "INSERT INTO subjects (id, institution_id, code, name) VALUES ($1, $2, $3, $4)",
        subject_id,
        institution_id,
        code,
        name,
    )
    return subject_id


async def upsert_course(connection: asyncpg.Connection, institution_id, subject_id, course: RawCourse):
    await connection.execute(
        """
        INSERT INTO courses (
            id, institution_id, subject_id, code, title, units, description, raw_html, catalog_url, scraped_at
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        ON CONFLICT (institution_id, subject_id, code)
        DO UPDATE SET
            title = EXCLUDED.title,
            units = EXCLUDED.units,
            description = EXCLUDED.description,
            raw_html = EXCLUDED.raw_html,
            catalog_url = EXCLUDED.catalog_url,
            scraped_at = NOW()
        """,
        uuid4(),
        institution_id,
        subject_id,
        course.course_code,
        course.title,
        course.units,
        course.description,
        course.raw_html,
        course.catalog_url,
    )


def print_summary(scraped_payloads: list[dict[str, object]], counts: dict[str, dict[str, int]]) -> None:
    for institution_slug, subject_counts in counts.items():
        total = sum(subject_counts.values())
        LOGGER.info("%s: %s courses total", institution_slug, total)
        for subject_code, count in sorted(subject_counts.items()):
            LOGGER.info("  %s: %s", subject_code, count)

    grouped_samples: dict[str, list[RawCourse]] = defaultdict(list)
    for payload in scraped_payloads:
        institution_slug = payload["institution_slug"]
        courses = [RawCourse.model_validate(course) for course in payload["courses"]]
        grouped_samples[institution_slug].extend(courses[:3])

    for institution_slug, courses in grouped_samples.items():
        LOGGER.info("%s samples:", institution_slug)
        for course in courses[:3]:
            LOGGER.info(
                "  %s %s — %s — %s",
                course.subject_code,
                course.course_code,
                course.title,
                course.description[:120],
            )


async def async_main(skip_db: bool) -> None:
    scraped_payloads, counts = await scrape_catalogs()

    cache_path = ROOT_DIR / "data" / "cache" / "catalog_scrape_snapshot.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(scraped_payloads, indent=2))

    if not skip_db:
        await persist_to_db(scraped_payloads)

    print_summary(scraped_payloads, counts)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Run the CrossList catalog ingest pipeline")
    parser.add_argument("--skip-db", action="store_true", help="Scrape catalogs without attempting database upserts")
    args = parser.parse_args()
    asyncio.run(async_main(skip_db=args.skip_db))


if __name__ == "__main__":
    main()
