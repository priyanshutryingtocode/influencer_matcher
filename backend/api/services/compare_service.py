from __future__ import annotations

from api.serialization import SUMMARY_KEYS, build_summary, candidate_key


def summarize_run(run: dict) -> dict:
    """Reuse the stored summary when it is complete, else recompute it.

    The arithmetic lives in `serialization.build_summary`; this only decides
    whether it has to run. It used to carry its own copy, reading the persisted
    dicts while the original read `Influencer` objects -- two implementations
    of one number, free to disagree.
    """
    stored = run.get("summary")
    if stored and all(key in stored for key in SUMMARY_KEYS):
        return stored
    result = run["result"]
    return build_summary(result["candidates"], result["ranked"])


def compare_runs(run_a: dict, run_b: dict) -> dict:
    candidates_a = {candidate_key(item): item for item in run_a["result"]["candidates"]}
    candidates_b = {candidate_key(item): item for item in run_b["result"]["candidates"]}
    ranked_a = {item["id"]: item for item in run_a["result"]["ranked"]}
    ranked_b = {item["id"]: item for item in run_b["result"]["ranked"]}
    keys_a = {_ranked_key(item, candidates_a) for item in ranked_a.values()}
    keys_b = {_ranked_key(item, candidates_b) for item in ranked_b.values()}
    shared = []
    for key in sorted(keys_a & keys_b):
        candidate = candidates_a[key]
        shared.append({
            "id": candidate["id"],
            "creator_key": candidate_key(candidate),
            "handle": candidate["handle"],
        })
    return {
        "run_ids": [run_a["id"], run_b["id"]],
        "summary_a": summarize_run(run_a),
        "summary_b": summarize_run(run_b),
        "shared_creators": shared,
    }


def _ranked_key(entry: dict, candidates: dict[str, dict]) -> str:
    candidate = candidates.get(next((key for key, item in candidates.items() if item["id"] == entry["id"]), ""))
    if candidate is None:
        return str(entry.get("creator_key") or entry["id"])
    return candidate_key(candidate)
