from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import func, select

from db.models import Articulation, Course, CourseEmbedding, Institution, ScrapeRun, ScrapeRunStatus
from db.session import async_session_factory


@dataclass
class StatsPayload:
    institutions: int
    courses: int
    articulations: int
    embedded_courses: int
    last_successful_scrape_run: str | None
    courses_per_institution: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


async def fetch_stats() -> StatsPayload:
    async with async_session_factory() as session:
        institutions = await session.scalar(select(func.count()).select_from(Institution))
        courses = await session.scalar(select(func.count()).select_from(Course))
        articulations = await session.scalar(select(func.count()).select_from(Articulation))
        embedded_courses = await session.scalar(select(func.count()).select_from(CourseEmbedding))

        last_successful = await session.scalar(
            select(func.max(ScrapeRun.finished_at)).where(ScrapeRun.status == ScrapeRunStatus.SUCCESS)
        )

        per_institution_rows = await session.execute(
            select(Institution.short_name, func.count(Course.id))
            .select_from(Institution)
            .join(Course, Course.institution_id == Institution.id, isouter=True)
            .group_by(Institution.short_name)
            .order_by(Institution.short_name)
        )

    return StatsPayload(
        institutions=int(institutions or 0),
        courses=int(courses or 0),
        articulations=int(articulations or 0),
        embedded_courses=int(embedded_courses or 0),
        last_successful_scrape_run=last_successful.isoformat() if last_successful else None,
        courses_per_institution={name: int(count or 0) for name, count in per_institution_rows},
    )
