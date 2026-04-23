from __future__ import annotations

from uuid import UUID
from io import BytesIO

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from sqlalchemy import text

from app.stats import fetch_stats
from db.session import async_engine
from matching import (
    MatchResult,
    fetch_course_schema,
    fetch_pair_similarity,
    generate_explanation,
    match_courses,
)

INSTITUTION_ALIASES = {
    "SMC": "SMC",
    "SJSU": "SJSU",
    "UCD": "UC Davis",
    "UC DAVIS": "UC Davis",
}


class MatchRequest(BaseModel):
    source_course_id: str
    target_institution_id: str


class SourceCourseInput(BaseModel):
    institution_short_name: str
    course_code: str


class ApiMatchRequest(BaseModel):
    source_courses: list[SourceCourseInput]
    target_institution_short_name: str
    similarity_threshold: float = 0.82


class InstitutionResponse(BaseModel):
    id: UUID
    name: str
    short_name: str
    kind: str


class MatchReportRequest(BaseModel):
    source_course_id: UUID
    target_course_id: UUID


app = FastAPI(title="CrossList API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "crosslist-api"}


@app.get("/health/db")
async def health_db() -> dict[str, object]:
    try:
        async with async_engine.connect() as connection:
            extension_present = await connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc}") from exc

    return {"db": "ok", "pgvector": bool(extension_present)}


@app.post("/courses/match")
def legacy_match_courses(payload: MatchRequest) -> dict[str, object]:
    _ = payload
    return {"matches": [], "phase": 1, "message": "not implemented"}


@app.get("/api/stats")
async def stats() -> dict[str, object]:
    try:
        return (await fetch_stats()).as_dict()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"stats unavailable: {exc}") from exc


@app.get("/api/institutions", response_model=list[InstitutionResponse])
async def institutions() -> list[InstitutionResponse]:
    query = text("SELECT id, name, short_name, kind::text AS kind FROM institutions ORDER BY kind, short_name")
    async with async_engine.connect() as connection:
        rows = (await connection.execute(query)).mappings().all()
    return [InstitutionResponse(**row) for row in rows]


def normalize_institution_short_name(value: str) -> str:
    normalized = value.strip().upper()
    return INSTITUTION_ALIASES.get(normalized, value.strip())


def split_course_code(value: str) -> tuple[str, str]:
    parts = value.strip().split(None, 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail=f"Invalid course code '{value}'. Use format like 'MATH 7'.")
    return parts[0].upper(), parts[1].strip()


async def resolve_institution_id(short_name: str) -> UUID:
    query = text("SELECT id FROM institutions WHERE short_name = :short_name")
    async with async_engine.connect() as connection:
        institution_id = await connection.scalar(
            query,
            {"short_name": normalize_institution_short_name(short_name)},
        )
    if institution_id is None:
        raise HTTPException(status_code=400, detail=f"Institution '{short_name}' was not found.")
    return institution_id


async def resolve_source_course_id(institution_short_name: str, course_code: str) -> UUID:
    subject_code, number = split_course_code(course_code)
    query = text(
        """
        SELECT c.id
        FROM courses c
        JOIN subjects s ON s.id = c.subject_id
        JOIN institutions i ON i.id = c.institution_id
        WHERE i.short_name = :institution_short_name
          AND s.code = :subject_code
          AND c.code = :course_number
        """
    )
    params = {
        "institution_short_name": normalize_institution_short_name(institution_short_name),
        "subject_code": subject_code,
        "course_number": number,
    }
    async with async_engine.connect() as connection:
        course_id = await connection.scalar(query, params)
    if course_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"Course '{course_code}' was not found for institution '{institution_short_name}'.",
        )
    return course_id


@app.post("/api/match", response_model=list[MatchResult])
async def api_match(payload: ApiMatchRequest) -> list[MatchResult]:
    source_course_ids = [
        await resolve_source_course_id(item.institution_short_name, item.course_code)
        for item in payload.source_courses
    ]
    target_institution_id = await resolve_institution_id(payload.target_institution_short_name)
    return await match_courses(
        source_course_ids=source_course_ids,
        target_institution_id=target_institution_id,
        similarity_threshold=payload.similarity_threshold,
    )


def wrap_text(pdf: canvas.Canvas, text_value: str, x: float, y: float, width: float, leading: float = 14) -> float:
    current_y = y
    for paragraph in text_value.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            current_y -= leading
            continue
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if pdf.stringWidth(test_line, "Helvetica", 10) <= width:
                line = test_line
            else:
                pdf.drawString(x, current_y, line)
                current_y -= leading
                line = word
        if line:
            pdf.drawString(x, current_y, line)
            current_y -= leading
    return current_y


@app.post("/api/match/report")
async def match_report(payload: MatchReportRequest) -> StreamingResponse:
    source_course = await fetch_course_schema(payload.source_course_id)
    target_course = await fetch_course_schema(payload.target_course_id)
    similarity_score = await fetch_pair_similarity(payload.source_course_id, payload.target_course_id)
    explanation = await generate_explanation(source_course, target_course)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 0.75 * inch
    cursor = height - margin

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, cursor, "CrossList Transfer Credit Comparison")
    cursor -= 28

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, cursor, "Section 1: Source Course")
    cursor -= 18
    pdf.setFont("Helvetica", 10)
    cursor = wrap_text(
        pdf,
        (
            f"{source_course.institution_name}\n"
            f"{source_course.subject_code} {source_course.code} — {source_course.title}\n"
            f"Units: {source_course.units if source_course.units is not None else 'N/A'}\n"
            f"{source_course.description}"
        ),
        margin,
        cursor,
        width - 2 * margin,
    )
    cursor -= 10

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, cursor, "Section 2: Target Course")
    cursor -= 18
    pdf.setFont("Helvetica", 10)
    cursor = wrap_text(
        pdf,
        (
            f"{target_course.institution_name}\n"
            f"{target_course.subject_code} {target_course.code} — {target_course.title}\n"
            f"Units: {target_course.units if target_course.units is not None else 'N/A'}\n"
            f"{target_course.description}"
        ),
        margin,
        cursor,
        width - 2 * margin,
    )
    cursor -= 10

    if cursor < 2 * inch:
        pdf.showPage()
        cursor = height - margin

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, cursor, "Section 3: Similarity Analysis")
    cursor -= 18
    pdf.setFont("Helvetica", 10)
    cursor = wrap_text(
        pdf,
        (
            f"Similarity score: {round(similarity_score * 100)}%\n"
            f"AI explanation: {explanation}"
        ),
        margin,
        cursor,
        width - 2 * margin,
    )
    cursor -= 20

    pdf.setFont("Helvetica", 9)
    wrap_text(
        pdf,
        (
            "This report was generated by CrossList on 2026-04-23. "
            "It is intended to support a petition to your registrar and does not "
            "constitute an official articulation agreement."
        ),
        margin,
        max(cursor, margin + 40),
        width - 2 * margin,
        leading=12,
    )

    pdf.save()
    buffer.seek(0)
    filename = f"crosslist_{source_course.subject_code}_{source_course.code}_{target_course.subject_code}_{target_course.code}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
