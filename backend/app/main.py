"""FlowCare AI — FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    from app.seed import seed

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    logger.info("FlowCare AI %s started (env=%s, llm=%s)", __version__, settings.environment, settings.has_llm)
    yield


app = FastAPI(
    title=settings.project_name,
    version=__version__,
    description="Healthcare referral automation platform + workflow builder.",
    lifespan=lifespan,
)

_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Auth uses Authorization: Bearer (no cookies); "*" requires credentials off.
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["system"])
def root() -> dict:
    """Friendly landing for the API root (the UI lives on the frontend host)."""
    return {
        "service": settings.project_name,
        "version": __version__,
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "api": settings.api_v1_prefix,
    }


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "version": __version__, "llm_enabled": settings.has_llm}


@app.get("/metrics", tags=["system"])
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
