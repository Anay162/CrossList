from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InstitutionKind(str, Enum):
    CC = "CC"
    UC = "UC"
    CSU = "CSU"
    OTHER = "OTHER"


class ArticulationType(str, Enum):
    DIRECT = "DIRECT"
    SERIES = "SERIES"
    OR_GROUP = "OR_GROUP"
    OTHER = "OTHER"


class ScrapeRunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[InstitutionKind] = mapped_column(
        SqlEnum(InstitutionKind, name="institution_kind"),
        nullable=False,
    )
    catalog_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("institution_id", "subject_id", "code", name="uq_courses_institution_subject_code"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    institution_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    units: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    raw_html: Mapped[str | None] = mapped_column(Text)
    catalog_url: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class CourseEmbedding(Base):
    __tablename__ = "course_embeddings"

    course_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    embedded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Articulation(Base):
    __tablename__ = "articulations"
    __table_args__ = (
        Index("ix_articulations_from_course_id", "from_course_id"),
        Index("ix_articulations_to_course_id", "to_course_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    from_course_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_course_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    agreement_year: Mapped[int | None] = mapped_column(nullable=True)
    articulation_type: Mapped[ArticulationType] = mapped_column(
        SqlEnum(ArticulationType, name="articulation_type"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ScrapeRunStatus] = mapped_column(
        SqlEnum(ScrapeRunStatus, name="scrape_run_status"),
        nullable=False,
    )
    stats: Mapped[dict | None] = mapped_column(JSONB)
