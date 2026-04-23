from fastapi import FastAPI
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.stats import fetch_stats
from db.session import async_engine


class MatchRequest(BaseModel):
    source_course_id: str
    target_institution_id: str


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
def match_courses(payload: MatchRequest) -> dict[str, object]:
    _ = payload
    return {"matches": [], "phase": 1, "message": "not implemented"}


@app.get("/api/stats")
async def stats() -> dict[str, object]:
    try:
        return (await fetch_stats()).as_dict()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"stats unavailable: {exc}") from exc
