# FlowCare AI — Architecture

This document covers the 16 design deliverables: high- and low-level architecture,
data model, APIs, queue/Redis design, the workflow engine, frontend, auth, deployment,
monitoring, scaling, and security.

---

## 1. High-level architecture

```
                       ┌────────────────────────────────────────────────┐
   Referral sources    │                  FlowCare AI                    │
   (PDF, image, fax,   │                                                │
    email, web form)   │   Nginx ─► FastAPI API  ──────────────┐        │
          │            │              │                        │        │
          └───────────►│        Intake service                 │        │
                       │              │ store file (S3/MinIO)   │        │
                       │              │ enqueue                 │        │
                       │              ▼                         ▼        │
                       │        Redis (broker) ──► Celery workers        │
                       │                              │                  │
                       │   OCR ─► AI extract ─► validate ─► workflow     │
                       │                              │   engine         │
                       │                              ▼                  │
                       │   insurance · scheduling · notifications        │
                       │                              │                  │
                       │        PostgreSQL  ◄─────────┘  (+ audit log)   │
                       │              ▲                                  │
                       │        Prometheus ◄── /metrics ──► Grafana      │
                       └────────────────────────────────────────────────┘
```

The API stays thin and fast: it persists the upload and enqueues work. All heavy
lifting (OCR, LLM calls, integrations, workflow execution) runs in Celery workers,
so the request path never blocks on a multi-second LLM call.

## 2. Low-level architecture (request → outcome)

1. `POST /api/v1/referrals` (multipart). Intake stores the file in object storage,
   mints `REF-xxxx`, writes `referrals` + `referral_documents`, audits
   `referral.uploaded`, and enqueues `process_referral_task`. Returns `202`.
2. **Worker** runs `app/services/pipeline.py:process_referral`:
   - **OCR** (`services/ocr.py`): `pdfplumber` for digital PDFs, Tesseract for scans,
     text passthrough for forms. Writes `ocr_text` + `ocr_confidence`.
   - **AI extraction** (`services/extraction.py`): Claude `claude-opus-4-8` with
     **structured outputs** (`output_config.format` → JSON schema) returns the seven
     fields plus per-field confidence. Falls back to a deterministic template
     extractor when no API key is set, so the pipeline always completes.
   - **Validation** (`services/validation.py`): required fields, date formats,
     insurance completeness, low-confidence flags, duplicate detection.
   - Persists `extracted_data`, sets referral status `validated` / `needs_review`.
   - **Trigger**: `workflow_engine.trigger("referral.received", …)` creates a
     `workflow_executions` row per matching active workflow, each dispatched to the
     `workflows` queue.
3. **Workflow worker** runs `run_workflow_execution` → `workflow_engine.run_execution`,
   walking the node graph (conditions, actions). Actions call the insurance,
   scheduling, and notification services.
4. Every step writes an immutable `audit_logs` row; metrics update Prometheus.

## 3. Database schema

Canonical DDL in [`backend/db/schema.sql`](../backend/db/schema.sql); mirrored by the
SQLAlchemy models in `backend/app/models/`. 14 tables: `organizations`, `users`,
`refresh_sessions`, `referrals`, `referral_documents`, `extracted_data`, `workflows`,
`workflow_nodes`, `workflow_executions`, `insurance_verifications`, `appointments`,
`notifications`, `tasks`, `audit_logs`. Highlights:

- Multi-tenant: every domain row carries `organization_id` (indexed) for isolation.
- `CHECK` constraints enforce the status/role/source enums at the DB layer.
- Composite indexes match the hot queries: `(organization_id, status)` on referrals,
  `(trigger_event, status)` on workflows, `(patient_name, dob)` for dedup.
- `audit_logs` is append-only — in production revoke `UPDATE`/`DELETE` on its DB role.
- JSONB for flexible payloads (`config`, `validation_report`, `eligibility`, `steps`).

## 4. API specification

All routes under `/api/v1`, JWT bearer auth (except `/auth/login`, `/auth/signup`,
`/auth/refresh`, `/auth/verify-email`). OpenAPI at `/docs`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/signup` | self-service: create org + admin, send verification, log in |
| POST | `/auth/login` | email/password → access + refresh tokens (lockout after 5 fails) |
| POST | `/auth/refresh` | rotate refresh token (reuse → revoke session family) |
| POST | `/auth/logout` · `/auth/logout-all` | revoke a session / all sessions |
| POST | `/auth/change-password` | verify current, rotate password, revoke sessions |
| POST | `/auth/verify-email` · `/auth/resend-verification` | email verification |
| POST | `/auth/register` · GET `/auth/me` | admin provisions a user · current user (+ org name) |
| POST | `/referrals` · `/referrals/form` | upload a document / web-form intake → `202` |
| GET  | `/referrals` · `/referrals/{id}` | list (filter by status) · detail + extraction |
| GET  | `/review/queue` · GET `/review/{id}` · POST `/review/{id}` | human-in-the-loop review |
| POST | `/workflows` · PUT `/workflows/{id}` | create · save graph (bumps version) |
| GET  | `/workflows` · `/workflows/{id}` · POST `/{id}/activate` | read · activate |
| GET  | `/workflows/{id}/executions` | execution history + per-step trace |
| POST | `/verify-insurance` · `/schedule-appointment` | eligibility · booking |
| GET  | `/tasks` · POST `/tasks` · PATCH `/tasks/{id}` · POST `/tasks/{id}/claim` | task inbox |
| GET  | `/dashboard/overview` | operations analytics (org-scoped aggregates) |
| GET  | `/audit-logs` | immutable audit trail (filter by referral) |
| GET  | `/health` · `/metrics` | liveness · Prometheus |

**Example — upload**
```bash
curl -F file=@referral.pdf -H "Authorization: Bearer $JWT" \
     http://localhost:8000/api/v1/referrals
