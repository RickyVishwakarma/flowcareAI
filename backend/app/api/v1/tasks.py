"""Task inbox / work queue.

Workflows create tasks via the `create_task` action; staff triage them here —
filter, claim (assign to self), change status, and jump to the source referral.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.base import TaskStatus
from app.models.operations import Task
from app.models.organization import User
from app.models.referral import Referral
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services import audit

router = APIRouter(prefix="/tasks", tags=["tasks"])

_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def _to_out(task: Task, refs: dict[str, str], users: dict[str, str]) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        referral_id=task.referral_id,
        referral_reference=refs.get(task.referral_id) if task.referral_id else None,
        assigned_to=task.assigned_to,
        assignee_email=users.get(task.assigned_to) if task.assigned_to else None,
        created_at=task.created_at,
    )


def _resolve(db: Session, tasks: list[Task]) -> tuple[dict, dict]:
    ref_ids = {t.referral_id for t in tasks if t.referral_id}
    user_ids = {t.assigned_to for t in tasks if t.assigned_to}
    refs = (
        dict(db.execute(select(Referral.id, Referral.reference_code).where(Referral.id.in_(ref_ids))).all())
        if ref_ids
        else {}
    )
    users = (
        dict(db.execute(select(User.id, User.email).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )
    return refs, users


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status_filter: TaskStatus | None = None,
    mine: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TaskOut]:
    stmt = select(Task).where(Task.organization_id == user.organization_id)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if mine:
        stmt = stmt.where(Task.assigned_to == user.id)
    tasks = list(db.execute(stmt).scalars().all())
    # Sort priority-major (high→low), newest-first within each priority.
    # Python's sort is stable, so apply the secondary key first.
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    tasks.sort(key=lambda t: _PRIORITY_RANK.get(t.priority, 1))
    refs, users = _resolve(db, tasks)
    return [_to_out(t, refs, users) for t in tasks]


def _owned(db: Session, task_id: str, user: User) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = Task(
        organization_id=user.organization_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        referral_id=payload.referral_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    refs, users = _resolve(db, [task])
    return _to_out(task, refs, users)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _owned(db, task_id, user)
    changes: dict = {}
    if payload.status is not None:
        changes["status"] = {"from": task.status, "to": payload.status.value}
        task.status = payload.status
    if payload.priority is not None:
        changes["priority"] = {"from": task.priority, "to": payload.priority}
        task.priority = payload.priority
    if changes:
        audit.record(
            db,
            action="task.updated",
            actor=user.id,
            organization_id=user.organization_id,
            referral_id=task.referral_id,
            entity_type="task",
            entity_id=task.id,
            detail=changes,
        )
    db.commit()
    db.refresh(task)
    refs, users = _resolve(db, [task])
    return _to_out(task, refs, users)


@router.post("/{task_id}/claim", response_model=TaskOut)
def claim_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = _owned(db, task_id, user)
    task.assigned_to = user.id
    if task.status == TaskStatus.OPEN:
        task.status = TaskStatus.IN_PROGRESS
    audit.record(
        db,
        action="task.claimed",
        actor=user.id,
        organization_id=user.organization_id,
        referral_id=task.referral_id,
        entity_type="task",
        entity_id=task.id,
        detail={"assigned_to": user.id},
    )
    db.commit()
    db.refresh(task)
    refs, users = _resolve(db, [task])
    return _to_out(task, refs, users)
