"""Workflow engine — a Zapier-style graph runner.

A workflow is a directed graph of nodes (trigger | condition | action).
Execution starts at the trigger node and walks `node.next[outcome]` edges,
evaluating conditions and dispatching actions against a shared context dict.

Supported node types
--------------------
triggers : referral.received, patient.created, insurance.verified,
           appointment.scheduled
conditions: if, switch  (with and/or operator groups)
actions  : verify_insurance, schedule_appointment, send_email, send_sms,
           create_task, update_status, call_api, send_webhook

The engine is deliberately synchronous and pure-Python so it runs identically
inside a Celery worker or in a unit test. Delayed/parallel execution and retries
are layered on by the task queue (see app/workers/tasks.py).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.base import ExecutionStatus, WorkflowStatus
from app.models.referral import Referral
from app.models.workflow import Workflow, WorkflowExecution, WorkflowNode
from app.services import audit, insurance, notification, scheduling

logger = get_logger(__name__)

MAX_STEPS = 100  # cycle guard


# ── Condition evaluation ─────────────────────────────────────────────


def _resolve(path: str, ctx: dict[str, Any]) -> Any:
    """Resolve a dotted path like 'extracted.insurance_provider' from context."""
    node: Any = ctx
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            node = getattr(node, part, None)
        if node is None:
            return None
    return node


def _eval_clause(clause: dict[str, Any], ctx: dict[str, Any]) -> bool:
    op = clause.get("op", "exists")
    left = _resolve(clause.get("field", ""), ctx)
    right = clause.get("value")
    match op:
        case "exists":
            return left is not None and left != ""
        case "not_exists":
            return left is None or left == ""
        case "eq":
            return left == right
        case "ne":
            return left != right
        case "gt":
            return _num(left) > _num(right)
        case "lt":
            return _num(left) < _num(right)
        case "gte":
            return _num(left) >= _num(right)
        case "lte":
            return _num(left) <= _num(right)
        case "contains":
            return bool(left) and str(right).lower() in str(left).lower()
        case "is_true":
            return bool(left)
        case "is_false":
            return not bool(left)
    return False


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def evaluate_condition(config: dict[str, Any], ctx: dict[str, Any]) -> bool:
    """Evaluate a condition node config supporting and/or groups."""
    if "all" in config:
        return all(evaluate_condition(c, ctx) for c in config["all"])
    if "any" in config:
        return any(evaluate_condition(c, ctx) for c in config["any"])
    return _eval_clause(config, ctx)


# ── Action executors ─────────────────────────────────────────────────

ActionFn = Callable[[Session, WorkflowExecution, WorkflowNode, dict[str, Any]], dict[str, Any]]
_ACTIONS: dict[str, ActionFn] = {}


def action(name: str) -> Callable[[ActionFn], ActionFn]:
    def deco(fn: ActionFn) -> ActionFn:
        _ACTIONS[name] = fn
        return fn

    return deco


@action("verify_insurance")
def _act_verify_insurance(db, execution, node, ctx):
    extracted = ctx.get("extracted", {})
    record = insurance.verify(
        db,
        referral_id=ctx["referral_id"],
        provider=extracted.get("insurance_provider"),
        member_id=extracted.get("insurance_member_id"),
    )
    ctx["insurance"] = {
        "status": record.status.value,
        "coverage_active": record.coverage_active,
        "eligibility": record.eligibility,
    }
    return {"insurance_status": record.status.value, "active": record.coverage_active}


@action("schedule_appointment")
def _act_schedule(db, execution, node, ctx):
    appt = scheduling.schedule(
        db,
        referral_id=ctx["referral_id"],
        provider_name=node.config.get("provider_name"),
    )
    ctx["appointment"] = {"id": appt.id, "scheduled_for": appt.scheduled_for.isoformat()}
    return ctx["appointment"]


@action("send_email")
def _act_send_email(db, execution, node, ctx):
    note = notification.send(
        db,
        channel="email",
        recipient=node.config.get("to") or ctx.get("patient_email", "patient@example.com"),
        subject=_render(node.config.get("subject", "FlowCare update"), ctx),
        body=_render(node.config.get("body", ""), ctx),
        referral_id=ctx.get("referral_id"),
    )
    return {"notification_id": note.id}


@action("send_sms")
def _act_send_sms(db, execution, node, ctx):
    note = notification.send(
        db,
        channel="sms",
        recipient=node.config.get("to") or ctx.get("patient_phone", "+10000000000"),
        body=_render(node.config.get("body", ""), ctx),
        referral_id=ctx.get("referral_id"),
    )
    return {"notification_id": note.id}


@action("send_webhook")
def _act_send_webhook(db, execution, node, ctx):
    note = notification.send(
        db,
        channel="webhook",
        recipient=node.config.get("url", ""),
        body=None,
        referral_id=ctx.get("referral_id"),
        payload={"event": execution.trigger_event, "context": _safe_ctx(ctx)},
    )
    return {"notification_id": note.id}


@action("create_task")
def _act_create_task(db, execution, node, ctx):
    from app.models.operations import Task

    task = Task(
        organization_id=ctx.get("organization_id"),
        referral_id=ctx.get("referral_id"),
        title=_render(node.config.get("title", "Review referral"), ctx),
        description=_render(node.config.get("description", ""), ctx),
        priority=node.config.get("priority", "normal"),
    )
    db.add(task)
    db.flush()
    return {"task_id": task.id}


@action("update_status")
def _act_update_status(db, execution, node, ctx):
    new_status = node.config.get("status")
    referral = db.get(Referral, ctx.get("referral_id"))
    if referral and new_status:
        referral.status = new_status
        db.flush()
        ctx["referral_status"] = new_status
    return {"status": new_status}


@action("call_api")
def _act_call_api(db, execution, node, ctx):
    # Stub: in production use httpx with retries/backoff. Logged for the audit trail.
    return {"called": node.config.get("url"), "method": node.config.get("method", "POST")}


def _render(template: str, ctx: dict[str, Any]) -> str:
    """Tiny {{path}} interpolation against the context."""
    import re

    def repl(match: re.Match[str]) -> str:
        value = _resolve(match.group(1).strip(), ctx)
        return "" if value is None else str(value)

    return re.sub(r"\{\{([^}]+)\}\}", repl, template or "")


def _safe_ctx(ctx: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in ctx.items() if isinstance(v, (str, int, float, bool, dict, list))}


# ── Graph runner ─────────────────────────────────────────────────────


def run_execution(db: Session, execution: WorkflowExecution) -> WorkflowExecution:
    """Execute a workflow from its trigger node to a terminal node."""
    from app.core.metrics import workflow_executions

    workflow = db.get(Workflow, execution.workflow_id)
    nodes = {n.node_key: n for n in workflow.nodes}
    ctx = dict(execution.context)
    steps: list[dict[str, Any]] = []

    execution.status = ExecutionStatus.RUNNING
    execution.attempts += 1
    db.flush()

    current = _entry_node(nodes)
    visited = 0
    try:
        while current is not None and visited < MAX_STEPS:
            visited += 1
            outcome, output = _execute_node(db, execution, current, ctx)
            steps.append(
                {
                    "node_key": current.node_key,
                    "type": current.type,
                    "outcome": outcome,
                    "output": output,
                    "at": datetime.now(timezone.utc).isoformat(),
                }
            )
            next_key = current.next.get(outcome) or current.next.get("default")
            current = nodes.get(next_key) if next_key else None

        execution.status = ExecutionStatus.SUCCEEDED
        execution.steps = steps
        workflow_executions.labels(status="succeeded").inc()
        audit.record(
            db,
            action="workflow.executed",
            organization_id=ctx.get("organization_id"),
            referral_id=ctx.get("referral_id"),
            entity_type="workflow_execution",
            entity_id=execution.id,
            detail={"workflow": workflow.name, "steps": len(steps)},
        )
    except Exception as exc:  # noqa: BLE001 — record and let the task layer retry
        execution.status = ExecutionStatus.FAILED
        execution.error = f"{type(exc).__name__}: {exc}"
        execution.steps = steps
        workflow_executions.labels(status="failed").inc()
        logger.exception("Workflow execution failed", extra={"execution_id": execution.id})
        raise
    finally:
        db.flush()
    return execution


def _entry_node(nodes: dict[str, WorkflowNode]) -> WorkflowNode | None:
    for node in nodes.values():
        if node.kind == "trigger":
            return node
    return next(iter(nodes.values()), None)


def _execute_node(
    db: Session, execution: WorkflowExecution, node: WorkflowNode, ctx: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    if node.kind == "trigger":
        return "default", {"event": execution.trigger_event}

    if node.kind == "condition":
        if node.type == "switch":
            for case in node.config.get("cases", []):
                if evaluate_condition(case.get("when", {}), ctx):
                    return case.get("label", "default"), {"matched": case.get("label")}
            return "default", {"matched": None}
        result = evaluate_condition(node.config, ctx)
        return ("true" if result else "false"), {"result": result}

    if node.kind == "action":
        executor = _ACTIONS.get(node.type)
        if executor is None:
            raise ValueError(f"Unknown action type: {node.type}")
        output = executor(db, execution, node, ctx)
        return "default", output

    raise ValueError(f"Unknown node kind: {node.kind}")


# ── Trigger dispatch ─────────────────────────────────────────────────


def trigger(
    db: Session,
    *,
    event: str,
    organization_id: str,
    referral_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> list[str]:
    """Find active workflows bound to `event` and create executions for them.

    Returns the list of created execution ids. Actual running is dispatched to
    the task queue so the request path stays fast.
    """
    stmt = select(Workflow).where(
        Workflow.organization_id == organization_id,
        Workflow.trigger_event == event,
        Workflow.status == WorkflowStatus.ACTIVE,
    )
    workflows = db.execute(stmt).scalars().all()
    execution_ids: list[str] = []
    base_ctx = {
        "organization_id": organization_id,
        "referral_id": referral_id,
        **(context or {}),
    }
    for workflow in workflows:
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            referral_id=referral_id,
            trigger_event=event,
            context=base_ctx,
            status=ExecutionStatus.PENDING,
        )
        db.add(execution)
        db.flush()
        execution_ids.append(execution.id)
    return execution_ids
