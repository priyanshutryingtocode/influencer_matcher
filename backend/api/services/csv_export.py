from __future__ import annotations

import csv
import io

#: Column -> how to read it off (creator, ranked entry, rank).

_CELL = {
    "rank": lambda c, e, r: r,
    "creator_key": lambda c, e, r: c.get("creator_key") or c.get("handle", ""),
    "handle": lambda c, e, r: c.get("handle", ""),
    "name": lambda c, e, r: c.get("name", ""),
    "platform": lambda c, e, r: c.get("platform", ""),
    "city": lambda c, e, r: c.get("city", ""),
    "country": lambda c, e, r: c.get("country", ""),
    "followers": lambda c, e, r: c.get("followers", 0),
    "engagement_pct": lambda c, e, r: c.get("engagement_pct", 0),
    "average_views": lambda c, e, r: c.get("average_views", 0),
    "average_likes": lambda c, e, r: c.get("average_likes", 0),
    "average_comments": lambda c, e, r: c.get("average_comments", 0),
    "verified": lambda c, e, r: c.get("verified", False),
    "posts_per_week": lambda c, e, r: c.get("posts_per_week", 0),
    "account_age_years": lambda c, e, r: c.get("account_age_years", 0),
    "content_style": lambda c, e, r: c.get("content_style", ""),
    "language": lambda c, e, r: c.get("language", ""),
    "audience_age": lambda c, e, r: c.get("audience_age", ""),
    "audience_gender": lambda c, e, r: c.get("audience_gender", ""),
    "audience_country": lambda c, e, r: c.get("audience_country", ""),
    "semantic_similarity": lambda c, e, r: c.get("similarity", ""),
    "reach_ratio": lambda c, e, r: f"{c.get('reach_ratio', 0):.3f}",
    "sponsored_ratio": lambda c, e, r: f"{c.get('sponsored_ratio', 0):.3f}",
    "growth_trend": lambda c, e, r: c.get("growth_trend", ""),
    "audience_top_countries": lambda c, e, r: "|".join(c.get("audience_top_countries", [])),
    "fit": lambda c, e, r: e.get("fit", ""),
    "source": lambda c, e, r: e.get("source", ""),
    "rationale": lambda c, e, r: e.get("rationale", ""),
    "evidence": lambda c, e, r: "; ".join(e.get("evidence", [])),
    "grounding": lambda c, e, r: "; ".join(
        f"{claim.get('field')}={claim.get('quote')}" for claim in e.get("grounding", [])
    ),
    "fallback_reason": lambda c, e, r: e.get("fallback_reason", ""),
    "tags": lambda c, e, r: "|".join(c.get("tags", [])),
    "brand_collaborations": lambda c, e, r: "|".join(c.get("brand_collaborations", [])),
}

CSV_COLUMNS = list(_CELL)


def build_csv(run: dict) -> str:
    candidates = {item["id"]: item for item in run["result"]["candidates"]}
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for rank, entry in enumerate(run["result"]["ranked"], start=1):
        creator = candidates.get(entry.get("id"))
        # A ranked entry whose snapshot is missing is skipped rather than
        # raising.
        if creator is None:
            continue
        writer.writerow([
            _safe_cell(read(creator, entry, rank)) for read in _CELL.values()
        ])
    return output.getvalue()


def _safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "\t", "\r")):
        return "'" + value
    return value
