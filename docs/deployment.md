# Deployment Guide

## Recommended Stack

| Service | Platform | Cost |
|---|---|---|
| Frontend (Vite static build) | Vercel | Free |
| Flask API | Railway or Render | ~$5–7/mo |
| Background worker | GitHub Actions (scheduled) | Free |
| Database + Auth | Supabase | Free tier |

**Total: ~$5–7/month** for a low-traffic hobby deployment.

### Why this split?

The project has three distinct runtime shapes that map cleanly to different hosting options:

- **Frontend** — Vite builds to static files. No server needed; Vercel is purpose-built for this.
- **Flask API** — A persistent HTTP server. Needs to be always-on. Does *not* need the ML stack (it only writes to the job queue; the worker does the heavy lifting).
- **Worker** — A background daemon that polls the job queue, runs generation, and validates puzzles using `torch` + `sentence-transformers`. This doesn't need to run 24/7 — it restocks the puzzle pool. Running it as a nightly GitHub Actions job is free and sufficient.

---

## Docker Images

Two Dockerfiles live in `backend/`:

| File | Base image | Requirements | Use for |
|---|---|---|---|
| `Dockerfile.api` | `python:3.12-slim` | `requirements-api.txt` | Flask API container |
| `Dockerfile.worker` | `python:3.12-slim` | `requirements.txt` (full) | Worker container |

The `requirements-api.txt` file excludes `torch`, `nvidia-*`, `sentence-transformers`,
`anthropic`, `scikit-learn`, `scipy`, and their transitive dependencies — roughly 40
packages and ~2-3 GB that the API doesn't need.

The worker image bakes the `all-mpnet-base-v2` sentence-transformer model (~420 MB)
into the image at build time, so startup is instant with no network download.

### Build and run locally

```bash
cd backend

# API
docker build -f Dockerfile.api -t connections-api .
docker run -p 8000:8000 --env-file .env connections-api

# Worker
docker build -f Dockerfile.worker -t connections-worker .
docker run --env-file .env connections-worker
```

---

## Environment Variables

### Flask API (`Dockerfile.api`)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | `service_role` key (bypasses RLS for server-side ops) |
| `SUPABASE_JWT_SECRET` | Used by `auth/middleware.py` to validate user JWTs |
| `ADMIN_EMAILS` | Comma-separated list of emails allowed to hit `/admin/*` |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins — **must be set in production** |

> **Important:** Set `CORS_ORIGINS` to your Vercel frontend URL (e.g. `https://your-app.vercel.app`).
> If this is missing, the API defaults to `localhost` only and the deployed frontend will be blocked by CORS.

`ANTHROPIC_API_KEY` and `DATABASE_URL` are **not** needed by the API container.

### Worker (`Dockerfile.worker`)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Same as above |
| `SUPABASE_KEY` | Same as above |
| `ANTHROPIC_API_KEY` | Used by the generation and LLM validation pipeline |

---

## Deploying the Frontend (Vercel)

1. Push the repo to GitHub.
2. In Vercel: **New Project → Import repository → set Root Directory to `frontend`**.
3. Build settings are auto-detected from `vite.config.ts`:
   - Build command: `npm run build`
   - Output directory: `dist`
4. Add environment variables in the Vercel dashboard:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
   - `VITE_API_URL` — the URL of your deployed Flask API

---

## Deploying the Flask API (Railway)

1. In Railway: **New Project → Deploy from GitHub repo**.
2. Set the **Root Directory** to `backend`.
3. Set the **Dockerfile Path** to `Dockerfile.api`.
4. Add the API environment variables listed above under **Variables**.
5. Railway auto-assigns a public URL. Set that as `VITE_API_URL` in Vercel.

### Alternatively: Render

- Create a **Web Service**, point at the repo, set Root Directory to `backend`.
- Set Docker build and point to `Dockerfile.api`.
- Free tier spins down after inactivity — use the $7/mo Starter plan to keep it always-on.

---

## Running the Worker (GitHub Actions)

The worker restocks the puzzle pool. It doesn't need to run continuously — a nightly
cron job using the Anthropic Batch API path is sufficient and free.

Create `.github/workflows/worker-nightly.yml`:

```yaml
name: Nightly puzzle generation

on:
  schedule:
    - cron: '0 3 * * *'   # 3 AM UTC daily
  workflow_dispatch:       # allow manual runs from the GitHub UI

jobs:
  generate:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install uv && uv pip install --system -r requirements.txt

      - name: Run batch fill
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_KEY: ${{ secrets.SUPABASE_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python -c "
          from src.generation.batch_generator import run_batch_fill
          result = run_batch_fill(count=10, config_name='classic')
          print(result)
          "
```

Add `SUPABASE_URL`, `SUPABASE_KEY`, and `ANTHROPIC_API_KEY` to **GitHub → Settings →
Secrets and variables → Actions**.

### Worker pipeline vs batch generator

| | Worker pipeline | Batch generator |
|---|---|---|
| Claude calls per puzzle | ~10–15 (multi-step) | 1 (single-shot) |
| Relative cost | ~$0.05 | ~$0.015 |
| Quality | High (iterative refinement) | Lower |
| Latency | Minutes | 15–60 min (async) |
| Best for | On-demand, admin trigger | Nightly restocking |

The GitHub Actions approach runs the cheaper batch path. If you want the higher-quality
worker pipeline, deploy `Dockerfile.worker` as a Railway service and trigger it via the
admin endpoint instead.
