# Influencer Matcher

A RAG pipeline that matches brand briefs to influencer profiles using PostgreSQL + pgvector for semantic retrieval and Gemini for final ranking with fit ratings and rationales. The dataset is synthetic and seeded by default; replace `backend/src/data_generator.py` when connecting real creator data.

## Features

- `gemini-embedding-001` embeddings at 768 dimensions via the Gemini API, which keeps the service inside a 512 MB free-tier budget
- Free-text brand briefs: the user describes the campaign in their own words, with optional audience and tone refinements
- Platform hard filtering plus semantic retrieval over topic tags, audience, and past brand work
- Gemini-written reasons that are verified server-side: each claim must quote a real stored profile field, and an unbacked "strong" fit is downgraded
- Tag-based creator profiles with no fixed niche taxonomy, so a creator can span several topics
- Deterministic generation: a creator is a pure function of its slot key, so changing `--count` or `--balanced-floor` never re-bills the embedding cache
- FastAPI backend with asynchronous match jobs
- React + TypeScript Search, History, and Compare pages
- PostgreSQL run history with complete creator snapshots
- Supabase email/password accounts with isolated per-user history
- Seeded balanced synthetic data generation and golden-case evaluation

## Architecture

```text
React/Vite frontend
        |
        | HTTP JSON
        v
FastAPI service
        |
        +--> Gemini embedding API (768-dim)
        +--> PostgreSQL/pgvector retrieval
        +--> Gemini ranking
        +--> PostgreSQL match_runs history
```

The matching pipeline lives in `backend/src/`. `backend/main.py` is the indexing and CLI entry point, `backend/api/main.py` is the HTTP service, `backend/evaluate.py` is the offline evaluator, and `frontend/` is the browser application. Run Python commands from inside `backend/`.

### Two creator tables

| Table | Holds | Refreshed by |
| --- | --- | --- |
| `influencers` | What the profile states: handle, platform, reach, topics, bio, plus the embedding | Reindex |
| `creator_signals` | What a third party infers *about* it: content style, audience age/gender/country, past brand partners, `reach_ratio`, `sponsored_ratio`, `growth_trend`, `audience_top_countries` | Signal refresh |

The split is the point: an inferred signal can change without re-embedding a profile, and a reason can say "inferred audience 25-34" rather than implying the creator declared it. `search()` reads both in one `LEFT JOIN`, never N+1, and every signal is `COALESCE`d so a creator with no signal row still returns cleanly.

Signals added in migration 007:

- `reach_ratio` — average views ÷ followers. The honest measure of whether reach is real; a follower count alone is the number brands are most often misled by. Stored as exactly that division, so a reader cannot disprove it.
- `sponsored_ratio` — share of posts that are paid.
- `growth_trend` — `rising` / `steady` / `declining`.
- `audience_top_countries` — the headline country is not the whole audience.

These four are **stored and displayable but not citable by the ranking model**, because they are deliberately not in `corpus_text`. Retrieval never searched on them, so a reason must not be able to claim them. The five fields that *did* move to `creator_signals` are in `corpus_text`, which is why the split invalidates no cached vector. `tests/test_signals_contract.py` pins that with a literal copy of the pre-split string.

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

