from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
import httpx

from .models import RawArticulation

LOGGER = logging.getLogger("crosslist.scrapers.assist")
ROOT_DIR = Path(__file__).resolve().parents[3]
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://crosslist:crosslist@localhost:5433/crosslist")
ASSIST_BASE_URL = "https://prod.assistng.org"
CACHE_DIR = ROOT_DIR / "data" / "cache" / "assist"
CATALOG_SNAPSHOT_PATH = ROOT_DIR / "data" / "cache" / "catalog_scrape_snapshot.json"


@dataclass(frozen=True)
class AgreementTarget:
    sending_id: int
    sending_name: str
    sending_slug: str
    receiving_id: int
    receiving_name: str
    receiving_slug: str
    sending_prefixes: frozenset[str]
    receiving_prefixes: frozenset[str]


AGREEMENT_TARGETS = (
    AgreementTarget(
        sending_id=137,
        sending_name="SMC",
        sending_slug="smc",
        receiving_id=89,
        receiving_name="UC Davis",
        receiving_slug="ucdavis",
        sending_prefixes=frozenset({"MATH", "CS", "ENGL", "PSYCH"}),
        receiving_prefixes=frozenset({"MAT", "ECS", "ENL", "PSC"}),
    ),
    AgreementTarget(
        sending_id=137,
        sending_name="SMC",
        sending_slug="smc",
        receiving_id=39,
        receiving_name="SJSU",
        receiving_slug="sjsu",
        sending_prefixes=frozenset({"MATH", "CS", "ENGL", "PSYCH"}),
        receiving_prefixes=frozenset({"MATH", "CS", "ENGL", "PSYC"}),
    ),
)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")


