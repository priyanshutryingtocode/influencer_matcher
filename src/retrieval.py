"""Hybrid retrieval: structured metadata filters (budget, platform) applied
first, then semantic search over the filtered pool.

Filtering first matters -- there's no point spending an embedding call and
comparing vectors against creators who don't fit the budget in the first
place. Real vector DBs (Pinecone, Weaviate, pgvector) support this natively
via metadata filters alongside the vector index.
"""

from google import genai

from .embeddings import cosine_sim, embed_texts
from .models import Brief, Influencer


def hybrid_retrieve(
    client: genai.Client,
    brief: Brief,
    influencers: list[Influencer],
    top_k: int = 10,
) -> list[Influencer]:
    pool = [inf for inf in influencers if inf.rate <= brief.budget_max]
    if brief.platform != "Any":
        pool = [inf for inf in pool if inf.platform == brief.platform]

    if not pool:
        return []

    query_vec = embed_texts(client, [brief.query_text()], task_type="RETRIEVAL_QUERY")[0]
    scored = [(inf, cosine_sim(query_vec, inf.embedding)) for inf in pool]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [inf for inf, _ in scored[:top_k]]