3. Copy `.env.example` to `.env` and fill the backend values. For local development keep `APP_ENV=development`, `AUTH_REQUIRED=false`; the Render demo overrides these with `APP_ENV=demo` and authentication enabled.

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
../venv/Scripts/python main.py --count 1000 --balanced --balanced-floor 11 --reindex --index-only
../venv/Scripts/python main.py --limit 5                        # smoke test: embeds 5, writes nothing
../venv/Scripts/python main.py --count 270 --reindex --balanced
../venv/Scripts/python main.py --count 3000 --reindex --balanced --balanced-floor 18
../venv/Scripts/python main.py --index-only --count 270 --balanced
../venv/Scripts/python main.py --goal "high-energy strength training for beginners" --platform TikTok
```

The CLI reindexes only when the table is empty or `--reindex` is supplied. Generation and embedding complete before the PostgreSQL table is replaced transactionally.

`--balanced-floor` sets how many creators each (topic group, platform) cell gets, and that number decides whether the retrieval metric can measure anything: a filtered query can never return more relevant creators than the cell holds, so a floor of 3 caps precision@10 at 0.30. Raise the floor to lift that cap. The minimum viable count is `groups (10) x platforms (9) x floor`, so a floor of 3 needs 270 profiles and a floor of 11 needs 990.

### Determinism

Every creator is a pure function of a **slot key**: `(seed, group, platform, slot)`, where `slot` is the creator's index within that one cell. Each creator draws from its own `random.Random` seeded with that key and its own Faker instance seeded from the same key. Nothing depends on how many creators were generated before it.

This is not tidiness, it is quota. The profile text is the embedding cache key, so if a creator's values shift when you change `--count` or `--balanced-floor`, every vector is re-billed — at 1,000 requests/day that is a full day of quota for a change that should have been free. With one shared random stream, raising `--balanced-floor` from 3 to 4 rewrote 98% of the corpus.

Two things depend on the ordering and are easy to get wrong:

- **The slot plan is ordered by `(slot, group, platform)`, round-robin** — not by `(group, platform, slot)`. Grouping a cell's creators together would insert new creators into the middle of the list when the floor rises, renumbering everything after them. Round-robin makes the plan for any floor a prefix of the plan for a higher one.
- **Handle collisions re-derive with a sub-salt** on the colliding creator's own key. The previous version retried by drawing from the shared stream, so one collision anywhere shifted every later creator.

`--balanced-floor` also cannot exceed what uniform cells supply (`platforms × floor`); asking for more raises rather than silently under-delivering.

Signal values are internally consistent by construction. `_plan_signals` decides `growth_trend` and `sponsored_ratio` together, then the view count is moved to match — a rising creator has real reach, a declining one does not, and a sponsored-heavy account never has excellent organic reach. A reason may quote two of these at once, so drawing them independently would let the corpus assert something a reader could disprove. Views are drawn log-uniformly rather than uniformly, so the median creator is not implausible.

Embeddings are billed per API request, so a full reindex is the expensive step. Two flags protect that spend:

- `--limit N` embeds only the first N profiles and writes nothing. Run it first to prove the API and credentials work before committing to a full reindex.
- Computed vectors are cached in `backend/.embed-cache/` keyed by a hash of the creator text, model, and width. Because the generator is seeded, an interrupted reindex resumes without re-billing, and a repeat run costs zero requests. `--embed-cache PATH` moves the file; `--no-embed-cache` ignores it.

The CLI prints what a run will cost before it spends anything (`Reusing 950 of 1000 creators; 50 requests still needed`), and warns loudly when the dataset barely matches the cache — that happens when `--count` or `--balanced` differ from the previous run, and it would cost a full day of quota to rediscover vectors already paid for.

### Embedding quota

The free tier allows 100 requests/minute and **1,000 requests/day per model**, and the API embeds one creator per request. A 1,000-profile index therefore costs an entire day of quota, once. The CLI keeps at least `EMBED_REQUEST_INTERVAL_SECONDS` (default 1.0) between calls to stay under the per-minute cap.

When the daily cap is hit, the run stops immediately with `DailyQuotaExhausted` rather than retrying a delay that cannot help, reports how many vectors are banked, and exits with code 2. Re-run the same command after the reset (midnight Pacific) and only the remaining creators are billed. Batch embedding is a paid-tier feature, so it is not an option for reducing the request count.

## Run the API

Migrations are applied by the service itself on startup (`RUN_SCHEMA_ON_STARTUP=true`), and the CLI applies the same migrations through `PostgresRunRepository.ensure_schema()` when it connects, so there is no separate migrate step to remember.

```bash
cd backend
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

Local development and the free demo use a bounded in-process job manager. Completed runs are persisted in PostgreSQL, but queued or running jobs are lost when the service sleeps, restarts, or redeploys. There is no separate worker: the durable PostgreSQL queue and `worker.py` were removed, along with the job tables created by migrations `002` and `003`, which are left in place because they are already recorded in `schema_migrations`.

## Run the React frontend

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend uses the Vite proxy for local API calls. Set `VITE_API_BASE_URL` for a hosted API; production builds fail closed when it is missing. For local Vite variables, use `frontend/.env.local`; Render and Vercel variables are configured in their dashboards.

The old local `.runs/` files are not imported into the new PostgreSQL history store.

The frontend contains:

