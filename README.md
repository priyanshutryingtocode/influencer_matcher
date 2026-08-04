# Influencer Matcher

A small RAG pipeline that matches a brand brief to influencer profiles:
platform is a hard filter, niche/audience/vibe are matched semantically via
Postgres + pgvector, and Gemini generation ranks the final shortlist with an
honest fit rating and a rationale per pick. Currently runs on a synthetic, seeded
influencer database — swap `src/data_generator.py` for a real data source
when you're ready.

## Project structure

```
influencer_matcher/
├── main.py                  # CLI entry point, wires the pipeline together
├── app.py                    # Streamlit interface (same pipeline, browser UI)
├── evaluate.py               # golden-brief evaluation harness → evaluation-report.json
├── evaluation-report.json    # last run's metrics output
├── requirements.txt
├── .env                      # (gitignored) GEMINI_API_KEY + DATABASE_URL
├── data/
│   └── evaluation_cases.json # versioned golden briefs for evaluate.py
└── src/
    ├── config.py              # model names, defaults, env loading
    ├── models.py               # Influencer and Brief data classes
    ├── data_generator.py       # synthetic influencer database
    ├── gemini_client.py        # Gemini API client factory (timeout + retries)
    ├── embeddings.py           # embedding computation
    ├── vector_store.py         # Postgres/Supabase + pgvector: schema, replace, search
    ├── retrieval.py            # embeds the brief, calls vector_store
    ├── ranking.py              # LLM ranking/reasoning step (structured JSON, validated)
    └── formatting.py           # stdout display helpers
```

## Setup

1. Create a project at [supabase.com](https://supabase.com) (free tier is fine).

2. Enable pgvector: in the Supabase dashboard, go to **Database → Extensions**,
   search for `vector`, and enable it. (`vector_store.init_schema` also runs
   `CREATE EXTENSION IF NOT EXISTS vector` itself, so this step is a
   belt-and-suspenders check.)

3. Get your connection string: on your project's main dashboard page,
   click **Connect** in the top bar (this used to live under Project
   Settings → Database — Supabase moved it). In the panel that opens, go to
   the **Session pooler** tab (not Transaction pooler — see note below) and
   copy the URI. It'll look like:
   ```
   postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
   Replace `[YOUR-PASSWORD]` in the copied string with your actual database
   password.

   **Not the Project URL.** The Project URL (`https://<ref>.supabase.co`,
   shown on the API settings page) is the REST/PostgREST endpoint for the
   `supabase-py` client — it's HTTPS, not a Postgres connection, and can't
   run the raw SQL this project uses (in particular, `ORDER BY embedding <=>
   ...`, pgvector's distance operator, isn't expressible through PostgREST's
   query builder). This project needs the `postgresql://...` connection
   string above, not the Project URL.

   **Creating the tables:** running `python main.py` or `streamlit run app.py`
   creates everything automatically on first connect (`init_schema()`).
   There's no separate schema file to run — `init_schema()` handles the
   extension and tables, and is safe to re-run on every start.

4. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate   # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. Get a Gemini API key from https://aistudio.google.com/apikey, then create a
   `.env` file in this directory (there's no example file shipped — `.env` is
   gitignored) with:
   ```
   GEMINI_API_KEY=your-key-here
   DATABASE_URL=your-supabase-connection-string
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
   python main.py --niche Fitness --platform TikTok \
       --audience "millennials, home gym" --vibe "high energy, no-nonsense"
   ```

   Run `python main.py --help` for all options. There's no `--budget` flag
   — budget isn't part of matching in this project (see above).

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

This project works against any Postgres instance with the `pgvector` extension
available. There's no bundled `docker-compose.yml`, so to run locally you'd
install Postgres, enable pgvector (e.g. `CREATE EXTENSION IF NOT EXISTS vector`
— `init_schema()` also runs this itself), and set `DATABASE_URL` to something
like `postgresql://postgres:postgres@localhost:5432/influencer_matcher`. The
schema and queries are identical either way — Supabase *is* Postgres, so
nothing in `vector_store.py` changes based on which one you use.

