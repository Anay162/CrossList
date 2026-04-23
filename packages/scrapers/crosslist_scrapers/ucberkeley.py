from __future__ import annotations

import logging
from selectolax.parser import HTMLParser

from .base import CatalogScraper, normalize_whitespace
from .models import RawCourse, ScrapedSubject

LOGGER = logging.getLogger("crosslist.scrapers.ucberkeley")


class UCBerkeleyScraper(CatalogScraper):
    institution_slug = "ucberkeley"
    institution_name = "UC Berkeley"

    SUBJECTS = {
        "MATH": ("Mathematics", "https://guide.berkeley.edu/courses/math/"),
        "COMPSCI": ("Computer Science", "https://undergraduate.catalog.berkeley.edu/courses?subject=COMPSCI"),
        "ENGLISH": ("English", "https://guide.berkeley.edu/courses/english/"),
        "PSYCH": ("Psychology", "https://guide.berkeley.edu/courses/psych/"),
    }

    async def list_subjects(self) -> list[ScrapedSubject]:
        return [
            ScrapedSubject(code=code, name=name, catalog_url=url)
            for code, (name, url) in self.SUBJECTS.items()
        ]

    async def list_courses(self, subject: ScrapedSubject) -> list[RawCourse]:
        html = await self.fetch_text(subject.catalog_url)
        root = HTMLParser(html)
        courses: list[RawCourse] = []
        found = 0

        heading_nodes = root.css("h3, h4")
        for node in heading_nodes:
            heading_text = normalize_whitespace(node.text())
            parsed = self.parse_course_heading(subject.code, heading_text)
            if not parsed:
                continue

            found += 1
            course_code, title, units = parsed
            description_parts: list[str] = []
            sibling = node.next
            while sibling is not None:
                if sibling.tag in {"h3", "h4"}:
                    break
                text = normalize_whitespace(sibling.text(deep=True))
                if text and not text.lower().startswith("expand all") and "collapse all" not in text.lower():
                    description_parts.append(text)
                sibling = sibling.next

            course = self.coerce_course(
                subject_code=subject.code,
                course_code=course_code,
                title=title,
                units=units,
                description=" ".join(description_parts),
                raw_html=node.html,
                catalog_url=subject.catalog_url,
            )
            if course is not None:
                courses.append(course)

        if not courses:
            courses = self.heuristic_courses_from_page(html=html, subject=subject, catalog_url=subject.catalog_url)
            found = max(found, len(courses))

        deduped = self.dedupe_courses(courses)
        self.log_counts(subject, found, len(deduped))
        return deduped