- Supabase email/password sign-in and account creation
- Search form with staged job progress, warnings, result cards, evidence, and CSV export
- PostgreSQL-backed History with run detail and deletion
- Side-by-side Compare with summary metrics and shared creators highlighted

### Design tokens

All styling lives in `frontend/src/styles.css`, which is organised around tokens in `:root`. Use these rather than literals, so new UI inherits the same rhythm.

| Group | Tokens |
|---|---|
| Type | `--text-2xs` (micro labels) · `--text-xs` (labels, buttons) · `--text-sm` · `--text-base` (body) · `--text-lg` (numbers, card titles) · `--text-xl` · `--text-display` (page `h1`) |
| Shape | `--radius-sm` · `--radius` · `--radius-pill` (and `50%` for dots/avatars) |
| Colour | `--canvas` `--surface` `--surface-raised` `--surface-soft` `--rule` `--rule-strong` `--text` `--muted` `--muted-strong` `--signal` `--signal-dim` `--info` `--warning` `--danger` |
| Tints | `--signal-soft` `--signal-line` `--signal-glow` `--signal-focus` `--signal-hover` `--danger-soft` `--topbar-veil` `--shadow-pop` `--hairline` |

Buttons all derive from one base: `.btn` with `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-danger-ghost`, and `.btn-block`. Page-level structure is shared too — `PageIntro`, `RunContext`, `ErrorNote` and `ResultList` render the same markup on every page, so the pages cannot drift apart visually.

## Evaluation

```bash
cd backend
../venv/Scripts/python evaluate.py
../venv/Scripts/python evaluate.py --sequential --output reports/report-<name>.json
../venv/Scripts/python evaluate.py --no-query-cache   # re-embed every brief
```

Brief embeddings are cached to `.embed-cache/*-queries.jsonl`, separately from the document cache, so a repeat run costs no embedding quota and the report records the hit count as evidence. `--no-query-cache` forces a fresh embed; `--query-cache PATH` points somewhere else. Gemini embeds documents and queries under different task types, so the two caches must stay separate or retrieval gets handed a document vector. Ranking quota is unaffected: every run still spends one `gemini-2.5-flash-lite` call per case.

Golden cases are free-text briefs written the way a marketer would write them, each listing the `expected_tags` that count as a hit. A retrieved creator is relevant when its tags intersect that set. Replace those tags with human-reviewed outcomes when using real creator data.

Relevance is an intersection, not equality. Creators now span several topics, so a creator tagged `["travel", "fashion"]` is relevant to both a travel case and a fashion case. That inflates precision relative to the single-label definition this replaced, and it enlarges `pool_size`, so **reports written before the tag change are not comparable to these**. The `reports/` files still using `expected_niche` and `*_niche_*` field names are the older series.

Three of the ten cases are flagged `"hard": true` (`sustainable-fashion`, `fitness-tiktok`, `food-tiktok`). Their briefs deliberately avoid their own case's tags ("at-home strength training" instead of saying gym or calisthenics), so they test whether the embedding carries the meaning rather than the words. They are scored separately in the report's `hard_cases` block rather than averaged into the headline: a case with nothing relevant in the pool is a different situation from one the ranker mis-ordered, and a single mean over both says nothing about which happened.

Retrieval is purely semantic. A lexical term-overlap bonus was tried on top of the vector score and removed: measured over these cases it moved mean p@10 from 0.393 to 0.387, because the bonus was capped well below the similarity gap between neighbouring candidates and so could only reshuffle near-ties. Term matching is kept for the per-result evidence line, where it is useful.

### Why each result can be checked

`Influencer.corpus_text()` is the single text used both as the embedding and as the basis for the evidence line, so the profile a reason describes is the profile retrieval searched.

The ranking model writes the reason, and `src/ranking.py` decides whether it stands:

- the model must return, per creator, a `grounding` list of `{field, quote}` pairs
- a citation survives only if `field` is in `GROUNDABLE_FIELDS` and `quote` really appears in that field on the stored creator. List fields (tags, brand partners) require an exact item; prose fields (bio, content style) accept a verbatim span
- if no citation survives, `fit: strong` is downgraded to `partial`, the rationale is replaced with a sentence naming what was checked, and `source` becomes `llm_unverified` so the UI marks the row

`GROUNDABLE_FIELDS` contains only fields that appear in `corpus_text`. A test asserts that correspondence, so the allowlist cannot drift into promising a field the vector never saw. Follower counts and engagement rate are deliberately not groundable: they cannot support a topical claim.