## Streamlit interface

For a UI instead of the CLI:

```
streamlit run app.py
```

Sidebar form for the brand brief (niche, platform, audience, vibe — no
budget field) plus a **Build/Rebuild database** button. Results render as
cards with follower and engagement metrics, a 🟢🟡🔴 fit badge, and the
Gemini-written rationale per pick. It reuses `src/` entirely — same
retrieval, same ranking, same database connection logic as the CLI.

## Evaluating retrieval and ranking

Run the versioned golden-brief set after indexing creators:

```
python evaluate.py
```

This writes `evaluation-report.json` with per-case and aggregate metrics:

- retrieval niche precision@K and niche hit rate@K;
- ranked niche precision@N;
- Gemini fallback rate; and
- retrieval and ranking latency.

The included synthetic cases define relevance as an exact niche match. For
real creator data, replace or extend `data/evaluation_cases.json` with
human-labelled campaign briefs and accepted creator IDs/niches. Keep prior
reports to compare quality after changing models, prompts, embeddings, or
retrieval parameters.

## How the pipeline works

1. **Generate** — `data_generator.py` builds a synthetic database of
   influencer profiles using Faker for realistic handles, cities, and bios,
   plus seeded local logic for niche, platform, followers, engagement, and tags.
2. **Index** (once, not per-run) — `embeddings.py` embeds every profile
   with `gemini-embedding-001`, entirely in memory. Only once that's fully
   succeeded does `vector_store.replace_influencers()` write to the
   database — it clears and inserts the new set inside a single
   transaction, so a failure partway through a rebuild can't leave the
   table empty (the previous data stays intact if the write fails).
   `main.py`/`app.py` check the row count first and skip re-embedding
   entirely if the table's already populated, unless you force a rebuild.
3. **Retrieve** — `retrieval.py` embeds the brand brief (niche, audience,
   vibe — no budget), then `vector_store.search` runs one SQL query:
   `[WHERE platform = ...] ORDER BY embedding <=> query LIMIT k`. Platform
   is the only hard filter; niche match is semantic, not guaranteed, so the
   app also reports how many retrieved candidates actually share the
   requested niche (`niche_coverage`) and warns if that ratio is low. Each
   result shows cosine-based semantic relevance plus deterministic evidence
   from matching niche, tags, bio, audience, and vibe terms; this evidence is
   derived from stored fields rather than invented by the ranking model.
4. **Rank** — `ranking.py` sends the top candidates to `gemini-2.5-flash`
   with a JSON schema, asking it to pick the best ones and rate each
   honestly as `strong` / `partial` / `weak`. That rating isn't trusted
   blindly: a candidate whose niche doesn't match the brief is
   deterministically capped at `partial`, regardless of what the model
   claims. If the model returns fewer valid picks than requested, the rest
   are filled from retrieval order rather than returning a short list; if
   the whole call fails, results fall back to retrieval order with a
   generic notice (the actual error is logged server-side, not shown to
   the user).

## Extending this

- **Real influencer data**: replace `generate_influencers()` with calls to
  platform APIs (Instagram Graph API, TikTok, YouTube Data API) or an
  influencer-data provider (Upfluence, Modash, HypeAuditor). Keep returning
  a list of `Influencer` objects and nothing downstream changes.
- **Incremental re-indexing**: right now a rebuild replaces every row.
  For a real, growing dataset you'd want to embed and upsert only new or
  changed rows — worth adding an `updated_at` column and a scheduled job
  (the `embed_model`/`content_hash` columns already there are a starting
  point for detecting which rows actually need re-embedding).
- **A web UI beyond Streamlit**: `formatting.py` is intentionally the only
  place that knows about stdout — replace it with a Flask/FastAPI response
  and the rest of the pipeline is untouched.
