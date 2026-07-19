# Influencer Matcher

A small RAG pipeline that matches a brand brief to influencer profiles:
hard filters (budget, platform) and semantic search happen together as one
Supabase (Postgres + pgvector) query, and Gemini generation ranks the final
shortlist with a rationale per pick. Currently runs on a synthetic, seeded
influencer database — swap `src/data_generator.py` for a real data source
when you're ready.

## Project structure

```
influencer_matcher/
├── main.py                  # CLI entry point, wires the pipeline together
├── docker-compose.yml        # optional: local Postgres+pgvector, if not using Supabase
├── requirements.txt
├── .env.example
├── pytest.ini
├── src/
│   ├── config.py             # model names, defaults, env loading
│   ├── models.py              # Influencer and Brief data classes
│   ├── data_generator.py      # synthetic influencer database
│   ├── gemini_client.py       # Gemini API client factory
│   ├── embeddings.py          # embedding computation (cosine similarity util)
│   ├── vector_store.py        # Postgres/Supabase + pgvector: schema, upsert, search
│   ├── retrieval.py           # hybrid retrieval: embeds the brief, calls vector_store
│   ├── ranking.py             # LLM ranking/reasoning step (structured JSON)
│   └── formatting.py          # stdout display helpers
└── tests/
    ├── test_pipeline.py       # offline tests, no external services required
    └── test_vector_store.py   # integration tests, need a live database
```

## Setup

1. Create a project at [supabase.com](https://supabase.com) (free tier is fine).

2. Enable pgvector: in the Supabase dashboard, go to **Database → Extensions**,
   search for `vector`, and enable it. (`vector_store.init_schema` also runs
   `CREATE EXTENSION IF NOT EXISTS vector` itself, so this step is a
   belt-and-suspenders check — Supabase's `postgres` role has permission to
   create it either way.)

3. Get your connection string: **Project Settings → Database → Connection
   string**, and pick the **Session pooler** option (not Transaction pooler —
   see note below). It'll look like:
   ```
   postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

4. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate   # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. Get a Gemini API key from https://aistudio.google.com/apikey, then:
   ```
   cp .env.example .env
   # edit .env: paste your GEMINI_API_KEY and Supabase DATABASE_URL
   ```

6. Run it:
   ```
   python main.py
   ```
   The first run generates the synthetic database and embeds + stores every
   profile in Supabase — that's the slow, API-call-heavy part. Every run
   after that reuses what's already indexed and skips straight to
   retrieval, unless you pass `--reindex`:
   ```
   python main.py --reindex
   ```

   Or with a custom brief:
   ```
   python main.py --niche "Fitness & wellness" --platform TikTok --budget 3000 \
       --audience "millennials, home gym" --vibe "high energy, no-nonsense"
   ```

   Run `python main.py --help` for all options.

### Session pooler vs. Transaction pooler vs. Direct connection

Supabase gives you three connection options — this matters more than it looks:

- **Session pooler** (recommended here): behaves like a normal Postgres
  connection, supports everything psycopg does. Use this for scripts and
  backends that hold a connection open, like this project.
- **Transaction pooler**: built for serverless/edge functions that open and
  close connections constantly. Runs in a mode that doesn't support
  prepared statements — `vector_store.get_connection()` already sets
  `prepare_threshold=None` to be safe if you use this anyway, but Session
  pooler is the simpler default.
- **Direct connection**: talks straight to the database, no pooler at all.
  On Supabase's free tier this is IPv6-only, so it often won't work from a
  typical home network or CI runner — Session pooler is the more portable
  choice.

### Local Postgres instead of Supabase

`docker-compose.yml` still works if you'd rather run Postgres locally
(`docker compose up -d`, then set `DATABASE_URL` to
`postgresql://postgres:postgres@localhost:5432/influencer_matcher`). The
schema and queries are identical either way — Supabase *is* Postgres, so
nothing in `vector_store.py` changes based on which one you use.

## Running tests

```
pytest
```

`test_pipeline.py` covers the deterministic/offline parts (data generation,
cosine similarity) and needs nothing running. `test_vector_store.py` needs
a live database at `DATABASE_URL` (Supabase or local) and skips itself
automatically if it can't connect, so `pytest` is always safe to run even
before the database is set up.

## How the pipeline works

1. **Generate** — `data_generator.py` builds a synthetic database of
   influencer profiles (niche, platform, followers, engagement, rate card).
2. **Index** (once, not per-run) — `embeddings.py` embeds every profile
   with `gemini-embedding-001`, then `vector_store.upsert_influencers`
   persists them in Postgres. `main.py` checks the row count first and
   skips this entirely if the table's already populated.
3. **Retrieve** — `retrieval.py` embeds the brand brief, then
   `vector_store.search` runs a single SQL query: `WHERE rate <= budget
   [AND platform = ...] ORDER BY embedding <=> query LIMIT k`. Metadata
   filtering and vector ranking happen together, in the database, not in
   Python.
4. **Rank** — `ranking.py` sends the top candidates to `gemini-2.5-flash`
   with a JSON schema, asking it to pick and justify the final shortlist.

## Extending this

- **Real influencer data**: replace `generate_influencers()` with calls to
  platform APIs (Instagram Graph API, TikTok, YouTube Data API) or an
  influencer-data provider (Upfluence, Modash, HypeAuditor). Keep returning
  a list of `Influencer` objects and nothing downstream changes — just call
  `vector_store.upsert_influencers` on new/changed profiles instead of the
  whole database each time.
- **Incremental re-indexing**: right now `--reindex` rebuilds everything.
  For a real, growing dataset you'd want to embed and upsert only new or
  changed rows — worth adding an `updated_at` column and a scheduled job.
- **A web UI**: `formatting.py` is intentionally the only place that knows
  about stdout — replace it with a Flask/FastAPI response and the rest of
  the pipeline is untouched.