def cache_path(name: str) -> Path:
    return CACHE_DIR / name


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, str] | None = None,
    cache_name: str,
) -> dict[str, Any]:
    target = cache_path(cache_name)
    if target.exists():
        return json.loads(target.read_text())

    response = await client.get(
        url,
        params=params,
        headers={"accept": "application/json", "user-agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    payload = response.json()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2))
    return payload


async def fetch_institutions(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    payload = await fetch_json(
        client,
        f"{ASSIST_BASE_URL}/Institutions/api",
        cache_name="institutions.json",
    )
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected ASSIST institutions payload")
    return payload


async def fetch_latest_all_departments_key(
    client: httpx.AsyncClient,
    target: AgreementTarget,
) -> tuple[str, int]:
    candidate_year_ids = list(range(90, 69, -1)) + list(range(69, 30, -1))
    for academic_year_id in candidate_year_ids:
        payload = await fetch_json(
            client,
            f"{ASSIST_BASE_URL}/articulation/api/Agreements/Published/for/{target.receiving_id}/to/{target.sending_id}/in/{academic_year_id}",
            params={"types": "Department"},
            cache_name=f"published_{target.sending_slug}_to_{target.receiving_slug}_{academic_year_id}.json",
        )
        result = payload.get("result") or {}
        all_reports = result.get("allReports") or []
        reports = result.get("reports") or []
        if not all_reports and not reports:
            continue

        for report in all_reports:
            if report.get("type") == "AllDepartments":
                return report["key"], academic_year_id

    raise RuntimeError(
        f"No published ASSIST agreements found for {target.sending_name} -> {target.receiving_name}"
    )


async def fetch_agreement_payload(
    client: httpx.AsyncClient,
    agreement_key: str,
    *,
    cache_name: str,
) -> dict[str, Any]:
    payload = await fetch_json(
        client,
        f"{ASSIST_BASE_URL}/articulation/api/Agreements",
        params={"Key": agreement_key},
        cache_name=cache_name,
    )
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected ASSIST agreement payload for {agreement_key}")
    return result


def flatten_courses(node: dict[str, Any]) -> list[dict[str, Any]]:
    if node.get("type") == "Course":
        return [node]

    courses: list[dict[str, Any]] = []
    for child in node.get("items") or []:
        courses.extend(flatten_courses(child))
    return courses


def classify_articulation(sending_articulation: dict[str, Any]) -> str:
    group_conjunctions = sending_articulation.get("courseGroupConjunctions") or []
    if any(item.get("groupConjunction") == "Or" for item in group_conjunctions):
        return "OR_GROUP"

    groups = sending_articulation.get("items") or []
    for group in groups:
        courses = flatten_courses(group)
        if len(courses) > 1:
            return "SERIES"

    if len(groups) == 1:
        return "DIRECT"

    return "OTHER"


def build_notes(sending_articulation: dict[str, Any]) -> str | None:
    groups = sending_articulation.get("items") or []
    rendered_groups: list[str] = []
    for group in sorted(groups, key=lambda item: item.get("position", 0)):
        courses = flatten_courses(group)
        if not courses:
            continue
        label = f" {group.get('courseConjunction', 'And')} ".join(
            f"{course.get('prefix')} {course.get('courseNumber')}".strip()
            for course in courses
        )
        rendered_groups.append(label)

    if not rendered_groups:
        return None

    conjunctions = sending_articulation.get("courseGroupConjunctions") or []
    if conjunctions and len(rendered_groups) > 1:
        note = rendered_groups[0]
        ordered = sorted(conjunctions, key=lambda item: item.get("sendingCourseGroupBeginPosition", 0))
        for index, conjunction in enumerate(ordered, start=1):
            if index >= len(rendered_groups):
                break
            note = f"{note} {conjunction.get('groupConjunction', 'Or')} {rendered_groups[index]}"
        return note

    if len(rendered_groups) == 1:
        return rendered_groups[0]

    return " ; ".join(rendered_groups)


def parse_raw_articulations(agreement: dict[str, Any], target: AgreementTarget) -> list[RawArticulation]:
    departments = json.loads(agreement["articulations"])
    academic_year = agreement["academicYear"]
    if isinstance(academic_year, str):
        academic_year = json.loads(academic_year)
    agreement_year = int(str(academic_year["code"]).split("-", 1)[0])
    rows: list[RawArticulation] = []

    for department in departments:
        for articulation in department.get("articulations", []):
            receiving_course = articulation.get("course") or {}
            receiving_prefix = str(receiving_course.get("prefix") or "").strip()
            receiving_number = str(receiving_course.get("courseNumber") or "").strip()
            if receiving_prefix not in target.receiving_prefixes or not receiving_number:
                continue

            sending_articulation = articulation.get("sendingArticulation") or {}
            sending_groups = sending_articulation.get("items") or []
            if not sending_groups:
                continue

            articulation_type = classify_articulation(sending_articulation)
            notes = build_notes(sending_articulation)
            seen_sending_courses: set[tuple[str, str]] = set()
            for group in sending_groups:
                for sending_course in flatten_courses(group):
                    sending_prefix = str(sending_course.get("prefix") or "").strip()
                    sending_number = str(sending_course.get("courseNumber") or "").strip()
                    if sending_prefix not in target.sending_prefixes or not sending_number:
                        continue
                    dedupe_key = (sending_prefix, sending_number)
                    if dedupe_key in seen_sending_courses:
                        continue
                    seen_sending_courses.add(dedupe_key)
                    rows.append(
                        RawArticulation(
                            from_institution=target.sending_name,
                            from_course_code=f"{sending_prefix} {sending_number}",
                            to_institution=target.receiving_name,
                            to_course_code=f"{receiving_prefix} {receiving_number}",
                            articulation_type=articulation_type,
                            agreement_year=agreement_year,
                            notes=notes,
                        )
                    )

    deduped: dict[tuple[str, str, str, str, int], RawArticulation] = {}
    for row in rows:
        key = (
            row.from_institution,
            row.from_course_code,
            row.to_institution,
            row.to_course_code,
            row.agreement_year,
        )
        deduped[key] = row
    return list(deduped.values())


def load_snapshot_course_keys() -> set[tuple[str, str]]:
    if not CATALOG_SNAPSHOT_PATH.exists():
        raise RuntimeError(f"Catalog snapshot not found at {CATALOG_SNAPSHOT_PATH}")

    payloads = json.loads(CATALOG_SNAPSHOT_PATH.read_text())
    keys: set[tuple[str, str]] = set()
    for payload in payloads:
        institution_slug = payload["institution_slug"]
        for course in payload["courses"]:
            keys.add((institution_slug, f"{course['subject_code']} {course['course_code']}"))
    return keys


def institution_slug_for_name(name: str) -> str:
    return {
        "SMC": "smc",
        "UC Davis": "ucdavis",
        "SJSU": "sjsu",
    }[name]


def resolve_against_snapshot(rows: list[RawArticulation]) -> tuple[list[RawArticulation], list[RawArticulation]]:
    course_keys = load_snapshot_course_keys()
    loaded: list[RawArticulation] = []
    skipped: list[RawArticulation] = []

    for row in rows:
        from_key = (institution_slug_for_name(row.from_institution), row.from_course_code)
        to_key = (institution_slug_for_name(row.to_institution), row.to_course_code)
        if from_key in course_keys and to_key in course_keys:
            loaded.append(row)
        else:
            skipped.append(row)

    return loaded, skipped


async def upsert_articulations(connection: asyncpg.Connection, rows: list[RawArticulation]) -> tuple[int, int]:
    loaded = 0
    skipped = 0

    for row in rows:
        from_parts = row.from_course_code.split(" ", 1)
        to_parts = row.to_course_code.split(" ", 1)
        if len(from_parts) != 2 or len(to_parts) != 2:
            skipped += 1
            continue

        from_prefix, from_number = from_parts
        to_prefix, to_number = to_parts

        from_course_id = await connection.fetchval(
            """
            SELECT c.id
            FROM courses c
            JOIN subjects s ON s.id = c.subject_id
            JOIN institutions i ON i.id = c.institution_id
            WHERE i.short_name = $1 AND s.code = $2 AND c.code = $3
            """,
            row.from_institution,
            from_prefix,
            from_number,
        )
        to_course_id = await connection.fetchval(
            """
            SELECT c.id
            FROM courses c
            JOIN subjects s ON s.id = c.subject_id
            JOIN institutions i ON i.id = c.institution_id
            WHERE i.short_name = $1 AND s.code = $2 AND c.code = $3
            """,
            row.to_institution,
            to_prefix,
            to_number,
        )
        if not from_course_id or not to_course_id:
            skipped += 1
            continue

        existing = await connection.fetchval(
            """
            SELECT id
            FROM articulations
            WHERE from_course_id = $1
              AND to_course_id = $2
              AND source = $3
              AND agreement_year = $4
            """,
            from_course_id,
            to_course_id,
            "assist.org",
            row.agreement_year,
        )
        if existing:
            await connection.execute(
                """
                UPDATE articulations
                SET articulation_type = $2, notes = $3, scraped_at = NOW()
                WHERE id = $1
                """,
                existing,
                row.articulation_type,
                row.notes,
            )
        else:
            await connection.execute(
                """
                INSERT INTO articulations (
                    id, from_course_id, to_course_id, source, agreement_year, articulation_type, notes, scraped_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                """,
                uuid4(),
                from_course_id,
                to_course_id,
                "assist.org",
                row.agreement_year,
                row.articulation_type,
                row.notes,
            )
        loaded += 1

    return loaded, skipped


async def persist_scrape_run(connection: asyncpg.Connection, loaded: int, skipped: int) -> None:
    await connection.execute(
        """
        INSERT INTO scrape_runs (id, source, started_at, finished_at, status, stats)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        """,
        uuid4(),
        "assist.org",
        datetime.now(tz=UTC),
        datetime.now(tz=UTC),
        "SUCCESS" if skipped == 0 else "PARTIAL",
        json.dumps({"loaded": loaded, "skipped": skipped}),
    )


async def run_assist_ingest(*, skip_db: bool = False) -> tuple[list[RawArticulation], list[RawArticulation]]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        await fetch_institutions(client)

        rows: list[RawArticulation] = []
        for target in AGREEMENT_TARGETS:
            agreement_key, _academic_year_id = await fetch_latest_all_departments_key(client, target)
            agreement = await fetch_agreement_payload(
                client,
                agreement_key,
                cache_name=f"agreement_{target.sending_slug}_to_{target.receiving_slug}.json",
            )
            rows.extend(parse_raw_articulations(agreement, target))

    if skip_db:
        return resolve_against_snapshot(rows)

    connection = await asyncpg.connect(DATABASE_URL)
    try:
        loaded_count, skipped_count = await upsert_articulations(connection, rows)
        await persist_scrape_run(connection, loaded_count, skipped_count)
    finally:
        await connection.close()

    loaded_rows, skipped_rows = resolve_against_snapshot(rows)
    return loaded_rows, skipped_rows


def print_summary(loaded_rows: list[RawArticulation], skipped_rows: list[RawArticulation]) -> None:
    by_pair: dict[str, int] = defaultdict(int)
    for row in loaded_rows:
        by_pair[f"{row.from_institution} -> {row.to_institution}"] += 1

    LOGGER.info("Loaded %s articulations (%s skipped because courses were not in DB/catalog)", len(loaded_rows), len(skipped_rows))
    for pair, count in sorted(by_pair.items()):
        LOGGER.info("  %s: %s", pair, count)

    LOGGER.info("Sample articulations:")
    for row in loaded_rows[:5]:
        LOGGER.info(
            "  %s -> %s (%s, %s)",
            row.from_course_code,
            row.to_course_code,
            row.articulation_type,
            row.agreement_year,
        )

    if skipped_rows:
        LOGGER.info("Skipped examples:")
        for row in skipped_rows[:5]:
            LOGGER.info("  %s -> %s", row.from_course_code, row.to_course_code)


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Fetch ASSIST articulations for CrossList seed institutions")
    parser.add_argument("--skip-db", action="store_true", help="Resolve against the cached catalog snapshot instead of inserting into Postgres")
    args = parser.parse_args()

    loaded_rows, skipped_rows = asyncio.run(run_assist_ingest(skip_db=args.skip_db))
    print_summary(loaded_rows, skipped_rows)


if __name__ == "__main__":
    main()
