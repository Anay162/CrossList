FROM python:3.11-slim

WORKDIR /app

COPY packages/scrapers /app/packages/scrapers
COPY apps/api /app/apps/api

RUN python -m ensurepip --upgrade && \
    python -m pip install --upgrade pip && \
    python -m pip install -e /app/packages/scrapers -e /app/apps/api

WORKDIR /app/apps/api

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
