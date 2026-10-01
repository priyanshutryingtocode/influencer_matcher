"""CLI entry point for the influencer matching pipeline.

Usage:
    python main.py
    python main.py --goal "high-energy strength training for beginners" --platform TikTok \\
        --audience "millennials, home gym" --vibe "high energy, no-nonsense"
    python main.py --reindex   # clear and regenerate/re-embed the database
    python main.py --limit 5   # embedding smoke test, writes nothing
"""

import argparse
import sys
from pathlib import Path

from api.repositories.postgres_run_repository import PostgresRunRepository
from src import config, vector_store
from src.data_generator import generate_balanced_influencers, generate_influencers
from src.platforms import PLATFORMS
from src.embeddings import EmbeddingCache, index_influencers, text_key
from src.formatting import print_brief, print_results
from src.gemini_client import DailyQuotaExhausted, get_client
from src.match_service import rank_match, retrieve_candidates
from src.models import Brief

CACHE_DIR = Path(__file__).resolve().parent / ".embed-cache"
# A cache this large is worth protecting, so warn when a run is about to spend
# fresh requests. Mid-build is never mistaken for a mistake: a build in progress
# reuses a growing *share* of the cache, whereas a corpus switch reuses almost
# none of it on every run and every one of those vectors is wasted.
_ORPHAN_WARN_MIN = 50
_MIN_CACHE_REUSE_RATIO = 0.05


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
    parser.add_argument(
        "--goal",
        default="a thrifted-vintage clothing label for Gen Z who care about slow fashion",
        help="Free-text description of what the brand wants",
    )
    parser.add_argument("--platform", default="Instagram", choices=["Any", *PLATFORMS])
    parser.add_argument("--audience", default="Gen Z")
    parser.add_argument("--vibe", default="warm, friendly")
    parser.add_argument(
        "--count", type=positive_int(config.MAX_INFLUENCER_COUNT),
        default=config.DEFAULT_INFLUENCER_COUNT, help="Size of the synthetic database",
    )
    parser.add_argument(
        "--balanced", action="store_true", 
        help="Generate balanced dataset with a minimum floor per (topic group, platform) cell"
    )
    parser.add_argument(
        "--balanced-floor", type=positive_int(),
        default=3,
        help="--balanced only: minimum profiles per (topic group, platform) cell; "
             "sets the dataset's minimum size (groups x platforms x floor)",
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
    parser.add_argument("--index-only", action="store_true", help="Initialize or populate the creator index without running a sample match")
    parser.add_argument(
        "--limit", type=positive_int(),
        help="Embed only the first N profiles and write nothing. Use it to smoke "
             "test the embedding API before spending a full reindex's quota.",
    )
    parser.add_argument(
        "--embed-cache", type=Path,
        help="Vector cache to reuse and append to (default: backend/.embed-cache/).",
    )
    parser.add_argument(
        "--no-embed-cache", action="store_true",
        help="Ignore any cached vectors and re-embed every profile.",
    )
    args = parser.parse_args()

    if args.top_n > args.top_k:
        parser.error(f"--top-n ({args.top_n}) can't be greater than --top-k ({args.top_k})")

    return args


def default_cache_path() -> Path:
    safe_model = config.EMBED_MODEL.replace("/", "_")
    return CACHE_DIR / f"{safe_model}-{config.EMBED_DIMENSIONS}d.jsonl"


def ensure_indexed(args) -> None:
    """Only regenerate + re-embed if the table is empty or --reindex was
    passed. Generation and embedding happen entirely before any database
    write -- if anything fails partway (bad key, network, quota), nothing
    here has touched the database yet, so existing indexed data survives.
    """
    embed_only = bool(args.limit) and not args.index_only

    if not embed_only:
        with vector_store.get_connection() as conn:
            existing = vector_store.count_influencers(conn)
        if existing and not args.reindex:
            print(f"Found {existing} indexed profiles, skipping re-embedding.")
            return

    print("Generating synthetic influencer database...")
    if args.balanced:
        influencers = generate_balanced_influencers(
            count=args.count, min_per_group_platform=args.balanced_floor
        )
    else:
        influencers = generate_influencers(count=args.count)
    if args.limit:
        influencers = influencers[:args.limit]

    cache = None
    if not args.no_embed_cache:
        cache = EmbeddingCache(args.embed_cache or default_cache_path())

    _report_remaining_work(influencers, cache)

    print(f"Embedding {len(influencers)} profiles with {config.EMBED_MODEL} "
          f"({config.EMBED_DIMENSIONS}d)...")
    try:
        index_influencers(influencers, cache=cache)
    except DailyQuotaExhausted as exc:
        _report_cache(cache)
        print(str(exc), file=sys.stderr)
        print(
            "Nothing was lost: re-run the same command after the reset and the "
            "cached vectors are reused, so only the remaining creators are billed.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
    _report_cache(cache)

    if embed_only:
        print("--limit was used, so the database was left untouched. "
              "Re-run without --limit to write the index.")
        return

    print("Writing to the database (atomic replace)...")
    with vector_store.get_connection() as conn:
        vector_store.replace_influencers(conn, influencers)
    return True


def _report_remaining_work(influencers, cache: EmbeddingCache | None) -> None:
    """Say what a reindex is about to cost before it costs anything.

    Embeddings are billed per creator and the free tier caps them per day, so a
    large build is expected to stop at the cap and resume. That must not be
    reported the same way as a run that is about to waste an already-paid-for
    cache because the flags changed, so the two cases are told apart by whether
    the cache holds vectors this dataset cannot use.
    """
    if cache is None:
        print(f"No vector cache in use: {len(influencers)} requests will be spent.")
        return

    keys = [text_key(influencer.corpus_text()) for influencer in influencers]
    reusable = sum(1 for key in keys if cache.contains(key))
    remaining = len(keys) - reusable
    interval = config.EMBED_REQUEST_INTERVAL_SECONDS
    estimate = f"~{int(remaining * interval)}s" if interval > 0 else "no throttle"
    print(f"Vector cache: {len(cache)} vectors in {cache.path}")
    print(f"Reusing {reusable} of {len(keys)} creators; "
          f"{remaining} requests still needed ({estimate}).")

    if len(cache) >= _ORPHAN_WARN_MIN and reusable < len(cache) * _MIN_CACHE_REUSE_RATIO:
        print(
            f"WARNING: only {reusable} of the {len(cache)} cached vectors belong to this "
            f"dataset. The generator is seeded, so a reindex only reuses cached vectors "
            f"when --count and --balanced-floor match the previous run. Continuing spends "
            f"{remaining} fresh requests, and the rest of the cache goes unused.",
            file=sys.stderr,
        )
    elif remaining:
        print(
            "The free tier caps embedding at 1,000 requests/day, so a build this size "
            "stops at the cap and resumes from this cache on the next run. The database "
            "is only written once every creator is embedded."
        )


def _report_cache(cache: EmbeddingCache | None) -> None:
    if cache is None:
        return
    print(f"Embedding API calls this run: {cache.misses} "
          f"({cache.hits} reused, {len(cache)} vectors banked in {cache.path}).")


def main() -> None:
    args = parse_args()

    PostgresRunRepository().ensure_schema()
    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)

    ensure_indexed(args)
    if args.index_only or args.limit:
        return

    brief = Brief(
        goal=args.goal,
        platform=args.platform,
        audience=args.audience,
        vibe=args.vibe,
    )
    print_brief(brief)

    print("\nRetrieving candidates (metadata filter + pgvector search)...")
    candidates = retrieve_candidates(brief, top_k=args.top_k)
    if not candidates:
        print("No creators found for that platform.")
        return
    print(f"  {len(candidates)} candidates returned")

    print("\nRanking with Gemini...")
    ranked = rank_match(brief, candidates, top_n=args.top_n, client=get_client())

    candidates_by_id = {c.id: c for c in candidates}
    print_results(ranked, candidates_by_id, brief=brief)


if __name__ == "__main__":
    main()
