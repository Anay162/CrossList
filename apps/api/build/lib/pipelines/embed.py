from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence
from uuid import uuid4

from openai import APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from sqlalchemy import Select, select

from db.models import Course, CourseEmbedding, ScrapeRun, ScrapeRunStatus
from db.session import async_session_factory

LOGGER = logging.getLogger("crosslist.pipelines.embed")
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 100
RETRY_DELAYS_SECONDS = (2, 4, 8)


@dataclass
class PendingCourse:
    id: object
    title: str
    description: str


def build_embedding_input(course: PendingCourse) -> str:
    return f"{course.title}. {course.description}".strip()


async def fetch_pending_courses() -> list[PendingCourse]:
    async with async_session_factory() as session:
        query: Select[tuple[object, str, str]] = (
            select(Course.id, Course.title, Course.description)
            .outerjoin(CourseEmbedding, CourseEmbedding.course_id == Course.id)
            .where(CourseEmbedding.course_id.is_(None))
            .order_by(Course.scraped_at.asc(), Course.id.asc())
        )
        rows = (await session.execute(query)).all()

    return [PendingCourse(id=row[0], title=row[1], description=row[2]) for row in rows]


async def request_embeddings(
    client: AsyncOpenAI,
    inputs: Sequence[str],
) -> list[list[float]]:
    last_error: Exception | None = None
    for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
        try:
            response = await client.embeddings.create(model=EMBEDDING_MODEL, input=list(inputs))
            ordered = sorted(response.data, key=lambda item: item.index)
            return [item.embedding for item in ordered]
        except (RateLimitError, APITimeoutError, APIError) as exc:
            last_error = exc
            if attempt == len(RETRY_DELAYS_SECONDS):
                break
            LOGGER.warning("Embedding batch failed (attempt %s/%s): %s", attempt, len(RETRY_DELAYS_SECONDS), exc)
            await asyncio.sleep(delay)

    raise RuntimeError(f"Embedding request failed: {last_error}") from last_error


async def store_embeddings(courses: Sequence[PendingCourse], vectors: Sequence[list[float]]) -> None:
    now = datetime.now(tz=UTC)
    async with async_session_factory() as session:
        for course, vector in zip(courses, vectors, strict=True):
            existing = await session.get(CourseEmbedding, course.id)
            if existing is None:
                session.add(
                    CourseEmbedding(
                        course_id=course.id,
                        embedding=vector,
                        model=EMBEDDING_MODEL,
                        embedded_at=now,
                    )
                )
            else:
                existing.embedding = vector
                existing.model = EMBEDDING_MODEL
                existing.embedded_at = now

        await session.commit()


async def record_scrape_run(status: ScrapeRunStatus, stats: dict[str, int]) -> None:
    now = datetime.now(tz=UTC)
    async with async_session_factory() as session:
        session.add(
            ScrapeRun(
                id=uuid4(),
                source="embeddings",
                started_at=now,
                finished_at=now,
                status=status,
                stats=stats,
            )
        )
        await session.commit()


async def run_embedding_pipeline() -> dict[str, int]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    pending = await fetch_pending_courses()
    if not pending:
        stats = {"embedded": 0, "pending": 0}
        await record_scrape_run(ScrapeRunStatus.SUCCESS, stats)
        return stats

    client = AsyncOpenAI(api_key=api_key)
    embedded = 0
    try:
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start : start + BATCH_SIZE]
            texts = [build_embedding_input(course) for course in batch]
            vectors = await request_embeddings(client, texts)
            await store_embeddings(batch, vectors)
            embedded += len(batch)
            LOGGER.info("Embedded %s/%s courses", embedded, len(pending))
    except Exception:
        await record_scrape_run(ScrapeRunStatus.FAILED, {"embedded": embedded, "pending": len(pending)})
        raise
    finally:
        await client.close()

    stats = {"embedded": embedded, "pending": len(pending)}
    await record_scrape_run(ScrapeRunStatus.SUCCESS, stats)
    return stats