# → 202 {"id":"…","reference_code":"REF-1A2B3C4D","status":"received"}
```
**Example — verify insurance**
```bash
curl -X POST -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
     -d '{"referral_id":"…"}' http://localhost:8000/api/v1/verify-insurance
# → {"status":"active","coverage_active":true,"eligibility":{"plan":"PPO","copay_usd":30}}
```

## 5. Folder structure

See the README. The backend is a layered modular monolith
(`api → services → models`) that is **microservice-ready**: each service module
(`ocr`, `extraction`, `insurance`, `scheduling`, `notification`) has no cross-imports
beyond its inputs, so any one can be lifted into its own deployable behind the same
queue contract.

## 6. Docker setup

`docker-compose.yml` runs: `db` (Postgres, schema auto-loaded), `redis`, `minio`
(S3), `api`, `worker` (Celery, 3 queues), `nginx`, `prometheus`, `grafana`, and
`frontend`. `docker compose up --build` brings up the full stack.

## 7. Redis architecture

Redis serves three roles on separate logical DBs:
- **DB 0** — application cache (idempotency keys, eligibility cache, rate limits).
- **DB 1** — Celery broker.
- **DB 2** — Celery result backend.

Separating them keeps cache eviction from touching in-flight task state and lets
each be sized/monitored independently.

## 8. Queue architecture

Three queues with dedicated routing (`celery_app.task_routes`):
`ingest` (OCR + extraction), `workflows` (engine execution), `default`.

Reliability: `acks_late=True` + `reject_on_worker_lost` (a crashed worker re-queues
its task), `prefetch_multiplier=1` (fair dispatch for long tasks). Retry ladder is
**attempt 1 → 2 → 3 → dead-letter** with exponential backoff (5s, 10s, 20s). On
final failure the entity is marked `failed`/`dead_letter` and an audit row is written
— nothing is lost silently. In dev (no broker) tasks run eagerly so the pipeline is
testable without a worker.

## 9. Workflow engine design

A workflow is a directed graph of nodes persisted in `workflow_nodes`
(`kind ∈ trigger|condition|action`, `next` = outcome→node_key adjacency).
`run_execution` walks from the trigger, evaluating against a shared `context` dict:

- **Triggers**: `referral.received`, `patient.created`, `insurance.verified`,
  `appointment.scheduled`.
- **Conditions**: `if` (→ `true`/`false` edges), `switch` (→ labelled cases), with
  `all`/`any` operator groups and operators `eq, ne, gt, lt, gte, lte, contains,
  exists, is_true…`.
- **Actions**: `verify_insurance`, `schedule_appointment`, `send_email`, `send_sms`,
  `send_webhook`, `create_task`, `update_status`, `call_api` — each a registered
  executor (`@action`). `{{path}}` templating pulls values from context.

`send_sms` dispatches through the real **Twilio** adapter
(`services/providers/twilio_sms.py`) when credentials are configured, and a logged
mock otherwise. Adapters share a `ProviderResult` / `ProviderError(retryable=…)`
contract: transient failures (429/5xx/network) raise and ride the task layer's
retry → backoff → DLQ ladder; permanent failures (bad number) are recorded without
failing the whole execution. The same shape is the template for the Textract,
clearinghouse, and SES adapters.

Cross-cutting: a cycle guard (`MAX_STEPS`), per-step trace stored on the execution,
retries/backoff/DLQ from the task layer, and delayed execution via Celery `countdown`.
Parallelism is expressed by a node with multiple `next` edges fanned out as separate
executions.

## 10. Frontend design

Next.js 15 (App Router) + TypeScript + Tailwind, with a sticky top nav and a typed
API client (`lib/api.ts`) that transparently refreshes the access token on a 401
(single-flight). Pages:

- **Dashboard** (`/dashboard`) — operations analytics: KPI cards + dependency-free
  SVG charts (referral volume, status/validation/source breakdowns).
- **Referrals** (`/referrals`) — upload + list + extracted-data/validation detail.
- **Review Queue** (`/review`) — correct failed extractions, re-validate, re-run.
- **Tasks** (`/tasks`) — work-queue inbox: claim, status, priority, filters.
- **Workflow Builder** (`/workflows`) — read-only canvas (`WorkflowCanvas.tsx`) plus a
  full **drag-and-drop editor** (`WorkflowEditor.tsx`): drag nodes from the palette,
  wire edges, edit per-node config, layered auto-layout, full-screen with zoom/fit and
  collapsible side panels. Saves the graph via `PUT /workflows/{id}`.
- **Auth** — `/login`, `/signup` (create org), `/verify-email`.

## 11. Authentication system

Production-shaped auth:

- **JWT** access (30 min) + **rotating refresh** (7 day) tokens, HS256; bcrypt password
  hashing. Refresh tokens are tracked server-side in `refresh_sessions`.
- **Rotation + reuse detection** — every refresh issues a new token and revokes the
  old; replaying a revoked token revokes the whole **session family** (theft defense).
- **Self-service signup** (org + first admin) and **email verification** (mock sender;
  pluggable to SES/SMTP). **Brute-force lockout** (5 fails → 15-min lock, `423`).
- **Logout / logout-all / change-password** all revoke sessions server-side.
- **RBAC** via `require_roles(...)` with roles `admin > manager > agent > viewer`
  (admin bypasses checks). Every query is scoped by `organization_id` (tenant isolation).

## 12. Production deployment plan

- Containers behind Nginx (TLS termination, body-size limits, `/metrics` restricted
  to the monitoring network).
- API + workers scale horizontally and independently (`api`, `worker` replicas).
- Managed Postgres (primary + read replica), managed Redis (or cluster), S3 for blobs.
- **Alembic migrations own the schema** on Postgres/prod: the Docker `migrate`
  service runs `alembic upgrade head` (and api/worker wait on it via
  `service_completed_successfully`) before the app starts. `db/schema.sql` is kept
  as a human-readable reference. SQLite dev/test still uses `create_all` for speed.
  CI verifies migrations apply + roll back. (`.\tasks.ps1 migrate` / `makemigration`.)
- Secrets from a secrets manager (never in the image). Blue/green or rolling deploys;
  health-gated cutover on `/health`.

## 13. Monitoring setup

Two layers:

- **Infra metrics** — `/metrics` exposes Prometheus counters/histograms (referrals by
  source, processing latency, OCR confidence, extraction/insurance failures, workflow
  success/fail, queue depth). Grafana auto-provisions the **FlowCare AI — Operations**
  dashboard (`monitoring/grafana/provisioning/dashboards/flowcare.json`).
- **In-app analytics** — `GET /dashboard/overview` (`services/analytics.py`) returns
  org-scoped business aggregates rendered on the `/dashboard` page: referral volume,
  status/validation/source/extractor breakdowns, workflow success rate, insurance-active
  rate, avg confidence, review-queue size, open tasks.

Structured JSON logs carry `referral_id`/`execution_id` for tracing.

## 14. Scaling strategy (1M referrals/month ≈ 23 req/min avg, bursty)

- Stateless API + workers → scale on CPU/queue depth. Workers are the throughput
  lever; add replicas per queue (OCR/LLM are the slow steps).
- Redis caches eligibility results and dedup lookups; idempotency keys prevent
  double-processing on retries.
- Postgres: read replicas for dashboards/lists, partition `audit_logs` and
  `workflow_executions` by month, connection pooling (PgBouncer).
- LLM cost/latency controlled with `claude-haiku-4-5` for simple docs and Claude
  prompt caching of the system prompt.
- Backpressure: bounded queues + DLQ; autoscale workers on `flowcare_queue_depth`.

## 15. Security best practices

- Tenant isolation on every query; RBAC on mutating routes.
- PHI: encrypt at rest (DB + S3 SSE), TLS in transit, least-privilege DB roles,
  append-only audit log (revoke UPDATE/DELETE), short-lived signed URLs for documents.
- Secrets via env/secret manager; bcrypt password hashing; JWT expiry + refresh.
- Input validation via Pydantic; Nginx body-size caps; never trust client `org`.
- LLM safety: structured outputs constrain the model; extraction never executes model
  text. HIPAA posture: BAA with the LLM/OCR vendor, audit everything, data minimization.

## 16. Development roadmap

See [ROADMAP.md](ROADMAP.md).

## 17. Testing & CI

- **Backend:** 21 integration tests (`backend/tests/`) drive the real app via FastAPI
  `TestClient` (SQLite + eager Celery), covering the pipeline, Twilio adapter, review
  queue, workflow editor, auth (rotation/reuse/lockout/verification), dashboard, and
  tasks — **87% coverage**.
- **Frontend:** 11 Vitest unit tests (`frontend/lib/*.test.ts`) for the API client's
  token refresh (single-flight, 401-retry) and the shared workflow auto-layout algorithm.
- **Live verification:** `backend/scripts/verify_live.py` plus per-feature scripts assert
  each feature end-to-end against a running server.
- **CI** (`.github/workflows/ci.yml`): every push/PR verifies Alembic migrations apply +
  roll back, runs backend `pytest` with a **coverage gate (fail under 80%)**, and runs the
  frontend **typecheck + Vitest + build**. Run the same checks locally with `.\tasks.ps1 ci`.
