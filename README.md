<div align="center">

# 🏥 FlowCare AI

**Production-grade healthcare _referral automation_ platform + visual _workflow builder_.**

Turn any referral — PDF, fax, scanned image, or web form — into a verified,
scheduled patient, automatically.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![Claude](https://img.shields.io/badge/AI-Claude%20Opus%204.8-D97757)
![Tests](https://img.shields.io/badge/tests-21%20passing-3fb950)
![Coverage](https://img.shields.io/badge/coverage-87%25-3fb950)
![License](https://img.shields.io/badge/license-MIT-blue)

</div>

---

## The problem

Healthcare providers receive referrals through a chaos of channels — PDFs, scanned
documents, faxes, email attachments, web forms. Today, staff manually read each one,
key in patient data, verify insurance, chase missing info, call patients, book
appointments, and track status across spreadsheets. It's slow, expensive, and
error-prone — and patients fall through the cracks (the industry calls it _referral
leakage_).

**FlowCare AI automates the entire referral lifecycle** with OCR, LLMs, a
queue-based pipeline, and a Zapier-style workflow engine — with a full audit trail
and observability.

```
Referral sources → Intake → OCR → AI extraction → Validation
   → Workflow engine → Task queue → Integrations
   → Scheduling → Notifications → Audit & monitoring
```

---

## ✨ What you can do with a referral

The platform treats a referral as a first-class object with a full lifecycle. Today
it does the core intake-to-action loop; the same foundation extends cleanly to the
high-value capabilities health systems actually pay for.

> ✅ built today &nbsp;·&nbsp; 🔭 designed-for / next build

### Intake & understanding
- ✅ **Omni-channel intake** — PDF, image, fax, and structured web form
- ✅ **OCR** — `pdfplumber` for digital PDFs, Tesseract for scans
- ✅ **AI extraction** — Claude structured outputs → patient, DOB, insurance, doctor, diagnosis, reason — with per-field confidence
- ✅ **Validation engine** — required fields, date formats, insurance completeness, duplicate detection
- ✅ **Human-in-the-loop review** — failed referrals route to a reviewer who corrects fields, re-validates, and re-runs the workflow
- 🔭 **AI triage** — auto-classify urgency and specialty, route to the right team
- 🔭 **Clinical summarization** — a concise summary of the referral for the receiving provider
- 🔭 **Coding assistance** — suggest ICD-10 / CPT codes from the diagnosis
- 🔭 **Missing-info auto-chase** — automatically request missing documents from the referring office

### Routing & matching
- ✅ **Visual workflow engine** — drag-and-drop triggers, conditions, and actions
- 🔭 **Smart provider matching** — by specialty, accepted insurance, location, and wait time
- 🔭 **Referral leakage prevention** — detect out-of-network routing and keep patients in-network

### Insurance & money
- ✅ **Eligibility verification** — coverage, eligibility, policy status (mock payer; pluggable to a real clearinghouse)
- 🔭 **Prior-authorization automation** — the single biggest referral bottleneck
- 🔭 **Denial & appeal management** — track rejections and drive appeal workflows

### Patient engagement
- ✅ **Notifications** — real **Twilio SMS**, plus email / webhook / in-app
- 🔭 **Two-way SMS self-scheduling** and multi-step reminder sequences
- 🔭 **Waitlist & backfill** — fill cancellations automatically

### Closed-loop & tracking
- ✅ **Status lifecycle** — `received → processing → extracted → validated → scheduled → completed`
- ✅ **Immutable audit trail** — every action on every referral
- ✅ **Task inbox / work queue** — workflow-created tasks staff can claim, prioritize, and close
- 🔭 **Closed-loop referrals** — track received → scheduled → seen → report back to the referring provider
- 🔭 **SLA / aging escalation** — flag stale referrals and escalate
- 🔭 **Patient matching (MPI)** — link an incoming referral to an existing patient record

### Intelligence & platform
- ✅ **Operations dashboard** — in-app analytics: volume, status/validation breakdowns, workflow success, insurance-active rate, avg confidence
- ✅ **Observability** — Prometheus metrics + a provisioned Grafana dashboard
- 🔭 **Referring-provider scorecards** & conversion / time-to-appointment analytics
- 🔭 **Intake copilot** — chat over a referral document
- 🔭 **Partner API + webhooks + EHR (FHIR/HL7) integration** — Epic, Oracle Health, athenahealth

---

## 🧱 Architecture

```
                       ┌────────────────────────────────────────────────┐
   Referral sources    │                  FlowCare AI                    │
   (PDF, image, fax,   │   Nginx ─► FastAPI API ───────────────┐        │
    email, web form)   │              │ store file (S3/MinIO)  │        │
          │            │              │ enqueue                ▼        │
          └───────────►│        Redis (broker) ──► Celery workers        │
                       │                              │                  │
                       │   OCR ─► AI extract ─► validate ─► workflow     │
                       │                              │   engine         │
                       │                              ▼                  │
                       │   insurance · scheduling · notifications        │
                       │                              │                  │
                       │        PostgreSQL  ◄─────────┘  (+ audit log)   │
                       │        Prometheus ◄── /metrics ──► Grafana      │
                       └────────────────────────────────────────────────┘
```

The API stays thin and fast — it persists the upload and enqueues work. All heavy
lifting (OCR, LLM calls, integrations, workflow execution) runs in Celery workers,
so the request path never blocks. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
for the full design (16 deliverables: HLA/LLA, schema, APIs, queue/Redis design,
workflow engine, auth, deployment, scaling, security).

### The end-to-end pipeline

```
POST /referrals → store + REF-id → [queue] process_referral
   → OCR → AI extract (Claude) → validate → persist
   → fire "referral.received" → matching workflows execute → audit every step
```

---

## 🛠 Tech stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI · Python 3.12 · Pydantic v2 |
| Data | PostgreSQL 16 · Redis 7 |
| Async jobs | Celery (retry → exponential backoff → dead-letter queue) |
| AI | **Anthropic Claude `claude-opus-4-8`** (structured outputs) + deterministic fallback |
| OCR | Tesseract · `pdfplumber` (AWS Textract adapter stub) |
| Integrations | **Twilio SMS** (real) · insurance / email / webhook (mock, pluggable) |
| Auth | JWT access + **rotating refresh** (reuse detection) · RBAC · lockout · email verification · multi-tenant |
| Frontend | Next.js 15 · TypeScript · TailwindCSS (dashboard, review queue, task inbox, drag-and-drop workflow editor) |
| Infra | Docker · Docker Compose · Nginx |
| Observability | Prometheus · Grafana · structured JSON logs |

---

## 🚀 Quick start

### Full stack (Docker)

```bash
cp .env.example .env          # optionally add ANTHROPIC_API_KEY + TWILIO_* creds
docker compose up --build
```

| Service | URL |
|---------|-----|
| API (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Grafana | http://localhost:3001 (admin / admin) |
| Prometheus | http://localhost:9090 |

Seeded admin login: **`admin@flowcare.ai`** / **`admin12345`**

### One-command local dev (Windows — `tasks.ps1`)

```powershell
.\tasks.ps1 setup    # one-time: venv + deps
.\tasks.ps1 test     # backend suite (21 passing, 87% coverage)
.\tasks.ps1 ci       # full CI locally: backend tests+coverage + frontend typecheck+build
.\tasks.ps1 api      # API on :8000  (SQLite + in-memory queue, no Redis needed)
.\tasks.ps1 web      # frontend on :3000
```

> No `ANTHROPIC_API_KEY`? Extraction falls back to a deterministic template
> extractor, so the whole pipeline still runs. No `TWILIO_*`? SMS logs as a mock.

---

## 🔌 API overview

All routes under `/api/v1`, JWT bearer auth, OpenAPI at `/docs`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/signup` · `/auth/login` · `/auth/refresh` | create org · login · rotate token |
| POST | `/auth/verify-email` · `/auth/logout` · `/auth/change-password` | account management |
| GET | `/dashboard/overview` | operations analytics (org-scoped aggregates) |
| POST | `/referrals` · `/referrals/form` | upload / submit a referral |
| GET | `/referrals` · `/referrals/{id}` | list / detail (extraction + validation) |
| GET | `/review/queue` · POST `/review/{id}` | human-in-the-loop review |
| GET | `/tasks` · POST `/tasks/{id}/claim` · PATCH `/tasks/{id}` | task inbox |
| POST | `/workflows` · PUT `/workflows/{id}` | create / save a visual workflow graph |
| GET | `/workflows/{id}/executions` | execution history + step trace |
| POST | `/verify-insurance` · `/schedule-appointment` | integrations |
| GET | `/audit-logs` | immutable audit trail |
| GET | `/health` · `/metrics` | liveness · Prometheus |

```bash
# Upload a referral
curl -F file=@referral.pdf -H "Authorization: Bearer $JWT" \
     http://localhost:8000/api/v1/referrals
# → 202 {"id":"…","reference_code":"REF-1A2B3C4D","status":"received"}
```

---

## 🧩 Workflow engine

A workflow is a directed graph of nodes built in the visual editor (`/workflows`):

- **Triggers** — `referral.received`, `patient.created`, `insurance.verified`, `appointment.scheduled`
- **Conditions** — `if` / `switch` with `and`/`or` groups and operators (`eq`, `gt`, `contains`, `exists`, …)
- **Actions** — `verify_insurance`, `schedule_appointment`, `send_email`, `send_sms`, `create_task`, `update_status`, `call_api`, `send_webhook` — with `{{templating}}`

Reliability: cycle guard, per-step trace, retry → exponential backoff → dead-letter
queue, and delayed execution via the task layer. Build a graph in the canvas, hit
**Save**, and it executes on the next matching referral.

---

## 📁 Project structure

```
healthReffer/
├── backend/                 FastAPI app, services, Celery workers
│   ├── app/
│   │   ├── core/            config, db, security, logging, metrics
│   │   ├── models/          SQLAlchemy ORM (14 tables)
│   │   ├── schemas/         Pydantic request/response models
│   │   ├── services/        ocr, extraction, validation, workflow_engine, review,
│   │   │   │                analytics, auth_service, email_service, insurance,
│   │   │   │                scheduling, notification, audit, pipeline, storage
│   │   │   └── providers/   external adapters (Twilio SMS) — ProviderResult shape
│   │   ├── api/v1/          versioned REST routers (auth, referrals, review,
│   │   │                    workflows, dashboard, tasks, operations)
│   │   └── workers/         Celery app + tasks (retry / backoff / DLQ)
│   ├── db/schema.sql        canonical PostgreSQL DDL (indexes, FKs, constraints)
│   ├── scripts/             verify_live.py — live HTTP smoke test
│   └── tests/               pytest suite (21 tests, 87% coverage)
├── frontend/                Next.js: dashboard, referrals, review, tasks, workflow editor
├── monitoring/             Prometheus + Grafana provisioning
├── nginx/                  reverse proxy config
├── .github/workflows/      CI (backend tests+coverage, frontend typecheck+build)
├── docs/                   ARCHITECTURE.md · ROADMAP.md
├── docker-compose.yml      9-service stack
└── tasks.ps1               one-command dev runner
```

---

## ✅ Testing & CI

```bash
cd backend && pytest --cov=app          # 21 integration tests, 87% coverage
python scripts/verify_live.py http://localhost:8000   # live HTTP smoke check
```

- **Backend:** 21 integration tests (pipeline, Twilio, review, workflow editor, auth,
  dashboard, tasks) driving the real app via `TestClient` — **87% coverage**.
- **Every feature** is additionally verified end-to-end against a live server each
  change, including the workflow engine executing a user-built graph on a real upload.
- **Continuous Integration** ([.github/workflows/ci.yml](.github/workflows/ci.yml)):
  on every push/PR, GitHub Actions runs the backend test suite with a **coverage gate
  (fail under 80%)** and the frontend **typecheck + production build**.
- Run the same checks locally before pushing: **`.\tasks.ps1 ci`**.

> CI activates once the repo is pushed to GitHub (`git init` → push). Add a status
> badge with: `![CI](https://github.com/<owner>/<repo>/actions/workflows/ci.yml/badge.svg)`.

---

## 🔐 Security & compliance

Built in: multi-tenant isolation on every query, RBAC on mutating routes, bcrypt
password hashing, JWT expiry + refresh, Pydantic input validation, an append-only
audit log, and TLS-terminating Nginx.

> ⚠️ **This is a production-_grade_ prototype, not a HIPAA-certified product.**
> Handling real PHI requires signed BAAs with every vendor (Anthropic, AWS, Twilio,
> host), encryption-at-rest with managed keys, SOC 2 / HITRUST, and real (not mock)
> integrations. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the path to production.

---

## 🗺 Roadmap & maturity

Phases 0–3 are done (foundation, referral pipeline, workflow engine + editor,
human review, real Twilio SMS). See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the
full plan — real OCR (Textract), clearinghouse eligibility, EHR/FHIR integration,
prior-auth automation, closed-loop tracking, analytics, and scale hardening.

## 📄 License

MIT — see `LICENSE`.

<div align="center">
<sub>Built as a portfolio-grade reference for healthcare referral automation.</sub>
</div>
