from __future__ import annotations

from statistics import median


def summarize_run(run: dict) -> dict:
    stored_summary = run.get("summary")
    if stored_summary and all(
        key in stored_summary
        for key in (
            "n_results",
            "n_ranked_on_niche",
            "n_strong",
            "n_weak",
            "avg_engagement_pct",
            "median_followers",
        )
    ):
        return stored_summary
    candidates = {item["id"]: item for item in run["result"]["candidates"]}
    ranked = [candidates[item["id"]] for item in run["result"]["ranked"] if item["id"] in candidates]
    brief_niche = run["brief"]["niche"]
    return {
        "n_results": len(ranked),
        "n_ranked_on_niche": sum(item["niche"] == brief_niche for item in ranked),
        "n_strong": sum(item.get("fit") == "strong" for item in run["result"]["ranked"]),
        "n_weak": sum(item.get("fit") == "weak" for item in run["result"]["ranked"]),
        "avg_engagement_pct": (
            sum(float(item["engagement_pct"]) for item in ranked) / len(ranked)
            if ranked
            else 0.0
        ),
        "median_followers": int(round(median(int(item["followers"]) for item in ranked))) if ranked else 0,
    }


def compare_runs(run_a: dict, run_b: dict) -> dict:
    candidates_a = {_creator_key(item): item for item in run_a["result"]["candidates"]}
    candidates_b = {_creator_key(item): item for item in run_b["result"]["candidates"]}
    ranked_a = {item["id"]: item for item in run_a["result"]["ranked"]}
    ranked_b = {item["id"]: item for item in run_b["result"]["ranked"]}
    keys_a = {_ranked_key(item, candidates_a) for item in ranked_a.values()}
    keys_b = {_ranked_key(item, candidates_b) for item in ranked_b.values()}
    shared = []
    for key in sorted(keys_a & keys_b):
        candidate = candidates_a[key]
        shared.append({
            "id": candidate["id"],
            "creator_key": _creator_key(candidate),
            "handle": candidate["handle"],
        })
    return {
        "run_ids": [run_a["id"], run_b["id"]],
        "summary_a": summarize_run(run_a),
        "summary_b": summarize_run(run_b),
        "shared_creators": shared,
    }


def _creator_key(item: dict) -> str:
    key = item.get("creator_key")
    if key and ":" in key:
        return key
    return f"{item.get('platform', '')}:{item['handle']}"


def _ranked_key(entry: dict, candidates: dict[str, dict]) -> str:
    candidate = candidates.get(next((key for key, item in candidates.items() if item["id"] == entry["id"]), ""))
    if candidate is None:
        return str(entry.get("creator_key") or entry["id"])
    return _creator_key(candidate)
