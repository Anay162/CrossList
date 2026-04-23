"""initial crosslist schema

Revision ID: 20260423_0001
Revises:
Create Date: 2026-04-23 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "20260423_0001"
down_revision = None
branch_labels = None
depends_on = None


institution_kind = sa.Enum("CC", "UC", "CSU", "OTHER", name="institution_kind")
articulation_type = sa.Enum("DIRECT", "SERIES", "OR_GROUP", "OTHER", name="articulation_type")
scrape_run_status = sa.Enum("SUCCESS", "PARTIAL", "FAILED", name="scrape_run_status")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    institution_kind.create(op.get_bind(), checkfirst=True)
    articulation_type.create(op.get_bind(), checkfirst=True)
    scrape_run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "institutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.Text(), nullable=False),
        sa.Column("kind", institution_kind, nullable=False),
        sa.Column("catalog_url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scrape_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", scrape_run_status, nullable=False),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "subjects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("units", sa.Numeric(5, 2), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("raw_html", sa.Text(), nullable=True),
        sa.Column("catalog_url", sa.Text(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id", "subject_id", "code", name="uq_courses_institution_subject_code"),
    )
    op.create_table(
        "articulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("agreement_year", sa.Integer(), nullable=True),
        sa.Column("articulation_type", articulation_type, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["from_course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_articulations_from_course_id", "articulations", ["from_course_id"], unique=False)
    op.create_index("ix_articulations_to_course_id", "articulations", ["to_course_id"], unique=False)
    op.create_table(
        "course_embeddings",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(dim=1536), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("embedded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("course_id"),
    )


def downgrade() -> None:
    op.drop_table("course_embeddings")
    op.drop_index("ix_articulations_to_course_id", table_name="articulations")
    op.drop_index("ix_articulations_from_course_id", table_name="articulations")
    op.drop_table("articulations")
    op.drop_table("courses")
    op.drop_table("subjects")
    op.drop_table("scrape_runs")
    op.drop_table("institutions")

    scrape_run_status.drop(op.get_bind(), checkfirst=True)
    articulation_type.drop(op.get_bind(), checkfirst=True)
    institution_kind.drop(op.get_bind(), checkfirst=True)
