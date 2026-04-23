from __future__ import annotations

from typing import Literal
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import text

from db.session import async_engine

EXPLANATION_CACHE: dict[tuple[UUID, UUID], str] = {}


class CourseSchema(BaseModel):
    id: UUID
    institution_id: UUID
    institution_short_name: str
    institution_name: str
    subject_code: str
    code: str
    title: str
    description: str
    units: float | None = None


class CourseMatch(BaseModel):
    target_course_id: UUID
    target_course: CourseSchema
    similarity_score: float
    match_type: Literal["OFFICIAL", "SEMANTIC", "NONE"]
    articulation_id: UUID | None
    agreement_year: int | None = None
    explanation: str | None


class MatchResult(BaseModel):
    source_course_id: UUID
    source_course: CourseSchema
    matches: list[CourseMatch]


async def generate_explanation(source_course: CourseSchema, target_course: CourseSchema) -> str:
    cache_key = (source_course.id, target_course.id)
    if cache_key in EXPLANATION_CACHE:
        return EXPLANATION_CACHE[cache_key]

    client = AsyncOpenAI()
    prompt = (
        "In one sentence, explain why these two courses are likely equivalent for transfer credit purposes. "
        f"Course A: {source_course.title} — {source_course.description[:300]}. "
        f"Course B: {target_course.title} — {target_course.description[:300]}."
    )
    response = await client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        max_output_tokens=80,
    )
    await client.close()
    explanation = (response.output_text or "").strip()
    EXPLANATION_CACHE[cache_key] = explanation
    return explanation


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(format(value, ".10f") for value in values) + "]"


async def fetch_source_bundle(source_course_id: UUID) -> tuple[CourseSchema, list[float]]:
    query = text(
        """
        SELECT
          c.id,
          c.institution_id,
          i.short_name AS institution_short_name,
          i.name AS institution_name,
          s.code AS subject_code,
          c.code,
          c.title,
          c.description,
          c.units,
          ce.embedding::text AS embedding
        FROM courses c
        JOIN subjects s ON s.id = c.subject_id
        JOIN institutions i ON i.id = c.institution_id
        JOIN course_embeddings ce ON ce.course_id = c.id
        WHERE c.id = :course_id
        """
    )
    async with async_engine.connect() as connection:
        row = (await connection.execute(query, {"course_id": source_course_id})).mappings().first()

    if row is None:
        raise ValueError(f"Source course {source_course_id} is missing a course or embedding row")

    embedding = [float(value) for value in row["embedding"].strip("[]").split(",") if value]
    course = CourseSchema(
        id=row["id"],
        institution_id=row["institution_id"],
        institution_short_name=row["institution_short_name"],
        institution_name=row["institution_name"],
        subject_code=row["subject_code"],
        code=row["code"],
        title=row["title"],
        description=row["description"],
        units=float(row["units"]) if row["units"] is not None else None,
    )
    return course, embedding


async def fetch_candidate_matches(
    *,
    source_course_id: UUID,
    target_institution_id: UUID,
    query_vector: list[float],
    top_k: int,
    excluded_target_course_ids: list[UUID],
) -> list[dict]:
    sql = text(
        """
        SELECT
          c.id,
          c.institution_id,
          i.short_name AS institution_short_name,
          i.name AS institution_name,
          s.code AS subject_code,
          c.code,
          c.title,
          c.description,
          c.units,
          1 - (ce.embedding <=> CAST(:query_vector AS vector)) AS similarity_score,
          a.id AS articulation_id,
          a.agreement_year
        FROM course_embeddings ce
        JOIN courses c ON c.id = ce.course_id
        JOIN subjects s ON s.id = c.subject_id
        JOIN institutions i ON i.id = c.institution_id
        LEFT JOIN articulations a
          ON a.from_course_id = :source_course_id
         AND a.to_course_id = c.id
        WHERE c.institution_id = :target_institution_id
          AND (
            :excluded_ids_empty
            OR c.id NOT IN (SELECT unnest(CAST(:excluded_target_course_ids AS uuid[])))
          )
        ORDER BY ce.embedding <=> CAST(:query_vector AS vector)
        LIMIT :top_k
        """
    )
    params = {
        "source_course_id": source_course_id,
        "target_institution_id": target_institution_id,
        "query_vector": vector_literal(query_vector),
        "top_k": top_k,
        "excluded_target_course_ids": excluded_target_course_ids,
        "excluded_ids_empty": len(excluded_target_course_ids) == 0,
    }
    async with async_engine.connect() as connection:
        rows = (await connection.execute(sql, params)).mappings().all()
    return [dict(row) for row in rows]


