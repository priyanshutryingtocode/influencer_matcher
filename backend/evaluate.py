"""Evaluate retrieval and ranking against a versioned golden brief set.

Usage:
    python evaluate.py
    python evaluate.py --top-k 10 --top-n 5 --output reports/evaluation-report.json
    python evaluate.py --sequential   # old one-at-a-time pacing

A case is relevant when a retrieved creator carries at least one of the case's
`expected_tags`. Replace those tags with human-labelled outcomes when real
creator data is available.

Relevance is defined by intersection, not equality: creators now span several
topics, so a creator tagged across two areas counts for both. That inflates
precision relative to the older single-label definition and makes `pool_size`
larger, so reports written before this change are not comparable to these.

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

from api.repositories.postgres_run_repository import PostgresRunRepository
from src import config, vector_store
from src.embeddings import EmbeddingCache, embed_query, get_cached_query_vector
from src.text_match import overlap_ratio, terms
from src.gemini_client import get_client
from src.match_service import rank_match, retrieve_candidates
from src.models import Brief

BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_CASES = BACKEND_ROOT / "data" / "evaluation_cases.json"
REPORTS_DIR = BACKEND_ROOT / "reports"
DEFAULT_QUERY_CACHE = BACKEND_ROOT / ".embed-cache"


def default_query_cache_path() -> Path:
    """A cache file dedicated to query vectors.

    Deliberately not the document cache that main.py writes: Gemini embeds
    under a different task type for queries than for documents, so one text
    has two legitimate vectors. Sharing a file would hand a document vector to
    retrieval and quietly skew every retrieval score.
    """
    safe_model = config.EMBED_MODEL.replace("/", "_")
    return DEFAULT_QUERY_CACHE / f"{safe_model}-{config.EMBED_DIMENSIONS}d-queries.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate influencer retrieval and ranking quality.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="JSON golden-brief dataset")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="JSON metrics output. Defaults to reports/evaluation-<rows>.json, named "
             "for the dataset it measured, so runs at different corpus sizes cannot "
             "overwrite or be mistaken for each other.",
    )
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
    parser.add_argument(
        "--query-cache", type=Path, default=None,
        help="Reuse and append query vectors here so a repeat run costs no "
             "embedding quota (default: backend/.embed-cache/*-queries.jsonl).",
    )
    parser.add_argument(
        "--no-query-cache", action="store_true",
        help="Re-embed every case even if its vector was computed before.",
    )
    args = parser.parse_args()
    if args.top_k <= 0 or args.top_n <= 0 or args.top_n > args.top_k:
        parser.error("top-k and top-n must be positive, and top-n cannot exceed top-k")
    if args.rate_limit_per_min <= 0:
        parser.error("--rate-limit-per-min must be positive")
    # The runner already paces itself by rate-limit windows, and one window is
    # far below the embedding free-tier cap. Leaving the per-request floor in
    # place would serialize the window and inflate the reported embed latency.
    config.EMBED_REQUEST_INTERVAL_SECONDS = 0.0
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


def tag_precision(items, expected_tags: set[str]) -> float:
    """Share of retrieved creators carrying at least one of the case's tags.

    Intersection-based by design, since creators now span several topics. The
    known cost is that a creator tagged across two topics counts as correct for
    both cases, which inflates precision relative to the old single-label
    definition; `tag_overlap` is reported alongside so the two can be read
    together.
    """
    if not items or not expected_tags:
        return 0.0
    return sum(bool(expected_tags & set(item.tags)) for item in items) / len(items)


def pool_for(
    conn,
    expected_tags: set[str],
    platform: str,
    table: str = vector_store.DEFAULT_TABLE,
) -> int:
    """Creators in the index that share at least one of the case's tags.

    This is the union, not a sum: a creator carrying two of the tags is one
    relevant creator, and `COUNT(DISTINCT id)` is what makes that correct.
    Summing per-tag counts would overstate the pool and make the ceiling
    unreachable in principle. It cannot come from `pool_sizes` because the
    relevant set is a union across tags rather than one grouped cell, so it
    costs one small indexed query per case.
    """
    if not expected_tags:
        return 0
    sql = (
        f"SELECT COUNT(DISTINCT {table}.id) FROM {table}, unnest(tags) AS tag "
        "WHERE tag = ANY(%s)"
    )
    params: list = [sorted(expected_tags)]
    if platform != "Any":
        sql += f" AND {table}.platform = %s"
        params.append(platform)
    return int(conn.execute(sql, params).fetchone()[0])


def ceiling_precision(pool: int, k: int) -> float:
    """Best precision@k this case could reach given what exists in the index."""
    return min(pool, k) / k if k > 0 else 0.0


def recall_of_ceiling(retrieved: int, pool: int, k: int) -> float:
    """Share of the relevant creators that could fit in the top k.

    1.0 means every achievable match was retrieved, which is the only reading
    of precision@k that stays comparable across corpus sizes. An empty pool
    counts as 1.0: there was nothing to find, so nothing was missed.
    """
    reachable = min(pool, k)
    return retrieved / reachable if reachable else 1.0


def _warmup(conn) -> None:
    """Absorb cold-start costs (first embedding API call + first HNSW query) so
    case #1 isn't timed against them. Without this, the very first retrieval
    pays the embedding round-trip plus a cold full-table scan over the Any
    platform, inflating one case's retrieval_latency."""
    query_vec = embed_query("warmup")
    vector_store.search(conn, query_embedding=query_vec, platform="Any", top_k=1)


