from __future__ import annotations

import logging
import re
from decimal import Decimal
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from .base import CatalogScraper, first_decimal, normalize_whitespace
from .models import RawCourse, ScrapedSubject

LOGGER = logging.getLogger("crosslist.scrapers.deanza")


class DeAnzaScraper(CatalogScraper):
    institution_slug = "deanza"
    institution_name = "De Anza"

    SUBJECTS = {
        "MATH": ("Mathematics", "https://www.deanza.edu/math/courses.html"),
        "CIS": ("Computer Information Systems", "https://www.deanza.edu/cis/courses.html"),
        "ENGL": ("English", "https://www.deanza.edu/english/courses.html"),
        "PSYC": ("Psychology", "https://www.deanza.edu/psychology/courses.html"),
    }

    async def list_subjects(self) -> list[ScrapedSubject]:
        return [
            ScrapedSubject(code=code, name=name, catalog_url=url)
            for code, (name, url) in self.SUBJECTS.items()
        ]

    async def list_courses(self, subject: ScrapedSubject) -> list[RawCourse]:
        try:
            html = await self.fetch_text(subject.catalog_url)
        except Exception as exc:
            LOGGER.warning("%s %s could not be fetched from %s: %s", self.institution_name, subject.code, subject.catalog_url, exc)
            return []
        if "Cloudflare" in html and "Sorry, you have been blocked" in html:
            LOGGER.warning("%s %s is blocked by Cloudflare; no courses collected from %s", self.institution_name, subject.code, subject.catalog_url)
            return []

        root = HTMLParser(html)
        table_rows = root.css("table tr")
        courses: list[RawCourse] = []
        found = 0

        for row in table_rows:
            columns = [normalize_whitespace(cell.text()) for cell in row.css("td")]
            if len(columns) < 3:
                continue
            raw_code, title, raw_units = columns[:3]
            match = re.match(r"([A-Z]+)\s+([A-Z0-9]+[A-Z0-9\-]*)$", raw_code)
            if not match:
                continue

            prefix, course_code = match.groups()
            if subject.code == "ENGL":
                allowed_prefixes = {"ENGL", "EWRT", "ELIT", "LING"}
                if prefix not in allowed_prefixes:
                    continue
            elif prefix != subject.code:
                continue

            found += 1

            # De Anza department pages are official catalog-derived inventories but often omit
            # descriptions. We keep only rows whose descriptions can be discovered on-page.
            description = self._description_from_department_page(root, raw_code)
            course = self.coerce_course(
                subject_code=prefix if subject.code == "ENGL" else subject.code,
                course_code=course_code,
                title=title,
                units=first_decimal(raw_units),
                description=description,
                raw_html=row.html,
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

    def _description_from_department_page(self, root: HTMLParser, course_label: str) -> str:
        return ""
