# Influencer Matcher

A small RAG pipeline that matches a brand brief to influencer profiles:
hard filters (budget, platform) narrow the pool, Gemini embeddings do
semantic retrieval over what's left, and Gemini generation ranks the final
shortlist with a rationale per pick. Currently runs on a synthetic,
seeded influencer database — swap `src/data_generator.py` for a real data
source when you're ready.

## Project structure

```
influencer_matcher/
├── main.py                  # CLI entry point, wires the pipeline together
├── requirements.txt
├── .env.example
├── src/
│   ├── config.py             # model names, defaults, env loading
│   ├── models.py              # Influencer and Brief data classes
│   ├── data_generator.py      # synthetic influencer database
│   ├── gemini_client.py       # Gemini API client factory
│   ├── embeddings.py          # embedding + indexing (cosine similarity)
│   ├── retrieval.py           # hybrid retrieval: filters + semantic search
│   ├── ranking.py             # LLM ranking/reasoning step (structured JSON)
│   └── formatting.py          # stdout display helpers
└── tests/
    └── test_pipeline.py       # offline tests, no API key required
```

## Setup

1. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate   # on Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Get a Gemini API key from https://aistudio.google.com/apikey, then:
   ```
   cp .env.example .env
   # edit .env and paste your key in
   ```

3. Run it:
   ```
   python main.py
   ```

   Or with a custom brief:
   ```
   python main.py --niche "Fitness & wellness" --platform TikTok --budget 3000 \
       --audience "millennials, home gym" --vibe "high energy, no-nonsense"
   ```

   Run `python main.py --help` for all options.

## Running tests

```
pytest
```

These tests cover the deterministic/offline parts of the pipeline (data
generation, cosine similarity, filter logic) and don't call the Gemini API,
so they run without a key.

## How the pipeline works

1. **Generate** — `data_generator.py` builds a synthetic database of
   influencer profiles (niche, platform, followers, engagement, rate card).
2. **Index** — `embeddings.py` embeds every profile with
   `gemini-embedding-001`. In production you'd persist these vectors in a
   real vector database (Pinecone, Weaviate, pgvector) instead of
   recomputing them each run.
3. **Retrieve** — `retrieval.py` applies hard metadata filters (budget,
   platform) first, then embeds the brand brief and ranks the filtered pool
   by cosine similarity.
4. **Rank** — `ranking.py` sends the top candidates to `gemini-2.5-flash`
   with a JSON schema, asking it to pick and justify the final shortlist.

## Extending this

- **Real influencer data**: replace `generate_influencers()` with calls to
  platform APIs (Instagram Graph API, TikTok, YouTube Data API) or an
  influencer-data provider (Upfluence, Modash, HypeAuditor). Keep returning
  a list of `Influencer` objects and nothing downstream changes.
- **Persisted vector store**: swap the in-memory `.embedding` field on each
  `Influencer` for a real vector DB client in `embeddings.py` and
  `retrieval.py`.
- **A web UI**: `formatting.py` is intentionally the only place that knows
  about stdout — replace it with a Flask/FastAPI response and the rest of
  the pipeline is untouched.
