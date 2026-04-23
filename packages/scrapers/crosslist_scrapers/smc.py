from __future__ import annotations

import logging
import re

from selectolax.parser import HTMLParser, Node

from .base import CatalogScraper, first_decimal, normalize_whitespace
from .models import RawCourse, ScrapedSubject

LOGGER = logging.getLogger("crosslist.scrapers.smc")


class SMCScraper(CatalogScraper):
    institution_slug = "smc"
    institution_name = "SMC"
    COURSE_FINDER_URL = "https://catalog.smc.edu/current/courses/course-finder.php"
    TOTAL_PAGES = 97

    SUBJECTS = {
        "MATH": "Mathematics",
        "CS": "Computer Science",
        "ENGL": "English",
        "PSYCH": "Psychology",
    }

    async def list_subjects(self) -> list[ScrapedSubject]:
        return [
            ScrapedSubject(code=code, name=name, catalog_url=self.COURSE_FINDER_URL)
            for code, name in self.SUBJECTS.items()
        ]

    async def list_courses(self, subject: ScrapedSubject) -> list[RawCourse]:
        courses: list[RawCourse] = []
        found = 0

        for page in range(1, self.TOTAL_PAGES + 1):
            page_url = f"{self.COURSE_FINDER_URL}?page={page}"
            html = await self.fetch_text(self.COURSE_FINDER_URL, params={"page": str(page)})
            root = HTMLParser(html)

            for row in root.css('tr[role="row"]'):
                parsed = self._parse_row(row, subject, page_url)
                if parsed is None:
                    continue
                found += 1
                courses.append(parsed)

        deduped = self.dedupe_courses(courses)
        self.log_counts(subject, found, len(deduped))
        return deduped

    def _parse_row(self, row: Node, subject: ScrapedSubject, page_url: str) -> RawCourse | None:
        code_node = row.css_first(".type")
        title_node = row.css_first("h2")
        if code_node is None or title_node is None:
            return None

        code_text = normalize_whitespace(code_node.text())
        match = re.match(r"^([A-Z&]+)\s+(.+)$", code_text)
        if not match:
            return None

        subject_code, course_code = match.groups()
        if subject_code != subject.code:
            return None

        units_node = row.css_first(".units-qty")
        units = first_decimal(units_node.text()) if units_node is not None else None
        description = self._extract_description(row)

        return self.coerce_course(
            subject_code=subject.code,
            course_code=course_code,
            title=title_node.text(strip=True),
            units=units,
            description=description,
            raw_html=row.html,
            catalog_url=page_url,
        )

    def _extract_description(self, row: Node) -> str:
        paragraphs = [normalize_whitespace(node.text(separator=" ", strip=True)) for node in row.css("td p")]
        paragraphs = [text for text in paragraphs if text]
        if not paragraphs:
            return ""

        for text in reversed(paragraphs):
            lowered = text.lower()
            if lowered.startswith("c-id:") or lowered.startswith("transfer:"):
                continue
            return text

        return paragraphs[-1]
