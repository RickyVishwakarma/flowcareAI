"""Operations dashboard endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.organization import User
from app.schemas.dashboard import DashboardStats
from app.services import analytics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardStats)
def overview(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DashboardStats:
    return DashboardStats(**analytics.overview(db, user.organization_id))
