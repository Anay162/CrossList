from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from .base import CatalogScraper, first_decimal, normalize_whitespace
from .models import RawCourse, ScrapedSubject

LOGGER = logging.getLogger("crosslist.scrapers.sjsu")


class SJSUScraper(CatalogScraper):
    institution_slug = "sjsu"
    institution_name = "SJSU"
    COURSE_DESCRIPTIONS_URL = "https://catalog.sjsu.edu/content.php"

    SUBJECTS = {
        "MATH": "Mathematics",
        "CS": "Computer Science",
        "ENGL": "English",
        "PSYC": "Psychology",
    }

    async def list_subjects(self) -> list[ScrapedSubject]:
        return [
            ScrapedSubject(code=code, name=name, catalog_url=self.COURSE_DESCRIPTIONS_URL)
            for code, name in self.SUBJECTS.items()
        ]

    async def list_courses(self, subject: ScrapedSubject) -> list[RawCourse]:
        listing_html = await self.fetch_text(
            self.COURSE_DESCRIPTIONS_URL,
            params={
                "catoid": "15",
                "navoid": "5382",
                "filter[item_type]": "3",
                "filter[only_active]": "1",
                "filter[3]": "1",
                "filter[cpage]": "1",
                "cur_cat_oid": "15",
                "expand": "1",
                "search_database": "Filter",
                "filter[exact_match]": "1",
                "filter[27]": subject.code,
            },
        )
        root = HTMLParser(listing_html)
        links = []
        seen_links: set[str] = set()
        for anchor in root.css("a[href*='preview_course_nopop.php']"):
            href = anchor.attributes.get("href")
            if not href or href in seen_links:
                continue
            seen_links.add(href)
            links.append(urljoin("https://catalog.sjsu.edu/", href))

        courses: list[RawCourse] = []
        for link in links:
            detail_html = await self.fetch_text(link)
            course = self._parse_course_detail(subject, detail_html, link)
            if course is not None:
                courses.append(course)

        found = len(links)
        if not courses:
            courses = self.heuristic_courses_from_page(html=listing_html, subject=subject, catalog_url=str(self.COURSE_DESCRIPTIONS_URL))
            found = max(found, len(courses))

        deduped = self.dedupe_courses(courses)
        self.log_counts(subject, found, len(deduped))
        return deduped

    def _parse_course_detail(self, subject: ScrapedSubject, html: str, catalog_url: str) -> RawCourse | None:
        root = HTMLParser(html)
        title_text = ""
        for selector in ("#course_preview_title", "h1", "title"):
            node = root.css_first(selector)
            if node is not None:
                title_text = normalize_whitespace(node.text())
                if title_text:
                    break

        match = re.search(rf"{subject.code}\s+([A-Z0-9][A-Z0-9\-]*)\s*-\s*(.+)", title_text, re.IGNORECASE)
        if not match:
            return None

        course_code, title = match.groups()
        body_text = normalize_whitespace(root.body.text(separator=" ", strip=True) if root.body else root.text())
        units_match = re.search(r"(\d+(?:\.\d+)?)\s+Units?", body_text, re.IGNORECASE)
        description = self._extract_description(body_text, title)

        return self.coerce_course(
            subject_code=subject.code,
            course_code=course_code,
            title=title,
            units=None if not units_match else first_decimal(units_match.group(1)),
            description=description,
            raw_html=root.body.html if root.body is not None else html,
            catalog_url=catalog_url,
        )

    def _extract_description(self, page_text: str, title: str) -> str:
        page_text = page_text.replace("opens a new window", "")
        parts = page_text.split(title, 1)
        if len(parts) == 2:
            candidate = parts[1]
        else:
            candidate = page_text

        for marker in ("Prerequisite", "Corequisite", "Repeatable", "Grading", "Typically Offered", "Misc/Lab"):
            if marker in candidate:
                candidate = candidate.split(marker, 1)[0]
        return normalize_whitespace(candidate)
