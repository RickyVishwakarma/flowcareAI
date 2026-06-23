"""Task / work-queue schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.base import TaskStatus


class TaskOut(BaseModel):
    id: str
    title: str
    description: str | None
    status: TaskStatus
    priority: str
    referral_id: str | None
    referral_reference: str | None
    assigned_to: str | None
    assignee_email: str | None
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "normal"
    referral_id: str | None = None


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    priority: str | None = None
