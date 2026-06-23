"""Workflow definition, nodes, and executions."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base
from app.models.base import (
    ExecutionStatus,
    TimestampMixin,
    UUIDMixin,
    WorkflowStatus,
)


class Workflow(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflows"

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[WorkflowStatus] = mapped_column(
        String(32), default=WorkflowStatus.DRAFT, index=True
    )
    # The trigger event that starts this workflow, e.g. "referral.received".
    trigger_event: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    nodes: Mapped[list["WorkflowNode"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowNode(UUIDMixin, TimestampMixin, Base):
    """A single node in the workflow graph (trigger | condition | action)."""

    __tablename__ = "workflow_nodes"

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    node_key: Mapped[str] = mapped_column(String(64))  # stable key within the graph
    kind: Mapped[str] = mapped_column(String(32))  # trigger | condition | action
    type: Mapped[str] = mapped_column(String(64))  # e.g. send_email, verify_insurance, if
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    # Adjacency: keys are outcome labels (default/true/false/<case>), values node_keys.
    next: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[dict] = mapped_column(JSON, default=dict)  # x/y for the canvas

    workflow: Mapped["Workflow"] = relationship(back_populates="nodes")


class WorkflowExecution(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_executions"

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), index=True
    )
    referral_id: Mapped[str | None] = mapped_column(
        ForeignKey("referrals.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        String(32), default=ExecutionStatus.PENDING, index=True
    )
    trigger_event: Mapped[str] = mapped_column(String(64))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    # Append-only log of node visits and their results.
    steps: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    workflow: Mapped["Workflow"] = relationship(back_populates="executions")
