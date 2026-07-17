"""CLI entry point for the influencer matching pipeline.

Usage:
    python main.py
    python main.py --niche "Fitness & wellness" --platform TikTok --budget 3000 \\
        --audience "millennials, home gym" --vibe "high energy, no-nonsense"
"""

import argparse

from src import config
from src.data_generator import PLATFORMS, generate_influencers
from src.embeddings import index_influencers
from src.formatting import print_brief, print_results
from src.gemini_client import get_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import hybrid_retrieve


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match brand briefs to influencers using Gemini + RAG.")
    parser.add_argument("--niche", default="Sustainable fashion")
    parser.add_argument("--platform", default="Instagram", choices=["Any", *PLATFORMS])
    parser.add_argument("--budget", type=int, default=5000, help="Max budget per creator, in USD")
    parser.add_argument("--audience", default="Gen Z, sustainability-minded")
    parser.add_argument("--vibe", default="warm, low-key, not overly polished")
    parser.add_argument("--count", type=int, default=config.DEFAULT_INFLUENCER_COUNT, help="Size of the synthetic database")
    parser.add_argument("--top-k", type=int, default=config.DEFAULT_TOP_K_RETRIEVAL, help="Candidates to retrieve before ranking")
    parser.add_argument("--top-n", type=int, default=config.DEFAULT_TOP_N_RANKED, help="Final shortlist size")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = get_client()

    print("Generating synthetic influencer database...")
    influencers = generate_influencers(count=args.count)

    print(f"Indexing {len(influencers)} profiles (embedding)...")
    index_influencers(client, influencers)

    brief = Brief(
        niche=args.niche,
        platform=args.platform,
        budget_max=args.budget,
        audience=args.audience,
        vibe=args.vibe,
    )
    print_brief(brief)

    print("\nRetrieving candidates (hard filters + semantic search)...")
    candidates = hybrid_retrieve(client, brief, influencers, top_k=args.top_k)
    if not candidates:
        print("No creators fit that budget/platform combination.")
        return
    print(f"  {len(candidates)} candidates passed filters + retrieval")

    print("\nRanking with Gemini...")
    ranked = rank_candidates(client, brief, candidates, top_n=args.top_n)

    candidates_by_id = {c.id: c for c in candidates}
    print_results(ranked, candidates_by_id)


if __name__ == "__main__":
    main()
