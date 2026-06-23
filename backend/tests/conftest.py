"""Test fixtures: in-memory-ish SQLite DB + eager Celery + FastAPI TestClient."""
from __future__ import annotations

import os
import tempfile

import pytest

# Configure environment BEFORE importing the app so settings pick it up.
_tmp_db = os.path.join(tempfile.gettempdir(), "flowcare_test.db")
if os.path.exists(_tmp_db):
    os.remove(_tmp_db)
os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{_tmp_db}"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ["ENVIRONMENT"] = "test"
os.environ["STORAGE_LOCAL_DIR"] = os.path.join(tempfile.gettempdir(), "flowcare_uploads")
os.environ.setdefault("ANTHROPIC_API_KEY", "")  # force template extractor
# A 32+ byte key keeps PyJWT's HMAC length check quiet in tests.
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
