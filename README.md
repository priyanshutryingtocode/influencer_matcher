# Influencer Matcher

A RAG pipeline that matches brand briefs to influencer profiles using Postgres + pgvector for semantic search and Gemini for final ranking with fit ratings and rationales. Runs on a synthetic, seeded influencer database (swap `src/data_generator.py` for real data).

## Key Features

- **Local embeddings**: Sentence Transformers (`all-mpnet-base-v2`, 768-dim) — no API costs
- **Platform hard filter**, niche/audience/vibe semantic matching
- **Balanced data generation**: `--balanced` flag ensures minimum representation per (niche, platform)
- **Max 1000 profiles** per run
- **15 evaluation cases** covering niche×platform combinations

## Project Structure

```
influencer_matcher/
├── main.py                   # CLI entry point
├── app.py                    # Streamlit navigation shell
├── views/                    # Streamlit pages + UI support modules
│   ├── shared.py             #   cached clients, DB access, run_pipeline()
│   ├── search.py             #   Search page (brief → shortlist → CSV)
│   ├── history.py            #   History page (.runs/ browser)
│   ├── compare.py            #   Compare page (side-by-side runs)
│   ├── cards.py              #   reusable result-card renderer
│   ├── compare_logic.py      #   pure diff/summary math
│   └── run_store.py          #   local JSON persistence + CSV export
├── evaluate.py               # golden-brief evaluation → evaluation-report.json
├── requirements.txt
├── .env                      # GEMINI_API_KEY + DATABASE_URL (gitignored)
├── data/
│   └── evaluation_cases.json # 15 golden briefs
└── src/
    ├── config.py             # models, defaults, env loading
    ├── models.py             # Influencer, Brief dataclasses
    ├── data_generator.py     # synthetic DB (random + balanced modes)
    ├── gemini_client.py      # Gemini API client (ranking only)
    ├── embeddings.py         # local Sentence Transformer embeddings
    ├── vector_store.py       # Postgres/pgvector: schema, search, HNSW
    ├── retrieval.py          # embeds brief, calls vector_store
    ├── ranking.py            # LLM ranking with structured JSON
    └── formatting.py         # display helpers
```

## Setup

1. **Supabase** (free tier): create project, enable `pgvector` extension, get **Session pooler** connection string
2. **Virtual env & deps**:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **`.env` file**:
   ```
   GEMINI_API_KEY=your-key
   DATABASE_URL=postgresql://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

## Usage

```bash
# First run: generates + indexes database (uses local embeddings)
python main.py

# Rebuild with 500 balanced profiles
python main.py --count 500 --reindex --balanced

# Max size (1000)
python main.py --count 1000 --reindex --balanced

# Denser coverage per (niche, platform): count must be >= niches x platforms x floor
# (30 x 9 = 270 combos, so floor 3 is the max that fits the 1000-profile cap)
python main.py --count 810 --reindex --balanced --balanced-floor 3

# Custom brief
python main.py --niche Fitness --platform TikTok \
    --audience "millennials, home gym" --vibe "high energy"

# Run evaluation (15 cases)
python evaluate.py
```

## Streamlit UI

```bash
streamlit run app.py
```

A three-page interface (requires streamlit >= 1.40):

- **Search** — brief form in the main area (niche, platform, audience, vibe) with staged progress, result cards showing fit badge, tier, metrics, rationale, and expandable match evidence; every successful run is saved locally and can be exported as CSV
- **History** — browse/reopen/delete past shortlists (stored as JSON files under `.runs/`, gitignored)
- **Compare** — side-by-side shortlists from any two runs, with shared creators highlighted and summary deltas

**No database build button** — data must be pre-indexed via CLI. History/Compare work offline from local files; Search needs the database.

## Embedding Backend

Embeddings are computed locally with Sentence Transformers — no API cost, no
network calls. Configured in `src/config.py`:
```python
LOCAL_EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBED_DIMENSIONS = 768
```
The model name is stored per-row in the database (`embed_model` column) so
vector provenance stays traceable. Changing the model requires a `--reindex`.

## Evaluation

```bash
python evaluate.py
```
Outputs `evaluation-report.json` with retrieval precision@K, ranked precision@N, fallback rate, and latency. 15 cases cover "Any" platform and platform-specific briefs.

