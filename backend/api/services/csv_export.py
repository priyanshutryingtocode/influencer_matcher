from __future__ import annotations

import csv
import io

CSV_COLUMNS = [
    "rank",
    "creator_key",
    "handle",
    "name",
    "niche",
    "secondary_niches",
    "platform",
    "city",
    "country",
    "followers",
    "engagement_pct",
    "average_views",
    "average_likes",
    "average_comments",
    "verified",
    "posts_per_week",
    "account_age_years",
    "content_style",
    "language",
    "audience_age",
    "audience_gender",
    "audience_country",
    "semantic_similarity",
    "fit",
    "source",
    "rationale",
    "evidence",
    "tags",
    "brand_collaborations",
]


def build_csv(run: dict) -> str:
    candidates = {item["id"]: item for item in run["result"]["candidates"]}
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for rank, entry in enumerate(run["result"]["ranked"], start=1):
        creator = candidates[entry["id"]]
        writer.writerow([
            _safe_cell(rank),
            _safe_cell(creator.get("creator_key", creator["handle"])),
            _safe_cell(creator["handle"]),
            _safe_cell(creator.get("name", "")),
            _safe_cell(creator["niche"]),
            _safe_cell("|".join(creator.get("secondary_niches", []))),
            _safe_cell(creator["platform"]),
            _safe_cell(creator.get("city", "")),
            _safe_cell(creator.get("country", "")),
            _safe_cell(creator["followers"]),
            _safe_cell(creator.get("engagement_pct", 0)),
            _safe_cell(creator.get("average_views", 0)),
            _safe_cell(creator.get("average_likes", 0)),
            _safe_cell(creator.get("average_comments", 0)),
            _safe_cell(creator.get("verified", False)),
            _safe_cell(creator.get("posts_per_week", 0)),
            _safe_cell(creator.get("account_age_years", 0)),
            _safe_cell(creator.get("content_style", "")),
            _safe_cell(creator.get("language", "")),
            _safe_cell(creator.get("audience_age", "")),
            _safe_cell(creator.get("audience_gender", "")),
            _safe_cell(creator.get("audience_country", "")),
            _safe_cell(creator.get("similarity", "")),
            _safe_cell(entry.get("fit", "")),
            _safe_cell(entry.get("source", "")),
            _safe_cell(entry.get("rationale", "")),
            _safe_cell("; ".join(entry.get("evidence", []))),
            _safe_cell("|".join(creator.get("tags", []))),
            _safe_cell("|".join(creator.get("brand_collaborations", []))),
        ])
    return output.getvalue()


def _safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "\t", "\r")):
        return "'" + value
    return value