def _run_case(client, case: dict, top_k: int, top_n: int, query_cache=None) -> dict:
    brief = Brief(
        goal=case["goal"], platform=case.get("platform", "Any"),
        audience=case.get("audience", ""), vibe=case.get("vibe", ""),
    )
    expected_tags = set(case["expected_tags"])
    brief_terms = terms(f"{brief.goal} {brief.audience} {brief.vibe}")

    embed_start = perf_counter()
    query_vec = get_cached_query_vector(brief.query_text(), query_cache)
    embed_ms = round((perf_counter() - embed_start) * 1000, 1)

    search_start = perf_counter()
    candidates = retrieve_candidates(brief, top_k=top_k, query_vec=query_vec)
    search_ms = round((perf_counter() - search_start) * 1000, 1)

    retrieval_ms = round(embed_ms + search_ms, 1)

    ranking_start = perf_counter()
    ranked = rank_match(brief, candidates, top_n=top_n, client=client)
    ranking_ms = round((perf_counter() - ranking_start) * 1000, 1)

    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    ranked_candidates = [candidate_by_id[item["id"]] for item in ranked]
    retrieved_correct = sum(1 for c in candidates if expected_tags & set(c.tags))
    ranked_correct = sum(1 for c in ranked_candidates if expected_tags & set(c.tags))
    # The pool is the only database work this case does, and it happens after
    # ranking. It used to run against a connection checked out at the top of the
    # case, which meant holding a pool slot across the embedding round trip, the
    # vector search and the ranking call. A window fires len(window) cases at
    # once -- 10 by default -- against a pool with max_size=4, so most threads
    # spent the case blocked on the pool while holding nothing. Taking the
    # connection here instead makes the database a short, uncontended step at
    # the end, and lets concurrency follow the rate limit rather than max_size.
    with vector_store.get_connection() as conn:
        pool = pool_for(conn, expected_tags, brief.platform)
    result = {
        "id": case["id"],
        "expected_tags": sorted(expected_tags),
        "platform": brief.platform,
        # True when the brief is deliberately worded away from the case's own
        # tags, so literal word matching cannot pass it. Reported per case, not
        # averaged -- see the hard_cases block below.
        "hard": bool(case.get("hard")),
        "retrieved_count": len(candidates),
        "retrieval_tag_precision_at_k": round(tag_precision(candidates, expected_tags), 3),
        "retrieval_tag_hit_at_k": retrieved_correct > 0,
        # Label-free relevance: how much of the brand's own wording appears in
        # the creators that came back.
        "topic_overlap_at_k": round(
            mean(overlap_ratio(brief_terms, candidate) for candidate in candidates), 3
        ) if candidates else 0.0,
        "ranked_tag_precision_at_n": round(tag_precision(ranked_candidates, expected_tags), 3),
            # The retriever's own ordering, scored at the *same* cutoff the
            # ranked list is scored at. Without this the only retrieval number
            # is precision@k while the only ranking number is precision@n, so
            # the two get compared across different cutoffs and the difference
            # gets read as a ranking win. Both are computed from the candidate
            # list already in hand, so this costs nothing.
            "retrieval_tag_precision_at_n": round(tag_precision(candidates[:top_n], expected_tags), 3),
            # What the reranker added over the retriever: same candidates, same
            # cutoff, only the order differs.
            "ranking_gain_at_n": round(
                tag_precision(ranked_candidates, expected_tags)
                - tag_precision(candidates[:top_n], expected_tags),
                3,
            ),
        "pool_size": pool,
        "ceiling_precision_at_k": round(ceiling_precision(pool, top_k), 3),
        "recall_of_ceiling_at_k": round(recall_of_ceiling(retrieved_correct, pool, top_k), 3),
        "ceiling_precision_at_n": round(ceiling_precision(pool, top_n), 3),
        "recall_of_ceiling_at_n": round(recall_of_ceiling(ranked_correct, pool, top_n), 3),
        "ranking_fallback": any(item.get("source") == "fallback" for item in ranked),
        "fallback_count": sum(1 for item in ranked if item.get("source") == "fallback"),
        "filled_count": sum(1 for item in ranked if item.get("source") == "filled"),
        "strong_fit_count": sum(1 for item in ranked if item.get("fit") == "strong"),
        "retrieval_latency_ms": retrieval_ms,
        "embed_latency_ms": embed_ms,
        "search_latency_ms": search_ms,
        "ranking_latency_ms": ranking_ms,
    }
    return result


