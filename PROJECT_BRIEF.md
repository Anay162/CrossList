# CrossList — Project Brief

## What it is
CrossList helps community college students discover transfer-credit 
equivalencies at 4-year universities — including equivalencies that are 
NOT yet in any official articulation agreement — by using semantic 
similarity over public course catalog descriptions and syllabi.

## The gap we're filling
Existing tools (Transferology, ASSIST.org, CourseWise, EdVisorly, 
TransferAI.app) only show pre-articulated equivalencies that faculty have 
already manually approved. If your course isn't in a prior agreement, 
every tool says "no match" — even when the course is 95% the same content. 
CrossList is the only consumer tool that surfaces LIKELY equivalencies 
for UNARTICULATED courses, using embedding similarity over public catalog 
data. Users then take those matches to their registrar as evidence for 
petitions.

## Demo scope for v1
California Community Colleges ←→ UC + CSU system. 
Ground truth: ASSIST.org official articulations (validates our matches). 
Seed institutions: De Anza College (CC), UC Berkeley (UC), San Jose State 
University (CSU). 
Seed subjects: MATH, Computer Science (CIS/CS/CSCI), ENGL, PSYCH.

## North-star demo (3-min pitch)
Student uploads transcript from a California CC, picks a target university 
+ major, sees every course labeled:
- Green: official articulation from ASSIST (guaranteed to transfer)
- Yellow: semantic match not in ASSIST (likely — here's the evidence, 
  here's the registrar petition packet)
- Red: no match found

## Judging criteria we're optimizing
Clarity, usefulness, creativity, execution, usability. 
(Handshake × OpenAI Codex Creator Challenge.)

## Tech stack (locked)
- Frontend: Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui, Vercel
- Backend: FastAPI (Python 3.11), SQLAlchemy 2.x async, asyncpg
- Database: Postgres 16 + pgvector (Docker locally, port 5433)
- Migrations: Alembic
- Scrapers: httpx + selectolax, Pydantic v2 models, file cache at data/cache/
- ML: OpenAI text-embedding-3-small (1536-dim), gpt-4o-mini for text gen
- Package manager (Python): uv
- Repo layout: monorepo with apps/web, apps/api, packages/scrapers, 
  infra/, data/ (gitignored)

## Build phases
- Phase 1 (DONE): monorepo scaffold, Next.js landing page, FastAPI /health
- Phase 2 (IN PROGRESS): DB schema → scrapers → ASSIST → embeddings → CLI
- Phase 3: matching algorithm, transcript upload, match UI
- Phase 4: appeal-packet generation, polish, demo video

## Scope discipline
Resist building for all 114 CCCs or all UCs. Three institutions, four 
subjects, ~300 total courses. The architecture should be clean but the 
data is scoped. Every feature beyond what's needed for the 3-min demo 
is Phase 4 or later.