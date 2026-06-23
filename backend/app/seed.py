"""Idempotent seed: default organization, admin user, and a sample workflow."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.base import UserRole, WorkflowStatus
from app.models.organization import Organization, User
from app.models.workflow import Workflow, WorkflowNode

logger = get_logger(__name__)


def seed(db: Session) -> None:
    org = db.execute(
        select(Organization).where(Organization.slug == "flowcare")
    ).scalar_one_or_none()
    if org is None:
        org = Organization(name="FlowCare Demo Clinic", slug="flowcare")
        db.add(org)
        db.flush()

    admin = db.execute(
        select(User).where(User.email == settings.first_admin_email)
    ).scalar_one_or_none()
    if admin is None:
        admin = User(
            organization_id=org.id,
            email=settings.first_admin_email,
            full_name="FlowCare Admin",
            hashed_password=hash_password(settings.first_admin_password),
            role=UserRole.ADMIN,
            email_verified=True,
        )
        db.add(admin)
        logger.info("Seeded admin user %s", settings.first_admin_email)

    _seed_sample_workflow(db, org.id)
    _seed_providers(db, org.id)
    db.commit()


def _seed_providers(db: Session, org_id: str) -> None:
    from app.models.provider import Provider

    existing = db.execute(
        select(Provider).where(Provider.organization_id == org_id)
    ).first()
    if existing:
        return

    providers = [
        # In-network, broad insurance acceptance → cardiology referrals match cleanly.
        Provider(organization_id=org_id, name="Bay Cardiology — Dr. Chen", specialty="cardiology",
                 accepted_insurances=["Aetna", "Blue Shield", "Cigna", "United", "Humana"],
                 location="San Francisco", in_network=True, current_wait_days=4),
        # OUT-of-network only → neurology referrals flag leakage risk.
        Provider(organization_id=org_id, name="Neuro Partners — Dr. Okafor", specialty="neurology",
                 accepted_insurances=["Aetna", "Cigna"],
                 location="Oakland", in_network=False, current_wait_days=9),
        # In-network but narrow insurance → ortho leaks unless insurance is Cigna/United.
        Provider(organization_id=org_id, name="Summit Orthopedics — Dr. Patel", specialty="orthopedics",
                 accepted_insurances=["Cigna", "United"],
                 location="San Jose", in_network=True, current_wait_days=6),
        Provider(organization_id=org_id, name="Endocrine Care — Dr. Reyes", specialty="endocrinology",
                 accepted_insurances=["Kaiser", "Aetna", "Humana"],
                 location="San Francisco", in_network=True, current_wait_days=8),
        Provider(organization_id=org_id, name="Lung & Chest — Dr. Muller", specialty="pulmonology",
                 accepted_insurances=["Humana", "United", "Blue Shield"],
                 location="Berkeley", in_network=True, current_wait_days=5),
    ]
    db.add_all(providers)
    logger.info("Seeded %d demo providers", len(providers))


def _seed_sample_workflow(db: Session, org_id: str) -> None:
    existing = db.execute(
        select(Workflow).where(
            Workflow.organization_id == org_id, Workflow.name == "Standard Intake"
        )
    ).scalar_one_or_none()
    if existing:
        return

    workflow = Workflow(
        organization_id=org_id,
        name="Standard Intake",
        description="Verify insurance, then schedule or request docs.",
        trigger_event="referral.received",
        status=WorkflowStatus.ACTIVE,
    )
    db.add(workflow)
    db.flush()

    nodes = [
        WorkflowNode(
            workflow_id=workflow.id, node_key="t1", kind="trigger",
            type="referral.received", next={"default": "c1"},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="c1", kind="condition", type="if",
            config={"field": "extracted.insurance_member_id", "op": "exists"},
            next={"true": "a1", "false": "a_docs"},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="a1", kind="action", type="verify_insurance",
            next={"default": "c2"},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="c2", kind="condition", type="if",
            config={"field": "insurance.coverage_active", "op": "is_true"},
            next={"true": "a_sched", "false": "a_review"},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="a_sched", kind="action",
            type="schedule_appointment", next={"default": "a_email"},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="a_email", kind="action", type="send_email",
            config={
                "subject": "Your appointment is scheduled",
                "body": "Hi {{extracted.patient_name}}, your appointment is booked for {{appointment.scheduled_for}}.",
            },
            next={},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="a_docs", kind="action", type="create_task",
            config={"title": "Request insurance documents", "priority": "high"},
            next={},
        ),
        WorkflowNode(
            workflow_id=workflow.id, node_key="a_review", kind="action", type="create_task",
            config={"title": "Manual review: insurance inactive", "priority": "high"},
            next={},
        ),
    ]
    db.add_all(nodes)
    logger.info("Seeded sample workflow 'Standard Intake'")