async def fetch_official_matches(
    *,
    source_course_id: UUID,
    target_institution_id: UUID,
    query_vector: list[float],
) -> list[dict]:
    sql = text(
        """
        SELECT
          c.id,
          c.institution_id,
          i.short_name AS institution_short_name,
          i.name AS institution_name,
          s.code AS subject_code,
          c.code,
          c.title,
          c.description,
          c.units,
          1 - (ce.embedding <=> CAST(:query_vector AS vector)) AS similarity_score,
          a.id AS articulation_id,
          a.agreement_year
        FROM articulations a
        JOIN courses c ON c.id = a.to_course_id
        JOIN course_embeddings ce ON ce.course_id = c.id
        JOIN subjects s ON s.id = c.subject_id
        JOIN institutions i ON i.id = c.institution_id
        WHERE a.from_course_id = :source_course_id
          AND c.institution_id = :target_institution_id
        ORDER BY ce.embedding <=> CAST(:query_vector AS vector)
        """
    )
    params = {
        "source_course_id": source_course_id,
        "target_institution_id": target_institution_id,
        "query_vector": vector_literal(query_vector),
    }
    async with async_engine.connect() as connection:
        rows = (await connection.execute(sql, params)).mappings().all()
    return [dict(row) for row in rows]


def build_course_schema(row: dict) -> CourseSchema:
    return CourseSchema(
        id=row["id"],
        institution_id=row["institution_id"],
        institution_short_name=row["institution_short_name"],
        institution_name=row["institution_name"],
        subject_code=row["subject_code"],
        code=row["code"],
        title=row["title"],
        description=row["description"],
        units=float(row["units"]) if row["units"] is not None else None,
    )


def sort_key(match: CourseMatch) -> tuple[int, float]:
    if match.match_type == "OFFICIAL":
        return (0, -match.similarity_score)
    if match.match_type == "SEMANTIC":
        return (1, -match.similarity_score)
    return (2, -match.similarity_score)


async def match_courses(
    source_course_ids: list[UUID],
    target_institution_id: UUID,
    top_k: int = 3,
    similarity_threshold: float = 0.82,
) -> list[MatchResult]:
    results: list[MatchResult] = []

    for source_course_id in source_course_ids:
        source_course, source_embedding = await fetch_source_bundle(source_course_id)
        official_rows = await fetch_official_matches(
            source_course_id=source_course_id,
            target_institution_id=target_institution_id,
            query_vector=source_embedding,
        )
        official_ids = [row["id"] for row in official_rows]
        candidate_rows = await fetch_candidate_matches(
            source_course_id=source_course_id,
            target_institution_id=target_institution_id,
            query_vector=source_embedding,
            top_k=top_k,
            excluded_target_course_ids=official_ids,
        )

        matches: list[CourseMatch] = []
        for row in official_rows + candidate_rows:
            target_course = build_course_schema(row)
            score = max(0.0, min(1.0, float(row["similarity_score"] or 0.0)))
            articulation_id = row["articulation_id"]
            agreement_year = row.get("agreement_year")
            explanation: str | None = None

            if articulation_id is not None:
                match_type: Literal["OFFICIAL", "SEMANTIC", "NONE"] = "OFFICIAL"
            elif score >= similarity_threshold:
                match_type = "SEMANTIC"
                explanation = await generate_explanation(source_course, target_course)
            else:
                match_type = "NONE"

            matches.append(
                CourseMatch(
                    target_course_id=target_course.id,
                    target_course=target_course,
                    similarity_score=score,
                    match_type=match_type,
                    articulation_id=articulation_id,
                    agreement_year=agreement_year,
                    explanation=explanation,
                )
            )

        matches.sort(key=sort_key)
        results.append(
            MatchResult(
                source_course_id=source_course_id,
                source_course=source_course,
                matches=matches,
            )
        )

    return results
