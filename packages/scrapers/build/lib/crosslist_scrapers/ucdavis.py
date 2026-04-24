from __future__ import annotations

import logging

from selectolax.parser import HTMLParser, Node

from .base import CatalogScraper, first_decimal, normalize_whitespace
from .models import RawCourse, ScrapedSubject

LOGGER = logging.getLogger("crosslist.scrapers.ucdavis")


class UCDavisScraper(CatalogScraper):
    institution_slug = "ucdavis"
    institution_name = "UC Davis"
    SUBJECT_URL_TEMPLATE = "https://catalog.ucdavis.edu/courses-subject-code/{subject_code}/"

    SUBJECTS = {
        "MAT": "Mathematics",
        "ECS": "Engineering Computer Science",
        "ENL": "English",
        "PSC": "Psychology",
    }

    async def list_subjects(self) -> list[ScrapedSubject]:
        return [
            ScrapedSubject(
                code=code,
                name=name,
                catalog_url=self.SUBJECT_URL_TEMPLATE.format(subject_code=code.lower()),
            )
            for code, name in self.SUBJECTS.items()
        ]

    async def list_courses(self, subject: ScrapedSubject) -> list[RawCourse]:
        html = await self.fetch_text(subject.catalog_url)
        root = HTMLParser(html)
        blocks = root.css(".courseblock")
        courses = [course for block in blocks if (course := self._parse_course_block(block, subject)) is not None]
        deduped = self.dedupe_courses(courses)
        self.log_counts(subject, len(blocks), len(deduped))
        return deduped

    def _parse_course_block(self, block: Node, subject: ScrapedSubject) -> RawCourse | None:
        code_node = block.css_first(".detail-code")
        title_node = block.css_first(".detail-title")
        units_node = block.css_first(".detail-hours_html")
        description_node = block.css_first("p.courseblockextra")

        if code_node is None or title_node is None or description_node is None:
            return None

        full_code = normalize_whitespace(code_node.text())
        prefix = f"{subject.code} "
        if not full_code.startswith(prefix):
            return None

        course_code = full_code.removeprefix(prefix).strip()
        title = normalize_whitespace(title_node.text()).lstrip("—- ").strip()
        units = first_decimal(units_node.text()) if units_node is not None else None
        description = normalize_whitespace(description_node.text(separator=" ", strip=True))
        description = description.removeprefix("Course Description:").strip()

        return self.coerce_course(
            subject_code=subject.code,
            course_code=course_code,
            title=title,
            units=units,
            description=description,
            raw_html=block.html,
            catalog_url=subject.catalog_url,
        )