Downgraded entries still rank, they just stop asserting something the server could not confirm.

### The ranking response has a hard budget

`RANKING_MAX_OUTPUT_TOKENS` (default 2048) caps the ranking response, and the schema bounds what goes in it: at most 3 `grounding` entries per creator, an 80-character `quote`, a 240-character `rationale`.

This matters more than it looks. A response stopped at the token cap is cut **mid-string**, so it fails to parse as `JSONDecodeError: Unterminated string` and the entire ranking degrades to retrieval order — while still spending one of the 20 `gemini-2.5-flash-lite` calls the free tier allows per day. Adding `grounding` without bounding it took the worst case from ~199 to ~1,471 tokens against a 512 cap, so the same brief failed every time (`temperature=0.0` makes ranking deterministic). The bounds bring the worst case to ~836 tokens.

`MAX_TOKENS` is now read from the response's `finish_reason` and named in the log, with the knob to change, because a bare parse error does not say why the response was short. There is no automatic retry: the bounds are what prevent it, and a retry would spend a second daily call to fix something they already handle.

### Reading the metrics

`precision@k` is bounded by the corpus, not just the model. The generator gives every (topic group, platform) cell a floor, so on a small index a platform-filtered query can only return as many relevant creators as that cell contains: with a floor of 3 and `top_k=10`, precision@10 cannot exceed 0.30 no matter how good the embeddings are. Two metrics avoid that trap:

- `recall_of_ceiling_at_k` / `_at_n` — the share of the relevant creators that could fit in the top k which were actually retrieved. 1.0 means every achievable match was found, and it stays comparable across corpus sizes.
- `ceiling_precision_at_k` / `_at_n` — the best precision the case could have scored given its pool, so a saturated cell is visible instead of looking like a miss.
- `mean_topic_overlap_at_k` — label-free: the mean share of the brief's own words present in the retrieved profiles. It needs no ground truth, so it still works on real creator data, but it rewards literal word reuse and should not be read as relevance on its own.

Each report also records `dataset_size`, `top_k`, and `top_n`. **Scores are not comparable across reports with different `dataset_size` values** — a 5,000-row index has deeper cells, so the same model scores higher there. Reports written before this field existed do not record their size; treat them as a separate series.

The `mean_embed_latency_ms` in a default (concurrent) run is inflated by the harness: cases fire in parallel windows, so requests contend. Use `--sequential` for a per-request latency figure.

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

- `EMBED_MODEL`
- `EMBED_DIMENSIONS`
- `EMBED_TASK_DOCUMENT` and `EMBED_TASK_QUERY`
- `EMBED_REQUEST_INTERVAL_SECONDS`
- `GEN_MODEL`
- `RANKING_MAX_OUTPUT_TOKENS` (default 2048) — see "Why each result can be checked"
- `GEMINI_API_KEY`
- `DATABASE_URL`
- `AUTH_REQUIRED`
- `SUPABASE_URL`
- `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL`
- `SUPABASE_ISSUER`
- `SUPABASE_JWT_AUDIENCE`
- `RUN_SCHEMA_ON_STARTUP`
- `MAX_MEMORY_JOBS`
- `MAX_MATCH_JOBS_PER_IP_PER_HOUR`

Changing the embedding model or vector width requires reindexing, and the service refuses to search a stale index: `/health/ready` reports `INDEX_MODEL_MISMATCH` and the Search page shows "Index needs re-embedding" instead of failing mid-query. Apply the matching migration first (`005_rebuild_gemini_embeddings.sql` moves the column to `vector(768)`), then re-embed. Run history stores creator snapshots and a `creator_key` composed as `platform:handle` for comparisons. Synthetic handles can change when the data is regenerated; real data should use a durable platform creator ID.

## Deployment

The deployment topology is Render for the API, Vercel for the React frontend, and Supabase for Auth/PostgreSQL. The root `.env` is ignored by Git; keep credentials out of source control and rotate any credential that has been shared.

### Supabase

1. Enable the `vector` extension.
2. Open **Authentication → Sign In Providers → Email**, enable email/password authentication, and leave **Allow new users to sign up** enabled.
3. Turn **Confirm email** off so account creation returns a session immediately without SMTP. Set a minimum password length of at least 8 and enable leaked-password protection.
4. Add the Vercel site URL and local development URL to the Supabase Auth URL configuration.
5. Rebuild the synthetic creator index. `main.py` applies the numbered migrations in lexical order before it connects, so no separate migrate step is needed:

