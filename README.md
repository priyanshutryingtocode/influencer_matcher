# Influencer Matcher

A RAG pipeline that matches brand briefs to influencer profiles using PostgreSQL + pgvector for semantic retrieval and Gemini for final ranking with fit ratings and rationales. The dataset is synthetic and seeded by default; replace `backend/src/data_generator.py` when connecting real creator data.

## Features

- Local `sentence-transformers/all-MiniLM-L6-v2` embeddings with 384-dimensional vectors
- Platform hard filtering plus semantic niche, audience, and vibe matching
- Gemini structured ranking with fit validation and retrieval-order fallbacks
- FastAPI backend with asynchronous match jobs
- React + TypeScript Search, History, and Compare pages
- PostgreSQL run history with complete creator snapshots
- Seeded balanced synthetic data generation and golden-case evaluation

## Architecture

```text
React/Vite frontend
        |
        | HTTP JSON
        v
FastAPI service
        |
        +--> local SentenceTransformer embeddings
        +--> PostgreSQL/pgvector retrieval
        +--> Gemini ranking
        +--> PostgreSQL match_runs history
```

The matching pipeline lives in `backend/src/`. `backend/main.py` is the indexing and CLI entry point, `backend/api/main.py` is the HTTP service, `backend/evaluate.py` is the offline evaluator, and `frontend/` is the browser application. Run Python commands from inside `backend/`.

## Repository Layout

```text
influencer_matcher/
├── frontend/       # React/Vite browser application
├── backend/
│   ├── api/        # FastAPI service and job runner
│   ├── src/        # Retrieval, embedding, ranking, and data generation
│   ├── tests/      # Python test suite
│   ├── migrations/ # PostgreSQL migrations
│   ├── data/       # Evaluation cases
│   ├── reports/    # Evaluation reports
│   ├── main.py     # Indexing CLI
│   ├── evaluate.py # Evaluation CLI
│   └── requirements.txt
├── .env            # Root environment file
└── venv/           # Local Python environment
```

## Setup

1. Create a PostgreSQL database with the `vector` extension available.
2. Create a virtual environment and install Python dependencies:

   ```bash
   python -m venv venv
   venv/Scripts/python -m pip install -r backend/requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill the backend values. For local development keep `APP_ENV=development`, `AUTH_REQUIRED=false`, and `JOB_BACKEND=memory`; the Render demo overrides these with `APP_ENV=demo` and authentication enabled.

4. Install frontend dependencies:

   ```bash
   cd frontend
   npm install
   ```

The first embedding query may download the local SentenceTransformer model.

## Indexing CLI

The creator index is built from the CLI before the API or frontend can search it:

```bash
cd backend
../venv/Scripts/python main.py
../venv/Scripts/python main.py --count 500 --reindex --balanced
../venv/Scripts/python main.py --count 5000 --reindex --balanced --balanced-floor 18
../venv/Scripts/python main.py --index-only --balanced
../venv/Scripts/python main.py --niche Fitness --platform TikTok --audience "millennials" --vibe "high energy"
```

The CLI reindexes only when the table is empty or `--reindex` is supplied. Generation and embedding complete before the PostgreSQL table is replaced transactionally.

## Run the API

For local development, the API can initialize the creator and history schemas on startup. Apply the migrations explicitly when needed:

```bash
cd backend
../venv/Scripts/python -m api.migrate
../venv/Scripts/python -m uvicorn api.main:app --reload --port 8000
```

For local browser development, the Vite proxy forwards `/api` and `/health` to port 8000. Set `CORS_ALLOWED_ORIGINS` only when the frontend is hosted on another origin:

```text
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

API endpoints include:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/meta`
- `POST /api/v1/match-jobs`
- `GET /api/v1/match-jobs/{job_id}`
- `GET /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `DELETE /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/export.csv`
- `POST /api/v1/comparisons`

Local development and the free demo use a bounded in-process job manager. Completed runs are persisted in PostgreSQL, but queued or running jobs can be lost when a free Render service sleeps, restarts, or redeploys. The optional paid configuration can use the separate PostgreSQL worker.

## Run the React frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend uses the Vite proxy for local API calls. Set `VITE_API_BASE_URL` for a hosted API; production builds fail closed when it is missing. For local Vite variables, use `frontend/.env.local`; Render and Vercel variables are configured in their dashboards.

The old local `.runs/` files are not imported into the new PostgreSQL history store.

The frontend contains:

- Search form with staged job progress, warnings, result cards, evidence, and CSV export
- PostgreSQL-backed History with run detail and deletion
- Side-by-side Compare with summary metrics and shared creators highlighted

## Evaluation

```bash
cd backend
../venv/Scripts/python evaluate.py
../venv/Scripts/python evaluate.py --output reports/report-<name>.json
```

Evaluation uses exact primary-niche equality against the synthetic golden cases. Replace those labels with human-reviewed outcomes when using real creator data.

