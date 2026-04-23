from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ScrapedSubject(BaseModel):
    code: str
    name: str
    catalog_url: str


class RawCourse(BaseModel):
    subject_code: str
    course_code: str
    title: str
    units: Decimal | None = None
    description: str
    raw_html: str
    catalog_url: str
    parser: Literal["primary", "heuristic"] = "primary"


class InstitutionConfig(BaseModel):
    name: str
    short_name: str
    kind: Literal["CC", "UC", "CSU", "OTHER"]
    catalog_url: str
