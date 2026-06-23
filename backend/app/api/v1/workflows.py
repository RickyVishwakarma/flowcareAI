"""Workflow CRUD, activation, and execution inspection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.base import UserRole, WorkflowStatus
from app.models.organization import User
from app.models.workflow import Workflow, WorkflowExecution, WorkflowNode
from app.schemas.workflow import ExecutionOut, WorkflowCreate, WorkflowOut

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.AGENT)),
) -> Workflow:
    workflow = Workflow(
        organization_id=user.organization_id,
        name=payload.name,
        description=payload.description,
        trigger_event=payload.trigger_event,
        status=payload.status,
    )
    db.add(workflow)
    db.flush()
    for node in payload.nodes:
        db.add(
            WorkflowNode(
                workflow_id=workflow.id,
                node_key=node.node_key,
                kind=node.kind,
                type=node.type,
                config=node.config,
                next=node.next,
                position=node.position,
            )
        )
    db.commit()
    db.refresh(workflow)
    return workflow


def _validate_graph(payload: WorkflowCreate) -> None:
    keys = [n.node_key for n in payload.nodes]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=400, detail="Duplicate node_key in graph")
    keyset = set(keys)
    for node in payload.nodes:
        for outcome, target in (node.next or {}).items():
            if target and target not in keyset:
                raise HTTPException(
                    status_code=400,
                    detail=f"Node '{node.node_key}' edge '{outcome}' points to unknown node '{target}'",
                )


@router.put("/{workflow_id}", response_model=WorkflowOut)
def update_workflow(
    workflow_id: str,
    payload: WorkflowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER, UserRole.AGENT)),
) -> Workflow:
    """Replace a workflow's graph (full save from the visual editor). Bumps version."""
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _validate_graph(payload)

    workflow.name = payload.name
    workflow.description = payload.description
    workflow.trigger_event = payload.trigger_event
    workflow.status = payload.status
    workflow.version += 1

    # Replace the node set wholesale.
    db.query(WorkflowNode).filter(WorkflowNode.workflow_id == workflow.id).delete()
    db.flush()
    for node in payload.nodes:
        db.add(
            WorkflowNode(
                workflow_id=workflow.id,
                node_key=node.node_key,
                kind=node.kind,
                type=node.type,
                config=node.config,
                next=node.next,
                position=node.position,
            )
        )
    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("", response_model=list[WorkflowOut])
def list_workflows(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[Workflow]:
    stmt = select(Workflow).where(Workflow.organization_id == user.organization_id)
    return list(db.execute(stmt).scalars().all())


@router.get("/{workflow_id}", response_model=WorkflowOut)
def get_workflow(
    workflow_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Workflow:
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("/{workflow_id}/activate", response_model=WorkflowOut)
def activate_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.MANAGER)),
) -> Workflow:
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.status = WorkflowStatus.ACTIVE
    db.commit()
    db.refresh(workflow)
    return workflow


@router.get("/{workflow_id}/executions", response_model=list[ExecutionOut])
def list_executions(
    workflow_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[WorkflowExecution]:
    workflow = db.get(Workflow, workflow_id)
    if workflow is None or workflow.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Workflow not found")
    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .order_by(WorkflowExecution.created_at.desc())
        .limit(100)
    )
    return list(db.execute(stmt).scalars().all())
