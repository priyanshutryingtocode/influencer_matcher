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
../venv/Scripts/python main.py --niche Fitness --platform TikTok --audience "millennials" --vibe "high energy"
```

The CLI reindexes only when the table is empty or `--reindex` is supplied. Generation and embedding complete before the PostgreSQL table is replaced transactionally.

## Run the API

The API creates the `match_runs` history table on startup. The migration can also be applied explicitly:

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

Match jobs use one in-process background worker. The service retains up to 128 tracked jobs and returns `429` when live jobs fill that queue. Completed results are durable in PostgreSQL; jobs that are still running when the API process stops are not resumed.

## Run the React frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend expects the API at `http://127.0.0.1:8000` through the Vite proxy. Set `VITE_API_BASE_URL` when the API is hosted elsewhere.

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

Changing the embedding model or vector width requires reindexing. Run history stores creator snapshots and a `creator_key` composed as `platform:handle` for comparisons. Synthetic handles can change when the data is regenerated; real data should use a durable platform creator ID.

## Limitations

This is a single-user/private application. It has no authentication, durable external job queue, deployment manifests, or CI configuration. Do not expose the API publicly without adding authentication, ownership checks, rate limits, and a durable worker.
