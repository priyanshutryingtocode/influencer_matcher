"""Evaluate retrieval and ranking against a versioned golden brief set.

Usage:
    python evaluate.py
    python evaluate.py --top-k 10 --top-n 5 --output evaluation-report.json
    python evaluate.py --sequential   # old one-at-a-time pacing

Exact niche match is the relevance label for this synthetic dataset. Replace
these cases with human-labelled outcomes when real creator data is available.

Cases run in batches sized to the rate limit (default 10/minute): each batch
fires concurrently, then the runner waits out the rest of that minute-window
before the next batch. Per-case latency timings are unaffected -- they only
cover that case's own retrieval/ranking work.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean
from time import perf_counter

from src import config, vector_store
from src.embeddings import embed_texts, get_cached_query_vector
from src.gemini_client import get_client
from src.models import Brief
from src.ranking import rank_candidates
from src.retrieval import niche_prior_sort

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
             "Cases run in concurrent batches of this size.",
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Run cases one at a time with even spacing (pre-parallel behavior).",
    )
    args = parser.parse_args()
    if args.top_k <= 0 or args.top_n <= 0 or args.top_n > args.top_k:
        parser.error("top-k and top-n must be positive, and top-n cannot exceed top-k")
    if args.rate_limit_per_min <= 0:
        parser.error("--rate-limit-per-min must be positive")
    return args


def batch_windows(total: int, per_minute: int) -> list[list[int]]:
    """Split case indices into rate-limit windows: window w gets indices
    [w*per_minute, (w+1)*per_minute). Pure so the scheduling math is testable."""
    if per_minute <= 0 or total <= 0:
        return []
    return [
        list(range(start, min(start + per_minute, total)))
        for start in range(0, total, per_minute)
    ]


def niche_precision(items, expected_niche: str) -> float:
    return sum(item.niche == expected_niche for item in items) / len(items) if items else 0.0


def _warmup(conn) -> None:
    """Absorb cold-start costs (embedding-model load + first HNSW query) so
    case #1 isn't timed against them. Without this, the very first retrieval
    pays a multi-second model load plus a cold full-table scan over the Any
    platform, inflating one case's retrieval_latency by ~45s."""
    query_vec = embed_texts(["warmup"])[0]
    vector_store.search(conn, query_embedding=query_vec, platform="Any", top_k=1)


def _run_case(client, case: dict, top_k: int, top_n: int) -> dict:
    brief = Brief(
        niche=case["niche"], platform=case.get("platform", "Any"),
        audience=case.get("audience", ""), vibe=case.get("vibe", ""),
    )
    expected_niche = case.get("expected_niche", brief.niche)

    # Split embed vs search timing so the report can distinguish model
    # cost (Task 5) from index cost (Task 4). Connection checkout stays
    # outside timing; retrieval_ms remains the sum for backward compat.
    embed_start = perf_counter()
    query_vec = get_cached_query_vector(brief.query_text())
    embed_ms = round((perf_counter() - embed_start) * 1000, 1)

    with vector_store.get_connection() as conn:
        # Replicate hybrid_retrieve's over-fetch + SQL niche boost + Python
        # prior, but timed as one search block. Keeps hybrid_retrieve's API
        # untouched for app code.
        search_start = perf_counter()
        fetch_k = min(top_k * 3, config.MAX_TOP_K)
        candidates_raw = vector_store.search(
            conn,
            query_embedding=query_vec,
            platform=brief.platform,
            top_k=fetch_k,
            niche=brief.niche,
        )
        candidates = niche_prior_sort(candidates_raw, brief.niche)[:top_k]
        search_ms = round((perf_counter() - search_start) * 1000, 1)

    retrieval_ms = round(embed_ms + search_ms, 1)

    ranking_start = perf_counter()
    ranked = rank_candidates(client, brief, candidates, top_n=top_n)
    ranking_ms = round((perf_counter() - ranking_start) * 1000, 1)

    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    ranked_candidates = [candidate_by_id[item["id"]] for item in ranked]
    return {
        "id": case["id"],
        "expected_niche": expected_niche,
        "retrieved_count": len(candidates),
        "retrieval_niche_precision_at_k": round(niche_precision(candidates, expected_niche), 3),
        "retrieval_niche_hit_at_k": any(c.niche == expected_niche for c in candidates),
        "ranked_niche_precision_at_n": round(niche_precision(ranked_candidates, expected_niche), 3),
        "ranking_fallback": any(item.get("source") == "fallback" for item in ranked),
        # Degradation + fit observability: nonzero filled/fallback counts mean
        # slots came from retrieval order (where the niche prior operates)
        # rather than LLM judgment; strong counts show how confident the
        # ranker was overall.
        "fallback_count": sum(1 for item in ranked if item.get("source") == "fallback"),
        "filled_count": sum(1 for item in ranked if item.get("source") == "filled"),
        "strong_fit_count": sum(1 for item in ranked if item.get("fit") == "strong"),
        "retrieval_latency_ms": retrieval_ms,
        "embed_latency_ms": embed_ms,
        "search_latency_ms": search_ms,
        "ranking_latency_ms": ranking_ms,
    }