def main() -> None:
    args = parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases:
        raise RuntimeError("Evaluation dataset is empty")

    client = get_client()
    case_results: list[dict | None] = [None] * len(cases)

    query_cache = None
    if not args.no_query_cache:
        query_cache = EmbeddingCache(args.query_cache or default_query_cache_path())

    PostgresRunRepository().ensure_schema()
    with vector_store.get_connection() as conn:
        vector_store.init_schema(conn)
        dataset_size = vector_store.count_influencers(conn)
        if not dataset_size:
            raise RuntimeError("No indexed creators. Run main.py --reindex before evaluating.")
        _warmup(conn)

    started = perf_counter()

    if args.sequential:
        spacing = 60.0 / args.rate_limit_per_min
        for idx, case in enumerate(cases):
            if idx > 0:
                time.sleep(spacing)
            case_results[idx] = _run_case(client, case, args.top_k, args.top_n, query_cache)
    else:
        windows = batch_windows(len(cases), args.rate_limit_per_min)
        for w, window in enumerate(windows):
            window_start = perf_counter()
            if len(windows) > 1:
                print(f"Window {w + 1}/{len(windows)}: cases "
                      f"{window[0] + 1}-{window[-1] + 1} firing concurrently...")
            with ThreadPoolExecutor(max_workers=len(window)) as pool:
                # No connection is passed in: each case takes one for its own
                # pool_for query at the end, rather than holding a pool slot for
                # the whole case. See the note in _run_case.
                futures = {}
                for idx in window:
                    futures[idx] = pool.submit(
                        _run_case, client, cases[idx], args.top_k, args.top_n,
                        query_cache,
                    )
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

    summary = {
        "case_count": len(report_results),
        "mean_retrieval_tag_precision_at_k": round(mean(item["retrieval_tag_precision_at_k"] for item in report_results), 3),
        "retrieval_tag_hit_rate_at_k": round(mean(item["retrieval_tag_hit_at_k"] for item in report_results), 3),
        "mean_ranked_tag_precision_at_n": round(mean(item["ranked_tag_precision_at_n"] for item in report_results), 3),
        "mean_retrieval_tag_precision_at_n": round(mean(item["retrieval_tag_precision_at_n"] for item in report_results), 3),
        # The reranker's contribution, and the only pair here that isolates it:
        # identical candidates, identical cutoff, different order.
        "mean_ranking_gain_at_n": round(mean(item["ranking_gain_at_n"] for item in report_results), 3),
        "ranking_fallback_rate": round(mean(item["ranking_fallback"] for item in report_results), 3),
        "total_fallback_slots": sum(item["fallback_count"] for item in report_results),
        "total_filled_slots": sum(item["filled_count"] for item in report_results),
        "mean_strong_fits_per_case": round(mean(item["strong_fit_count"] for item in report_results), 2),
        "mean_retrieval_latency_ms": round(mean(item["retrieval_latency_ms"] for item in report_results), 1),
        "mean_embed_latency_ms": round(mean(item["embed_latency_ms"] for item in report_results), 1),
        "mean_search_latency_ms": round(mean(item["search_latency_ms"] for item in report_results), 1),
        "mean_ranking_latency_ms": round(mean(item["ranking_latency_ms"] for item in report_results), 1),
        "mean_topic_overlap_at_k": round(mean(item["topic_overlap_at_k"] for item in report_results), 3),
        "mean_recall_of_ceiling_at_k": round(mean(item["recall_of_ceiling_at_k"] for item in report_results), 3),
        "mean_recall_of_ceiling_at_n": round(mean(item["recall_of_ceiling_at_n"] for item in report_results), 3),
        "mean_ceiling_precision_at_k": round(mean(item["ceiling_precision_at_k"] for item in report_results), 3),
        "mean_ceiling_precision_at_n": round(mean(item["ceiling_precision_at_n"] for item in report_results), 3),
        "cases_at_ceiling_at_n": sum(1 for item in report_results if item["recall_of_ceiling_at_n"] >= 1.0),
        "wall_clock_seconds": round(total_wall, 1),
    }
    hard = [item for item in report_results if item["hard"]]
    if hard:
        # Reported per case, not as a mean. These briefs avoid their own case's
        # tags, so they are the only evidence that the embedding carries meaning
        # rather than words -- but three briefs cannot support an average, and a
        # mean over them reads as a statistic when it is three anecdotes.
        summary["hard_cases"] = {
            "case_count": len(hard),
            "note": (
                f"{len(hard)} briefs, too few for a mean; read the individual "
                "cases rather than averaging them"
            ),
            "cases": [
                {
                    "id": item["id"],
                    "retrieval_tag_precision_at_k": item["retrieval_tag_precision_at_k"],
                    "topic_overlap_at_k": item["topic_overlap_at_k"],
                }
                for item in hard
            ],
        }

    # The figures worth quoting, in one place. The `summary` above keeps every
    # field for debugging and regression work; most of it is operational detail
    # that means nothing to a reader.
    headline = {
        "dataset_size": dataset_size,
        "case_count": len(report_results),
        "mean_retrieval_tag_precision_at_k": summary["mean_retrieval_tag_precision_at_k"],
        # Quoted as a pair on purpose. Read alone, precision@5 looks like a
        # verdict on the retriever; beside precision@5 for the retriever's own
        # ordering, it shows how much of it the reranker is responsible for.
        "mean_retrieval_tag_precision_at_n": summary["mean_retrieval_tag_precision_at_n"],
        "mean_ranked_tag_precision_at_n": summary["mean_ranked_tag_precision_at_n"],
        "mean_ranking_gain_at_n": summary["mean_ranking_gain_at_n"],
        "mean_recall_of_ceiling_at_k": summary["mean_recall_of_ceiling_at_k"],
        "mean_recall_of_ceiling_at_n": summary["mean_recall_of_ceiling_at_n"],
        "mean_topic_overlap_at_k": summary["mean_topic_overlap_at_k"],
        "mean_strong_fits_per_case": summary["mean_strong_fits_per_case"],
        "ranking_fallback_rate": summary["ranking_fallback_rate"],
    }

    report = {
        "embedding_model": config.EMBED_MODEL,
        "embed_dimensions": config.EMBED_DIMENSIONS,
        "dataset_size": dataset_size,
        "top_k": args.top_k,
        "top_n": args.top_n,
        # Counters come from the disk layer only, so a repeat run reporting
        # hits == case_count is the evidence that it cost no embedding quota.
        "query_cache": {
            "enabled": query_cache is not None,
            "path": str(query_cache.path) if query_cache is not None else None,
            "hits": query_cache.hits if query_cache is not None else 0,
            "misses": query_cache.misses if query_cache is not None else 0,
        },
        "headline": headline,
        "cases": report_results,
        "summary": summary,
    }
    # Named after the dataset, and only after the count is known.
    output = args.output or REPORTS_DIR / f"evaluation-{dataset_size}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["headline"], indent=2))
    print(f"\nFull per-case report written to {output}")


if __name__ == "__main__":
    main()
