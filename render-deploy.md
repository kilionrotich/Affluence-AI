# Deploying Affluence-AI to Render (Single Web Service)

This app is configured to deploy as a **single Render Web Service** that serves both the
FastAPI backend **and** the built React frontend. It uses SQLite for the quick demo
(data is ephemeral and resets on redeploy/sleep).

## Prerequisites
- A GitHub repo containing this project (already set up: `kilionrotich/Affluence-AI`)
- A [Render](https://render.com) account

## Files that make this work
| File | Purpose |
|------|---------|
| `render.yaml` | Render blueprint (auto-detected when you add a Blueprint) |
| `build.sh` | Installs backend deps + builds frontend into `backend/static/` |
| `backend/app/main.py` | Serves the built frontend + provides `/health` |
| `.gitignore` | Excludes `*.db`, `venv`, `node_modules`, `dist`, `backend/static` |

## One-time Push
Make sure the deployment files are committed and pushed to GitHub `main`:

```bash
git add .
git commit -m "Add Render deployment config (single web service)"
git push origin main
```

## Steps in Render Dashboard

### Option A — Blueprint (recommended, uses render.yaml)
1. In Render, click **New → Blueprint**.
2. Connect your `Affluence-AI` repo.
3. Render reads `render.yaml` and creates the `affluence-ai` web service.
4. Click **Apply**.

### Option B — Manual Web Service
1. In Render, click **New → Web Service**.
2. Connect your `Affluence-AI` repo.
3. Configure:
   - **Name:** `affluence-ai`
   - **Runtime:** `Python 3`
   - **Region:** `Oregon (US West)` (or nearest)
   - **Branch:** `main`
   - **Root Directory:** `/`
   - **Build Command:** `./build.sh`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** `Free`
4. Add environment variables:
   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | `sqlite:///./affiliate.db` |
   | `ADMIN_TOKEN` | your admin token |
   | `VIEWER_TOKEN` | your viewer token |
   | `REQUIRE_HTTPS` | `false` |
5. Click **Create Web Service**.

> **Important:** Render injects `PORT` automatically. The start command uses `$PORT`.

## Notes & Limitations (SQLite on Render)
- **Data is not persistent.** Render's filesystem is ephemeral — the SQLite DB is wiped
  on every redeploy and when the service sleeps. This is fine for a demo.
- **Free tier sleeps** after ~15 min of inactivity. First request after sleep has a cold-start delay.
- For **production**, switch to a managed **PostgreSQL**:
  1. Create a Render PostgreSQL instance.
  2. Set `DATABASE_URL` to the Postgres internal connection string.
  3. The app already supports Postgres via SQLAlchemy (`psycopg` driver).

## Verify
After deploy, open the provided URL (e.g. `https://affluence-ai.onrender.com`):
- `GET /health` → `{"status":"ok"}`
- `GET /` → the Affluence-AI dashboard
- `GET /docs` → FastAPI interactive docs
- `GET /report` (with `Authorization: Bearer <VIEWER_TOKEN>`) → earnings JSON

## Redeploying after changes
Push to `main` → Render auto-deploys (if auto-deploy is on) or click
**Manual Deploy → Deploy latest commit** in the Render dashboard.
