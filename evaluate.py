"""Evaluate retrieval and ranking against a versioned golden brief set.

Usage:
    python evaluate.py
    python evaluate.py --top-k 10 --top-n 5 --output evaluation-report.json

Exact niche match is the relevance label for this synthetic dataset. Replace
these cases with human-labelled outcomes when real creator data is available.
"""

import argparse
import json
import time
from pathlib import Path
from statistics import mean
from time import perf_counter

from src import config, vector_store
from src.embeddings import embed_texts
from src.gemini_client import get_client, get_embedding_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import hybrid_retrieve

DEFAULT_CASES = Path("data/evaluation_cases.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate influencer retrieval and ranking quality.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="JSON golden-brief dataset")
    parser.add_argument("--output", type=Path, default=Path("evaluation-report.json"), help="JSON metrics output")
    parser.add_argument("--top-k", type=int, default=config.DEFAULT_TOP_K_RETRIEVAL)
    parser.add_argument("--top-n", type=int, default=config.DEFAULT_TOP_N_RANKED)
    parser.add_argument(
        "--rate-limit-per-min", type=int, default=10,
        help="Max ranking requests per minute to throttle to (free tier = 10). "
             "Spreads cases out so the run doesn't trip the API burst quota.",
    )
    args = parser.parse_args()
    if args.top_k <= 0 or args.top_n <= 0 or args.top_n > args.top_k:
        parser.error("top-k and top-n must be positive, and top-n cannot exceed top-k")
    if args.rate_limit_per_min <= 0:
        parser.error("--rate-limit-per-min must be positive")
    return args


def niche_precision(items, expected_niche: str) -> float:
    return sum(item.niche == expected_niche for item in items) / len(items) if items else 0.0


def _warmup(conn, embedding_client) -> None:
    """Absorb cold-start costs (embedding-model load + first HNSW query) so
    case #1 isn't timed against them. Without this, the very first retrieval
    pays a multi-second model load plus a cold full-table scan over the Any
    platform, inflating one case's retrieval_latency by ~45s."""
    query_vec = embed_texts(
        embedding_client, ["warmup"], task_type="RETRIEVAL_QUERY"
    )[0]
    vector_store.search(conn, query_embedding=query_vec, platform="Any", top_k=1)


def main() -> None:
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        raise RuntimeError("Evaluation dataset is empty")

    client = get_client()
    embedding_client = get_embedding_client()
    case_results = []
    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)
        if not vector_store.count_influencers(conn):
            raise RuntimeError("No indexed creators. Run main.py --reindex before evaluating.")
        _warmup(conn, embedding_client)

        spacing = 60.0 / args.rate_limit_per_min
        for i, case in enumerate(cases):
            # Each case is one ranking call; space them out so the burst stays
            # under the per-minute quota instead of tripping a 429 mid-run.
            if i > 0 and spacing > 0:
                time.sleep(spacing)

            brief = Brief(
                niche=case["niche"], platform=case.get("platform", "Any"),
                audience=case.get("audience", ""), vibe=case.get("vibe", ""),
            )
            expected_niche = case.get("expected_niche", brief.niche)
            retrieval_start = perf_counter()
            candidates = hybrid_retrieve(client, conn, brief, top_k=args.top_k)
            retrieval_ms = round((perf_counter() - retrieval_start) * 1000, 1)

            ranking_start = perf_counter()
            ranked = rank_candidates(client, brief, candidates, top_n=args.top_n)
            ranking_ms = round((perf_counter() - ranking_start) * 1000, 1)
            candidate_by_id = {candidate.id: candidate for candidate in candidates}
            ranked_candidates = [candidate_by_id[item["id"]] for item in ranked]

            case_results.append({
                "id": case["id"],
                "expected_niche": expected_niche,
                "retrieved_count": len(candidates),
                "retrieval_niche_precision_at_k": round(niche_precision(candidates, expected_niche), 3),
                "retrieval_niche_hit_at_k": any(c.niche == expected_niche for c in candidates),
                "ranked_niche_precision_at_n": round(niche_precision(ranked_candidates, expected_niche), 3),
                "ranking_fallback": any(item.get("source") == "fallback" for item in ranked),
                "retrieval_latency_ms": retrieval_ms,
                "ranking_latency_ms": ranking_ms,
            })

    report = {
        "cases": case_results,
        "summary": {
            "case_count": len(case_results),
            "mean_retrieval_niche_precision_at_k": round(mean(item["retrieval_niche_precision_at_k"] for item in case_results), 3),
            "retrieval_niche_hit_rate_at_k": round(mean(item["retrieval_niche_hit_at_k"] for item in case_results), 3),
            "mean_ranked_niche_precision_at_n": round(mean(item["ranked_niche_precision_at_n"] for item in case_results), 3),
            "ranking_fallback_rate": round(mean(item["ranking_fallback"] for item in case_results), 3),
            "mean_retrieval_latency_ms": round(mean(item["retrieval_latency_ms"] for item in case_results), 1),
            "mean_ranking_latency_ms": round(mean(item["ranking_latency_ms"] for item in case_results), 1),
        },
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Full per-case report written to {args.output}")


if __name__ == "__main__":
    main()
