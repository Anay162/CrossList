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
