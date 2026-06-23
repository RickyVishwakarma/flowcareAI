-- FlowCare AI — canonical PostgreSQL schema
-- Indexes, foreign keys, and constraints for a 1M-referrals/month workload.
-- The ORM (app/models) mirrors this; production uses this DDL + Alembic.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Organizations & users ────────────────────────────────────────────
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(32) NOT NULL DEFAULT 'agent'
                       CHECK (role IN ('admin','manager','agent','viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_org ON users(organization_id);

-- Refresh-token sessions: rotation, revocation, and reuse detection.
CREATE TABLE refresh_sessions (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    jti          VARCHAR(36) NOT NULL UNIQUE,
    family_id    VARCHAR(36) NOT NULL,
    expires_at   TIMESTAMPTZ NOT NULL,
    revoked      BOOLEAN NOT NULL DEFAULT FALSE,
    revoked_at   TIMESTAMPTZ,
    replaced_by  VARCHAR(36),
    user_agent   VARCHAR(512),
    ip_address   VARCHAR(64),
    last_used_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_user ON refresh_sessions(user_id);
CREATE INDEX idx_refresh_jti ON refresh_sessions(jti);
CREATE INDEX idx_refresh_family ON refresh_sessions(family_id);

-- ── Referrals & documents ────────────────────────────────────────────
CREATE TABLE referrals (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    reference_code   VARCHAR(32) NOT NULL UNIQUE,
    source           VARCHAR(32) NOT NULL
                        CHECK (source IN ('pdf','image','fax','email','web_form')),
    status           VARCHAR(32) NOT NULL DEFAULT 'received'
                        CHECK (status IN ('received','processing','extracted','validated',
                                          'needs_review','insurance_verified','scheduled',
                                          'completed','failed')),
    created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    patient_name     VARCHAR(255),
    referring_doctor VARCHAR(255),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_referrals_org_status ON referrals(organization_id, status);
CREATE INDEX idx_referrals_created ON referrals(created_at DESC);

CREATE TABLE referral_documents (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_id    UUID NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    filename       VARCHAR(512) NOT NULL,
    content_type   VARCHAR(128),
    storage_key    VARCHAR(1024) NOT NULL,
    size_bytes     INTEGER NOT NULL DEFAULT 0,
    ocr_text       TEXT,
    ocr_confidence DOUBLE PRECISION,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_documents_referral ON referral_documents(referral_id);

CREATE TABLE extracted_data (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_id         UUID NOT NULL UNIQUE REFERENCES referrals(id) ON DELETE CASCADE,
    patient_name        VARCHAR(255),
    dob                 VARCHAR(32),
    insurance_provider  VARCHAR(255),
    insurance_member_id VARCHAR(128),
    referring_doctor    VARCHAR(255),
    diagnosis           TEXT,
    referral_reason     TEXT,
    field_confidence    JSONB NOT NULL DEFAULT '{}',
    overall_confidence  DOUBLE PRECISION,
    extractor           VARCHAR(64),
    validation_status   VARCHAR(32)
                          CHECK (validation_status IN ('passed','passed_with_warnings','failed')),
    validation_report   JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Duplicate-detection support index.
CREATE INDEX idx_extracted_patient_dob ON extracted_data(patient_name, dob);

-- ── Workflows ────────────────────────────────────────────────────────
CREATE TABLE workflows (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft','active','paused','archived')),
    trigger_event   VARCHAR(64) NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_workflows_org ON workflows(organization_id);
CREATE INDEX idx_workflows_trigger_active ON workflows(trigger_event, status);

CREATE TABLE workflow_nodes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    node_key    VARCHAR(64) NOT NULL,
    kind        VARCHAR(32) NOT NULL CHECK (kind IN ('trigger','condition','action')),
    type        VARCHAR(64) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}',
    next        JSONB NOT NULL DEFAULT '{}',
    position    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workflow_id, node_key)
);
CREATE INDEX idx_nodes_workflow ON workflow_nodes(workflow_id);

CREATE TABLE workflow_executions (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id   UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    referral_id   UUID REFERENCES referrals(id) ON DELETE SET NULL,
    status        VARCHAR(32) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','running','succeeded','failed','dead_letter')),
    trigger_event VARCHAR(64) NOT NULL,
    context       JSONB NOT NULL DEFAULT '{}',
    steps         JSONB NOT NULL DEFAULT '[]',
    attempts      INTEGER NOT NULL DEFAULT 0,
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_executions_referral ON workflow_executions(referral_id);
CREATE INDEX idx_executions_status ON workflow_executions(status);

-- ── Operations ───────────────────────────────────────────────────────
CREATE TABLE insurance_verifications (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_id     UUID NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    provider        VARCHAR(255),
    member_id       VARCHAR(128),
    status          VARCHAR(32) NOT NULL DEFAULT 'unknown'
                       CHECK (status IN ('active','inactive','pending','unknown')),
    coverage_active BOOLEAN,
    eligibility     JSONB NOT NULL DEFAULT '{}',
    raw_response    JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_insurance_referral ON insurance_verifications(referral_id);

CREATE TABLE appointments (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_id      UUID NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    provider_name    VARCHAR(255),
    scheduled_for    TIMESTAMPTZ,
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    status           VARCHAR(32) NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled','rescheduled','cancelled','completed','no_show')),
    location         VARCHAR(512),
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_appointments_referral ON appointments(referral_id);

CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_id UUID REFERENCES referrals(id) ON DELETE SET NULL,
    channel     VARCHAR(32) NOT NULL CHECK (channel IN ('email','sms','webhook','in_app')),
    recipient   VARCHAR(512) NOT NULL,
    subject     VARCHAR(512),
    body        TEXT,
    sent        BOOLEAN NOT NULL DEFAULT FALSE,
    payload     JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notifications_referral ON notifications(referral_id);

CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    referral_id     UUID REFERENCES referrals(id) ON DELETE SET NULL,
    assigned_to     UUID REFERENCES users(id) ON DELETE SET NULL,
    title           VARCHAR(512) NOT NULL,
    description     TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open','in_progress','done','cancelled')),
    priority        VARCHAR(16) NOT NULL DEFAULT 'normal',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tasks_org_status ON tasks(organization_id, status);

-- Provider directory + referral→provider match records (leakage detection).
CREATE TABLE providers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    specialty       VARCHAR(64) NOT NULL,
    accepted_insurances JSONB NOT NULL DEFAULT '[]',
    location        VARCHAR(255),
    in_network      BOOLEAN NOT NULL DEFAULT TRUE,
    weekly_capacity INTEGER NOT NULL DEFAULT 20,
    current_wait_days INTEGER NOT NULL DEFAULT 7,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_providers_org ON providers(organization_id);
CREATE INDEX idx_providers_specialty ON providers(specialty);

CREATE TABLE provider_matches (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    referral_id     UUID NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    provider_id     UUID REFERENCES providers(id) ON DELETE SET NULL,
    specialty       VARCHAR(64),
    in_network      BOOLEAN NOT NULL DEFAULT FALSE,
    accepts_insurance BOOLEAN NOT NULL DEFAULT FALSE,
    leakage_risk    BOOLEAN NOT NULL DEFAULT FALSE,
    score           DOUBLE PRECISION NOT NULL DEFAULT 0,
    candidates      JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_matches_referral ON provider_matches(referral_id);
CREATE INDEX idx_matches_leakage ON provider_matches(leakage_risk);

-- Immutable audit trail. Revoke UPDATE/DELETE at the DB role level in prod.
CREATE TABLE audit_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID,
    referral_id     UUID,
    actor           VARCHAR(255),
    action          VARCHAR(128) NOT NULL,
    entity_type     VARCHAR(64),
    entity_id       UUID,
    detail          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org ON audit_logs(organization_id);
CREATE INDEX idx_audit_referral ON audit_logs(referral_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