```bash
cd backend
../venv/Scripts/python main.py --index-only --count 3000 --balanced --balanced-floor 11
```

Migrations `004` and `005` recreate the creator embedding column (`vector(384)`, then `vector(768)`) and clear the old synthetic rows, so the index must be rebuilt whenever the embedding model or width changes. Migration `006` drops the `niche` and `secondary_niches` columns and truncates, because the same change that removed the taxonomy also rewrote `corpus_text()` to include audience, content style, and brand partners — every stored vector was built from text that no longer exists. Migration `007` moves the inferred fields into `creator_signals` and does **not** truncate: `corpus_text()` still emits the same string, so it is safe to apply before the pending re-embed rather than compounding it. `match_runs` is untouched throughout, so stored runs still export. The API refuses to search a stale index and reports `INDEX_MODEL_MISMATCH` until you do. The API uses a direct server-side PostgreSQL connection with table-owner or `BYPASSRLS` permissions. Never use the browser Supabase URL or anon key as `DATABASE_URL`.

The API supports either Supabase legacy `HS256` tokens (`SUPABASE_JWT_SECRET`) or asymmetric tokens (`SUPABASE_JWKS_URL`). Set `SUPABASE_ISSUER` only when it differs from `<SUPABASE_URL>/auth/v1`; `SUPABASE_JWT_AUDIENCE` defaults to `authenticated`. Password reset and email-change flows are intentionally omitted because they require custom SMTP.

### Render

`render.yaml` defines one free native Python web service with `rootDir: backend` and Python `3.12.11`:

- `influencer-matcher-api`: builds with `pip install -r requirements.txt`, starts FastAPI on Render’s `PORT`, checks `/health/live`, and applies database migrations during application startup. The health check is liveness on purpose: `/health/ready` returns 503 while the creator index is empty or being rebuilt, and that is app state rather than a process Render should restart for.
- No worker, persistent disk, or paid plan is used; jobs run in the API process

The free service has 512 MB RAM and sleeps after 15 minutes idle. Embeddings come from the Gemini API rather than a local model: a SentenceTransformer plus torch exceeded the whole allowance and the service was OOM-killed on the first match. That also means no model download on cold start. Render Free does not support pre-deploy commands, so `RUN_SCHEMA_ON_STARTUP=true` applies migrations when the service starts. Rebuild the creator index locally before deploying. The service uses `EMBED_MODEL=gemini-embedding-001`, `EMBED_DIMENSIONS=768`, `MAX_MEMORY_JOBS=2`, and `MAX_MATCH_JOBS_PER_IP_PER_HOUR=12`. Abuse control is per-IP (`APP_ENV=demo` only); there is no per-user match cap, because an in-process counter would reset on every cold start and would not survive the service sleeping. `/health/live` and `/health/ready` both report `memory_rss_mb` so headroom is visible without a debugger.

Required backend environment values are:

```text
APP_ENV=demo
AUTH_REQUIRED=true
RUN_SCHEMA_ON_STARTUP=true
DATABASE_URL=...
GEMINI_API_KEY=...
SUPABASE_URL=...
SUPABASE_JWT_SECRET=...
CORS_ALLOWED_ORIGINS=https://<your-vercel-domain>
```

`render.yaml` supplies the Python version, model, dimensions, queue limits, and ephemeral cache path. Set the secrets requested by the Blueprint. Visitors create an email/password account or sign in with Supabase Auth; this keeps the server-side Gemini key from being exposed to anonymous visitors. `CORS_ALLOWED_ORIGINS` is needed by the API; do not put it in the frontend. Startup migrations require database DDL permission.


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

Never place `GEMINI_API_KEY`, the Supabase service-role key, `SUPABASE_JWT_SECRET`, or `DATABASE_URL` in Vercel. The deployed application is a best-effort personal demo: Supabase Auth protects the server-side Gemini key, completed runs remain in PostgreSQL, and in-process jobs can be interrupted by Render sleeping or restarting. Open account creation is rate-limited; add Supabase CAPTCHA or switch to invite-only signup if the public demo receives abuse.
