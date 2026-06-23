"""Workflow schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.base import ExecutionStatus, WorkflowStatus


class NodeIn(BaseModel):
    node_key: str
    kind: str = Field(description="trigger | condition | action")
    type: str = Field(description="e.g. send_email, verify_insurance, if, switch")
    config: dict = {}
    next: dict = {}
    position: dict = {}


class NodeOut(NodeIn):
    id: str
    model_config = {"from_attributes": True}


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    trigger_event: str = "referral.received"
    status: WorkflowStatus = WorkflowStatus.DRAFT
    nodes: list[NodeIn] = []


class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str | None
    trigger_event: str
    status: WorkflowStatus
    version: int
    nodes: list[NodeOut] = []

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    id: str
    workflow_id: str
    referral_id: str | None
    status: ExecutionStatus
    trigger_event: str
    steps: list = []
    attempts: int
    error: str | None

    model_config = {"from_attributes": True}