## Verification

```bash
cd backend
../venv/Scripts/python -m pytest -q
cd ../frontend
npm run typecheck
npm run lint
npm test
npm run build
```

## Configuration

Important settings are in `backend/src/config.py` and `.env`:

- `LOCAL_EMBED_MODEL`
- `EMBED_DIMENSIONS`
- `EMBED_QUERY_PREFIX` and `EMBED_PASSAGE_PREFIX`
- `GEN_MODEL`
- `GEMINI_API_KEY`
- `DATABASE_URL`
- `AUTH_REQUIRED`
- `SUPABASE_URL`
- `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL`
- `SUPABASE_ISSUER`
- `SUPABASE_JWT_AUDIENCE`
- `JOB_BACKEND`
- `RUN_SCHEMA_ON_STARTUP`
- `MAX_MEMORY_JOBS`
- `MAX_MATCH_JOBS_PER_USER_PER_HOUR`
- `STALE_JOB_AFTER_SECONDS`

Changing the embedding model or vector width requires reindexing. Run history stores creator snapshots and a `creator_key` composed as `platform:handle` for comparisons. Synthetic handles can change when the data is regenerated; real data should use a durable platform creator ID.

## Deployment

The deployment topology is Render for the API, Vercel for the React frontend, and Supabase for Auth/PostgreSQL. The root `.env` is ignored by Git; keep credentials out of source control and rotate any credential that has been shared.

### Supabase

1. Enable the `vector` extension.
2. Enable Supabase Auth and configure the production email provider.
3. Add the Vercel site URL and local development URL to the Supabase Auth redirect allowlist. The magic-link flow returns to the current frontend origin.
4. Rebuild the approved synthetic creator index with the lightweight embedding model. Run migrations first so the vector dimension is corrected before indexing:

```bash
cd backend
../venv/Scripts/python -m api.migrate
../venv/Scripts/python main.py --index-only --balanced
```

`api.migrate` applies the numbered migrations in lexical order. Migration `004` recreates the creator embedding column as `vector(384)` and clears the old synthetic rows; `main.py --index-only` then repopulates them. The API uses a direct server-side PostgreSQL connection with table-owner or `BYPASSRLS` permissions. Never use the browser Supabase URL or anon key as `DATABASE_URL`.

The API supports either Supabase legacy `HS256` tokens (`SUPABASE_JWT_SECRET`) or asymmetric tokens (`SUPABASE_JWKS_URL`). Set `SUPABASE_ISSUER` only when it differs from `<SUPABASE_URL>/auth/v1`; `SUPABASE_JWT_AUDIENCE` defaults to `authenticated`.

### Render

`render.yaml` defines one free native Python web service with `rootDir: backend` and Python `3.12.11`:

- `influencer-matcher-api`: builds with `pip install -r requirements.txt`, starts FastAPI on Render’s `PORT`, checks `/health/ready`, and runs `python -m api.migrate` before each deploy
- No worker, persistent disk, or paid plan is used; jobs run in the API process with `JOB_BACKEND=memory`

The free service has 512 MB RAM, sleeps after 15 minutes idle, and loses local model-cache files on restart. Rebuild the creator index locally before deploying. The service uses `HF_HOME=/tmp/influencer-model-cache`, `MAX_MEMORY_JOBS=4`, and `MAX_MATCH_JOBS_PER_USER_PER_HOUR=3`.

Required backend environment values are:

```text
APP_ENV=demo
AUTH_REQUIRED=true
JOB_BACKEND=memory
RUN_SCHEMA_ON_STARTUP=true
DATABASE_URL=...
GEMINI_API_KEY=...
SUPABASE_URL=...
SUPABASE_JWT_SECRET=...
CORS_ALLOWED_ORIGINS=https://<your-vercel-domain>
```

`render.yaml` supplies the Python version, model, dimensions, queue limits, and ephemeral cache path. Set the secrets requested by the Blueprint. Viewers sign in with Supabase magic links; this keeps the server-side Gemini key from being exposed to anonymous visitors. `CORS_ALLOWED_ORIGINS` is needed by the API; do not put it in the frontend. The pre-deploy migration requires database DDL permission.


### Vercel

Create a Vercel project with root directory `frontend`:

- Install: `npm ci`
- Build: `npm run build`
- Output: `dist`
- Rewrite: `frontend/vercel.json` sends SPA routes to `index.html`

Set these Vercel variables:

```text
VITE_API_BASE_URL=https://<your-render-api>.onrender.com
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
VITE_DEMO_MODE=true
```

Never place `GEMINI_API_KEY`, the Supabase service-role key, `SUPABASE_JWT_SECRET`, or `DATABASE_URL` in Vercel. The deployed application is a best-effort personal demo: Supabase Auth protects the server-side Gemini key, completed runs remain in PostgreSQL, and in-process jobs can be interrupted by Render sleeping or restarting.
