# Influencer Matcher

A RAG pipeline that matches brand briefs to influencer profiles using PostgreSQL + pgvector for semantic retrieval and Gemini for final ranking with fit ratings and rationales. The dataset is synthetic and seeded by default; replace `backend/src/data_generator.py` when connecting real creator data.

## Features

- Local `intfloat/e5-base-v2` embeddings with 768-dimensional vectors
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

3. Create `.env` in the repository root:

   ```text
   GEMINI_API_KEY=your-key
   DATABASE_URL=postgresql://user:password@host:5432/database
   ```

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

Local development uses a bounded in-process job manager. Production requires `JOB_BACKEND=postgres`: the API writes jobs to PostgreSQL and the separate Render worker claims them with a database lease. Completed jobs and results are durable, and abandoned running jobs are requeued after `STALE_JOB_AFTER_SECONDS`.

## Run the React frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend uses the Vite proxy for local API calls. Set `VITE_API_BASE_URL` for a hosted API; production builds fail closed when it is missing.

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
- `MAX_MATCH_JOBS_PER_USER_PER_HOUR`
- `STALE_JOB_AFTER_SECONDS`

Changing the embedding model or vector width requires reindexing. Run history stores creator snapshots and a `creator_key` composed as `platform:handle` for comparisons. Synthetic handles can change when the data is regenerated; real data should use a durable platform creator ID.

## Deployment

The production topology is Render for the API and worker, Vercel for the React frontend, and Supabase for Auth/PostgreSQL. The root `.env` is ignored by Git; keep credentials out of source control and rotate any credential that has been shared.

### Supabase

1. Enable the `vector` extension.
2. Enable Supabase Auth and configure the production email provider.
3. Add the Vercel site URL and local development URL to the Supabase Auth redirect allowlist. The magic-link flow returns to the current frontend origin.
4. Create and index the creator table once, then apply all migrations in order. The Render API pre-deploy command performs the same bootstrap safely: `main.py --index-only` populates an empty index and skips work when data already exists.

```bash
cd backend
../venv/Scripts/python main.py --index-only --balanced
../venv/Scripts/python -m api.migrate
```

`api.migrate` applies `001` through `003` in lexical order. Migration `003` enables RLS and revokes direct `anon`/`authenticated` table access; the Render API and worker must use a direct server-side PostgreSQL connection using a table-owner or `BYPASSRLS` role with permission to read and write the app tables. Never use the browser Supabase URL or anon key as `DATABASE_URL`.

The API supports either Supabase legacy `HS256` tokens (`SUPABASE_JWT_SECRET`) or asymmetric tokens (`SUPABASE_JWKS_URL`). Set `SUPABASE_ISSUER` only when it differs from `<SUPABASE_URL>/auth/v1`; `SUPABASE_JWT_AUDIENCE` defaults to `authenticated`.

### Render

`render.yaml` defines two native Python services with `rootDir: backend` and Python `3.12.11`:

- `influencer-matcher-api`: builds with `pip install -r requirements.txt`, starts FastAPI on Render’s `PORT`, checks `/health/ready`, and runs `python main.py --index-only --balanced && python -m api.migrate` before each deploy
- `influencer-matcher-worker`: builds with `pip install -r requirements.txt`, starts `python -m worker`, and uses a 5 GB persistent disk at `/opt/render/project/src/model-cache`

Create a Render Blueprint from the repository, then provide the secret values requested by the manifest. The worker disk keeps the local SentenceTransformer model cache across restarts. Both services use a `1c-2g` plan: the API needs headroom for its first-deploy index bootstrap, and the worker needs it for embeddings and ranking.

Required backend environment values for the API are shown below; repeat the database, Gemini, and Supabase values on the worker as well:

```text
APP_ENV=production
AUTH_REQUIRED=true
JOB_BACKEND=postgres
RUN_SCHEMA_ON_STARTUP=false
DATABASE_URL=...
GEMINI_API_KEY=...
SUPABASE_URL=...
SUPABASE_JWT_SECRET=...
CORS_ALLOWED_ORIGINS=https://<your-vercel-domain>
```

Set `SUPABASE_JWT_SECRET` for legacy HS256 tokens. For asymmetric tokens, the standard JWKS URL is derived from `SUPABASE_URL`; set `SUPABASE_JWKS_URL` only when a custom URL is required. `CORS_ALLOWED_ORIGINS` is needed by the API; do not put it in the frontend. The API pre-deploy migration requires the database credentials and should be allowed to run DDL.

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
```

Never place `GEMINI_API_KEY`, the Supabase service-role key, `SUPABASE_JWT_SECRET`, or `DATABASE_URL` in Vercel. The deployed application is multi-user: Supabase Auth, owner-scoped queries, the hourly job quota, and the separate worker are required. Add monitoring, retention controls, and a formal CI/deployment review before exposing it broadly.
