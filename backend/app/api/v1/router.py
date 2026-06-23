"""Aggregate v1 router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, dashboard, operations, referrals, review, tasks, workflows

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(referrals.router)
api_router.include_router(review.router)
api_router.include_router(workflows.router)
api_router.include_router(operations.router)
api_router.include_router(dashboard.router)
api_router.include_router(tasks.router)