def main() -> None:
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        raise RuntimeError("Evaluation dataset is empty")

    client = get_client()
    case_results: list[dict | None] = [None] * len(cases)

    # Warm the model + pool before any timing; also verifies data exists.
    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)
        if not vector_store.count_influencers(conn):
            raise RuntimeError("No indexed creators. Run main.py --reindex before evaluating.")
        _warmup(conn)

    started = perf_counter()

    if args.sequential:
        spacing = 60.0 / args.rate_limit_per_min
        for idx, case in enumerate(cases):
            if idx > 0:
                time.sleep(spacing)
            case_results[idx] = _run_case(client, case, args.top_k, args.top_n)
    else:
        windows = batch_windows(len(cases), args.rate_limit_per_min)
        for w, window in enumerate(windows):
            window_start = perf_counter()
            if len(windows) > 1:
                print(f"Window {w + 1}/{len(windows)}: cases "
                      f"{window[0] + 1}-{window[-1] + 1} firing concurrently...")
            with ThreadPoolExecutor(max_workers=len(window)) as pool:
                futures = {
                    idx: pool.submit(_run_case, client, cases[idx], args.top_k, args.top_n)
                    for idx in window
                }
                for idx, future in futures.items():
                    case_results[idx] = future.result()

            if len(windows) > 1:
                elapsed = perf_counter() - window_start
                remaining = 60.0 - elapsed
                if remaining > 0 and w < len(windows) - 1:
                    print(f"  window done in {elapsed:.1f}s; waiting {remaining:.1f}s "
                          f"to respect the per-minute quota")
                    time.sleep(remaining)

    report_results = [r for r in case_results if r is not None]
    total_wall = perf_counter() - started

    report = {
        "cases": report_results,
        "summary": {
            "case_count": len(report_results),
            "mean_retrieval_niche_precision_at_k": round(mean(item["retrieval_niche_precision_at_k"] for item in report_results), 3),
            "retrieval_niche_hit_rate_at_k": round(mean(item["retrieval_niche_hit_at_k"] for item in report_results), 3),
            "mean_ranked_niche_precision_at_n": round(mean(item["ranked_niche_precision_at_n"] for item in report_results), 3),
            "ranking_fallback_rate": round(mean(item["ranking_fallback"] for item in report_results), 3),
            "total_fallback_slots": sum(item["fallback_count"] for item in report_results),
            "total_filled_slots": sum(item["filled_count"] for item in report_results),
            "mean_strong_fits_per_case": round(mean(item["strong_fit_count"] for item in report_results), 2),
            "mean_retrieval_latency_ms": round(mean(item["retrieval_latency_ms"] for item in report_results), 1),
            "mean_embed_latency_ms": round(mean(item["embed_latency_ms"] for item in report_results), 1),
            "mean_search_latency_ms": round(mean(item["search_latency_ms"] for item in report_results), 1),
            "mean_ranking_latency_ms": round(mean(item["ranking_latency_ms"] for item in report_results), 1),
            "wall_clock_seconds": round(total_wall, 1),
        },
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Full per-case report written to {args.output}")


if __name__ == "__main__":
    main()
