# FlowCare AI — Development Roadmap

Status legend: ✅ done · 🔶 partial · ⬜ planned

## Phase 0 — Foundation ✅
- ✅ Modular FastAPI backend, settings, structured logging, Prometheus metrics
- ✅ PostgreSQL schema (14 tables) + SQLAlchemy models, multi-tenant
- ✅ JWT auth + RBAC, seeded org/admin/sample workflow
- ✅ Docker Compose stack (Postgres, Redis, MinIO, API, worker, Nginx, Prometheus, Grafana, frontend)

## Phase 1 — Referral pipeline (vertical slice) ✅
- ✅ Intake: file upload + web-form, secure storage, unique referral IDs, upload history
- ✅ OCR: pdfplumber + Tesseract (+ Textract adapter stub)
- ✅ AI extraction: Claude structured outputs with confidence + deterministic fallback
- ✅ Validation engine: required fields, dates, insurance, duplicates, confidence flags
- ✅ Audit logging for every step; end-to-end smoke test passing

## Phase 2 — Workflow engine ✅
- ✅ Graph runner: triggers, if/switch conditions, 8 action executors, templating
- ✅ Queue execution with retry → exponential backoff → DLQ
- ✅ **Editable drag-and-drop builder** — drag nodes, wire edges, per-node config,
  layered auto-layout, full-screen with zoom/fit + collapsible panels, `PUT` graph save
  (bumps version, rejects dangling edges)
- 🔶 Delayed + parallel execution primitives (countdown wired; fan-out join planned)

## Phase 3 — Integrations 🔶
- ✅ Mock insurance eligibility with history
- ✅ Appointment scheduling (availability, booking, reschedule, cancel)
- ✅ Notifications (email/SMS/webhook/in-app) — mock senders by default
- ✅ **Real Twilio SMS adapter** — live Messages API, E.164 validation, retryable vs
  permanent errors, graceful mock fallback. `ProviderResult`/`ProviderError` abstraction.
- 🔶 Email: mock sender + verification mechanism wired (`email_service.py`) — real
  SES/SMTP delivery pending
- ⬜ Remaining real adapters: AWS Textract, a clearinghouse (Availity/Change/Stedi),
  calendars (Cal/Google) — all follow the `ProviderResult`/`ProviderError` shape

## Phase 4 — Accounts & auth ✅
- ✅ Self-service signup (org + first admin); email verification (mock sender)
- ✅ Rotating refresh tokens with server-side sessions (`refresh_sessions`)
- ✅ Refresh-token reuse detection (revokes the session family)
- ✅ Brute-force lockout (5 fails → 15 min); logout / logout-all / change-password
- ✅ Frontend: transparent token refresh, signup/verify pages, sticky nav with user/org
- ⬜ Password reset, SSO (SAML/OIDC), real email delivery

## Phase 5 — Operations UX ✅
- ✅ **Human-in-the-loop review queue** — correct failed extractions, re-validate, re-run
- ✅ **Operations dashboard** — KPI cards + SVG charts (volume, status/validation/source,
  workflow success, insurance-active, avg confidence, review/tasks counts)
- ✅ **Task inbox / work queue** — claim, status, priority, filters; surfaces
  workflow-created tasks; audited
- ⬜ SLA/aging timers, referring-provider scorecards, closed-loop tracking

## Phase 6 — Quality & CI ✅ / 🔶
- ✅ 21 backend integration tests, **87% coverage**
- ✅ **CI** (`.github/workflows/ci.yml`): backend tests + coverage gate (80%), frontend
  typecheck + build; `.\tasks.ps1 ci` runs it locally
- 🔶 Frontend unit/component tests (Vitest) — planned
- ⬜ Ruff lint gate, Playwright E2E

## Phase 7 — Hardening & scale ⬜
- ⬜ Alembic migrations; partition audit_logs / executions by month
- ⬜ Redis eligibility cache + idempotency keys; PgBouncer; read replicas
- ⬜ Autoscale workers on queue depth; load test to 1M referrals/month
- ⬜ Rate limiting, RLS, field-level PHI encryption, signed document URLs

## Suggested demo script
1. `.\tasks.ps1 api` + `.\tasks.ps1 web` (or `docker compose up --build`)
2. Sign up (create an org) — or sign in as `admin@flowcare.ai` / `admin12345`
3. Land on the **Dashboard** → KPIs + charts
4. **Referrals** → upload a PDF → watch it move `received → validated`; open the
   extracted data, validation report, and audit log
5. Upload one *without* insurance → it lands in the **Review Queue** and spawns a **Task**
6. **Workflow Builder** → Edit "Standard Intake" → full-screen drag/zoom editor; Save
7. **Grafana** (`localhost:3001`) → infra Operations dashboard
