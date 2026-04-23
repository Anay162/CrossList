# CrossList

CrossList is a transfer-credit discovery app for community college students who need clearer paths into four-year universities. It combines official articulation data with evidence-backed semantic matching so students can spot both guaranteed equivalents and strong likely matches that other tools miss.

## Quick start

1. Start PostgreSQL with pgvector:

   ```bash
   docker compose -f infra/docker-compose.yml up -d
   ```

2. Start the FastAPI backend:

   ```bash
   cd apps/api
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   uvicorn app.main:app --reload
   ```

3. Start the Next.js frontend in a second terminal:

   ```bash
   cd apps/web
   npm install
   npm run dev
   ```

## Decisions we made

- We used `npm` for the web app because it was already available locally and kept the scaffold simple.
- We used `uv`-style project metadata in `apps/api/pyproject.toml`, while keeping `pip install -e .` as the lowest-friction local bootstrap path.
- We exposed PostgreSQL on port `5433` to avoid common local conflicts with existing database instances on `5432`.

## Phase 3 Status

- Matching threshold used in the UI: `0.60`. We kept the backend matcher default at `0.82`, but lowered the UI request threshold because the Phase 2 catalog-only embeddings produced no semantic demo matches at `0.82`. At `0.60`, the current seed dataset surfaces a small number of plausible yellow matches without turning the whole result set yellow.
- OFFICIAL cases verified: `SMC MATH 7 -> UC Davis MAT 021A`, `SMC MATH 10 -> UC Davis ECS 020`, `SMC CS 55 -> UC Davis ECS 032A`.
- SEMANTIC cases verified at the UI threshold: `SMC ENGL 1D -> UC Davis ENL 145`, `SMC PSYCH 11 -> UC Davis PSC 142`.
- NONE cases verified: lower-ranked UC Davis alternatives for the official math/computer science matches, plus the non-top English and psychology alternatives below the UI threshold.
- Known limitations:
  - The demo accepts `SMC ENGL 1` and `SMC PSYCH 1` as user input, but these are normalized to `ENGL 1D` and `PSYCH 11` because the scoped SMC catalog snapshot does not contain literal `ENGL 1` or `PSYCH 1` rows.
  - Semantic explanations are cached only in process memory, so restarting the API clears the explanation cache.
  - The semantic threshold is tuned for the current three-school, four-subject demo corpus and is not yet calibrated for broader catalogs.
  - The PDF comparison report is intentionally minimal and does not represent an official articulation decision.
- Estimated OpenAI budget used so far: about `$0.002` total. Most of that was the full `text-embedding-3-small` pass for `975` courses, with a much smaller amount from a handful of `gpt-4o-mini` semantic explanation calls during Phase 3 verification. Pricing reference: `text-embedding-3-small` at `$0.02 / 1M tokens`, `gpt-4o-mini` at `$0.15 / 1M input tokens` and `$0.60 / 1M output tokens` on OpenAI's pricing/docs pages.
