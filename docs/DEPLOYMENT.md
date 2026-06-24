# Deploying FlowCare AI (live)

The simplest free, reliable path: **backend + Postgres on [Render]**, **frontend on
[Vercel]**. Both connect directly to your GitHub repo. ~15 minutes.

> This deploys the backend as a **single service that processes referrals
> synchronously** (Celery eager mode) — no separate Redis/worker/S3 needed. To
> scale to a real queue later, see *Scaling up* at the bottom.

Prerequisites: a free [Render](https://render.com) account and a free
[Vercel](https://vercel.com) account, both linked to your GitHub.

---

## 1. Backend + database on Render (via the blueprint)

1. Render Dashboard → **New** → **Blueprint**.
2. Connect the **`RickyVishwakarma/flowcareAI`** repo. Render reads
   [`render.yaml`](../render.yaml) and proposes a **`flowcare-api`** web service +
   a **`flowcare-db`** Postgres database. Click **Apply**.
3. Open the **flowcare-api** service → **Environment** and set the `sync: false`
   vars:
   - `FIRST_ADMIN_PASSWORD` → a strong password (don't ship the demo default).
   - `ANTHROPIC_API_KEY` → your key for real Claude extraction (optional — leave
     blank to use the deterministic template extractor).
   - Leave `CORS_ORIGINS` and `FRONTEND_BASE_URL` blank **for now** — you'll fill
     them after the frontend is up.
4. First deploy runs `alembic upgrade head` (preDeploy) then boots the API and
   seeds the admin user. When it's live, note the URL, e.g.
   **`https://flowcare-api.onrender.com`**.
5. Verify: open `https://flowcare-api.onrender.com/health` → `{"status":"ok"}`,
   and `…/docs` for the API.

> Render free tier: the DB expires after 90 days, and the web service **sleeps
> after ~15 min idle** (first request then takes ~50s to wake). Fine for a demo.

---

## 2. Frontend on Vercel

1. Vercel → **Add New… → Project** → import **`RickyVishwakarma/flowcareAI`**.
2. **Root Directory** → `frontend`. Framework preset auto-detects **Next.js**.
3. **Environment Variables** → add:
   - `NEXT_PUBLIC_API_BASE` = your Render API URL (e.g. `https://flowcare-api.onrender.com`)
4. **Deploy**. You'll get a URL like **`https://flowcare-xyz.vercel.app`**.

---

## 3. Point the backend at the frontend (CORS + email links)

Back in Render → **flowcare-api** → **Environment**, set and save (triggers a
redeploy):
- `CORS_ORIGINS` = your Vercel URL (e.g. `https://flowcare-xyz.vercel.app`)
- `FRONTEND_BASE_URL` = the same Vercel URL

Now the SPA can call the API, and verification/reset email links point at the
live site.

---

## 4. Smoke-test the live app

1. Open the Vercel URL → **Sign up** (creates an org) or sign in with
   `admin@flowcare.ai` / your `FIRST_ADMIN_PASSWORD`.
2. **Referrals → Upload** a PDF/text → it should move to `validated`.
3. **Workflow Builder**, **Providers → Find provider**, **Dashboard** all load.

---

## Scaling up (optional, when you outgrow the demo)

The eager single-service setup trades the async queue for simplicity. To run the
real architecture:

1. Add a **Render Redis** instance; set `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`
   to its URL (replacing `memory://`).
2. Add a second Render service (**Background Worker**) using the same repo/Dockerfile
   with command:
   `celery -A app.workers.celery_app.celery_app worker -Q default,ingest,workflows`.
3. Switch `STORAGE_BACKEND=s3` and point it at an S3-compatible bucket
   (**Cloudflare R2** has a free tier) so the worker can read uploads the API stored.
4. Restrict `CORS_ORIGINS` to your exact domain(s).

[Render]: https://render.com
[Vercel]: https://vercel.com
