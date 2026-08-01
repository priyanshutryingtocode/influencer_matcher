"""CLI entry point for the influencer matching pipeline.

Usage:
    python main.py
    python main.py --niche "Fitness & wellness" --platform TikTok --budget 3000 \\
        --audience "millennials, home gym" --vibe "high energy, no-nonsense"
    python main.py --reindex   # clear and regenerate/re-embed the database
"""

import argparse

from src import config, vector_store
from src.data_generator import PLATFORMS, generate_influencers
from src.embeddings import index_influencers
from src.formatting import print_brief, print_results
from src.gemini_client import get_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import hybrid_retrieve


def positive_int(max_value: int | None = None):
    """argparse type factory: rejects zero/negative values (and, if given,
    anything above max_value) instead of silently accepting them and
    failing later inside a SQL LIMIT or an oversized Gemini batch."""

    def _parse(value: str) -> int:
        n = int(value)
        if n <= 0:
            raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
        if max_value is not None and n > max_value:
            raise argparse.ArgumentTypeError(f"must be <= {max_value}, got {n}")
        return n

    return _parse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match brand briefs to influencers using Gemini + RAG.")
    parser.add_argument("--niche", default="Sustainable fashion")
    parser.add_argument("--platform", default="Instagram", choices=["Any", *PLATFORMS])
    parser.add_argument("--budget", type=positive_int(), default=5000, help="Max budget per creator, in USD")
    parser.add_argument("--audience", default="Gen Z, sustainability-minded")
    parser.add_argument("--vibe", default="warm, low-key, not overly polished")
    parser.add_argument(
        "--count", type=positive_int(config.MAX_INFLUENCER_COUNT),
        default=config.DEFAULT_INFLUENCER_COUNT, help="Size of the synthetic database",
    )
    parser.add_argument(
        "--top-k", type=positive_int(config.MAX_TOP_K),
        default=config.DEFAULT_TOP_K_RETRIEVAL, help="Candidates to retrieve before ranking",
    )
    parser.add_argument(
        "--top-n", type=positive_int(config.MAX_TOP_K),
        default=config.DEFAULT_TOP_N_RANKED, help="Final shortlist size",
    )
    parser.add_argument("--reindex", action="store_true", help="Clear and regenerate/re-embed the database even if already populated")
    args = parser.parse_args()

    if args.top_n > args.top_k:
        parser.error(f"--top-n ({args.top_n}) can't be greater than --top-k ({args.top_k})")

    return args


def ensure_indexed(client, conn, args) -> None:
    """Only regenerate + re-embed if the table is empty or --reindex was
    passed. Generation and embedding happen entirely before any database
    write -- if Gemini fails partway (bad key, network, quota), nothing
    here has touched the database yet, so existing indexed data survives.
    The clear-and-write itself is atomic (see vector_store.replace_influencers)."""
    existing = vector_store.count_influencers(conn)
    if existing and not args.reindex:
        print(f"Found {existing} indexed profiles, skipping re-embedding.")
        return

    print("Generating synthetic influencer database...")
    influencers = generate_influencers(count=args.count)

    print(f"Embedding {len(influencers)} profiles with Gemini...")
    index_influencers(client, influencers)

    print("Writing to the database (atomic replace)...")
    vector_store.replace_influencers(conn, influencers)


def main() -> None:
    args = parse_args()
    client = get_client()

    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)
        ensure_indexed(client, conn, args)

        brief = Brief(
            niche=args.niche,
            platform=args.platform,
            budget_max=args.budget,
            audience=args.audience,
            vibe=args.vibe,
        )
        print_brief(brief)

        print("\nRetrieving candidates (metadata filter + pgvector search)...")
        candidates = hybrid_retrieve(client, conn, brief, top_k=args.top_k)
        if not candidates:
            print("No creators fit that budget/platform combination.")
            return
        print(f"  {len(candidates)} candidates returned")

        print("\nRanking with Gemini...")
        ranked = rank_candidates(client, brief, candidates, top_n=args.top_n)

    candidates_by_id = {c.id: c for c in candidates}
    print_results(ranked, candidates_by_id, niche=args.niche)


if __name__ == "__main__":
    main()