#!/usr/bin/env sh
set -e

# Apply database migrations (idempotent), then start the API bound to the
# platform-provided port ($PORT on Render; defaults to 8000 locally).
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
