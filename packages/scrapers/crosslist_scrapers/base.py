from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import httpx
from selectolax.parser import HTMLParser

from .models import RawCourse, ScrapedSubject

LOGGER = logging.getLogger("crosslist.scrapers")
RETRY_DELAYS_SECONDS = (2, 4, 8)
ROOT_DIR = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT_DIR / "data" / "cache"


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def first_decimal(value: str) -> Decimal | None:
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    return Decimal(match.group(1))


def looks_like_course_heading(text: str, subject_code: str) -> bool:
    compact = normalize_whitespace(text).upper()
    return compact.startswith(f"{subject_code} ")


class CatalogScraper(ABC):
    institution_slug: str
    institution_name: str
    polite_delay_ms: int

    def __init__(self, *, force: bool = False, polite_delay_ms: int = 500) -> None:
        self.force = force
        self.polite_delay_ms = polite_delay_ms
        self._client: httpx.AsyncClient | None = None
        self._heuristic_hits: list[str] = []

    async def __aenter__(self) -> "CatalogScraper":
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            headers={"User-Agent": "CrossList/0.1 (+https://crosslist.local)"},
            timeout=httpx.Timeout(30.0),
        )
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Scraper client not initialized")
        return self._client

    @property
    def heuristic_hits(self) -> list[str]:
        return self._heuristic_hits

    async def fetch_text(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        cache_path = self._cache_path(url, params)
        if cache_path.exists() and not self.force:
            return cache_path.read_text()

        last_error: Exception | None = None
        for attempt, delay in enumerate(RETRY_DELAYS_SECONDS, start=1):
            try:
                response = await self.client.get(url, params=params, headers=headers)
                response.raise_for_status()
                text = response.text
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text)
                await asyncio.sleep(self.polite_delay_ms / 1000)
                return text
            except Exception as exc:  # pragma: no cover - exercised live
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError):
                    status_code = exc.response.status_code
                    if 400 <= status_code < 500 and status_code not in {408, 429}:
                        break
                if attempt == len(RETRY_DELAYS_SECONDS):
                    break
                LOGGER.warning("%s request failed for %s (attempt %s/%s): %s", self.institution_name, url, attempt, len(RETRY_DELAYS_SECONDS), exc)
                await asyncio.sleep(delay)

        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error

    def _cache_path(self, url: str, params: dict[str, str] | None) -> Path:
        payload = url if not params else f"{url}?{urlencode(sorted(params.items()))}"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return CACHE_DIR / self.institution_slug / f"{digest}.html"

    def log_counts(self, subject: ScrapedSubject, found: int, kept: int) -> None:
        skipped = found - kept
        LOGGER.info(
            "%s %s: found %s courses, kept %s (%s had no description)",
            self.institution_name,
            subject.code,
            found,
            kept,
            skipped,
        )

    def parse_course_heading(self, subject_code: str, text: str) -> tuple[str, str, Decimal | None] | None:
        cleaned = normalize_whitespace(text)
        pattern = re.compile(
            rf"^{re.escape(subject_code)}\s+([A-Z0-9][A-Z0-9\-]*)\s+(.+?)\s+(\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?)\s+Units?$",
            re.IGNORECASE,
        )
        match = pattern.match(cleaned)
        if match:
            return match.group(1), match.group(2), first_decimal(match.group(3))

        fallback = re.compile(rf"^{re.escape(subject_code)}\s+([A-Z0-9][A-Z0-9\-]*)\s+(.+)$", re.IGNORECASE)
        match = fallback.match(cleaned)
        if not match:
            return None
        return match.group(1), match.group(2), None

    def coerce_course(
        self,
        *,
        subject_code: str,
        course_code: str,
        title: str,
        units: Decimal | None,
        description: str,
        raw_html: str,
        catalog_url: str,
        parser: str = "primary",
    ) -> RawCourse | None:
        description = normalize_whitespace(description)
        if not description:
            return None

        return RawCourse(
            subject_code=subject_code,
            course_code=normalize_whitespace(course_code),
            title=normalize_whitespace(title),
            units=units,
            description=description,
            raw_html=raw_html,
            catalog_url=catalog_url,
            parser=parser,  # type: ignore[arg-type]
        )

    def heuristic_courses_from_page(
        self,
        *,
        html: str,
        subject: ScrapedSubject,
        catalog_url: str,
    ) -> list[RawCourse]:
        root = HTMLParser(html)
        courses: list[RawCourse] = []
        nodes = root.css("h1, h2, h3, h4")

        for node in nodes:
            heading = normalize_whitespace(node.text())
            if not looks_like_course_heading(heading, subject.code):
                continue

            parsed = self.parse_course_heading(subject.code, heading)
            if not parsed:
                continue

            course_code, title, units = parsed
            description_chunks: list[str] = []
            sibling = node.next
            while sibling is not None:
                if sibling.tag in {"h1", "h2", "h3", "h4"}:
                    break
                text = normalize_whitespace(sibling.text(deep=True))
                if text and "units" not in text.lower():
                    description_chunks.append(text)
                sibling = sibling.next

            course = self.coerce_course(
                subject_code=subject.code,
                course_code=course_code,
                title=title,
                units=units,
                description=" ".join(description_chunks),
                raw_html=node.html,
                catalog_url=catalog_url,
                parser="heuristic",
            )
            if course is not None:
                self._heuristic_hits.append(f"{subject.code} {course_code}")
                courses.append(course)

        return courses

    def dedupe_courses(self, courses: Iterable[RawCourse]) -> list[RawCourse]:
        deduped: dict[tuple[str, str], RawCourse] = {}
        for course in courses:
            deduped[(course.subject_code, course.course_code)] = course
        return list(deduped.values())

    @abstractmethod
    async def list_subjects(self) -> list[ScrapedSubject]:
        raise NotImplementedError

    @abstractmethod
    async def list_courses(self, subject: ScrapedSubject) -> list[RawCourse]:
        raise NotImplementedError
