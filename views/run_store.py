"""Local run persistence: one JSON file per shortlist in .runs/ (gitignored).

Deliberately free of any Streamlit imports so the store and CSV export are
plain, unit-testable code. The directory lives under the project root next
to app.py; a Postgres-backed store can replace this later behind the same
four functions (save/list/load/delete).
"""

import csv
import io
import json
import logging
import re
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

from src.models import Brief, Influencer

logger = logging.getLogger(__name__)

RUNS_DIR = Path(".runs")

# run_ids double as filenames -- restrict to a safe charset so a crafted
# id can never escape .runs/ via traversal.
_RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_INFLUENCER_FIELDS = {f.name for f in fields(Influencer)}

# Fields persisted per candidate. The embedding array is intentionally
# excluded: it's large, derivable from corpus text, and useless without
# the model that made it.
_STORED_FIELDS = _INFLUENCER_FIELDS - {"embedding"}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "na"


def _inf_to_dict(inf: Influencer) -> dict:
    out = {}
    for name in sorted(_STORED_FIELDS):
        value = getattr(inf, name)
        if name == "similarity":
            value = round(value, 6) if value is not None else None
        out[name] = value
    return out


def _inf_from_dict(data: dict) -> Influencer:
    known = {k: v for k, v in data.items() if k in _INFLUENCER_FIELDS}
    return Influencer(**known)


def save_run(brief: Brief, ranked: list[dict], candidates: list[Influencer],
             params: dict | None = None) -> str:
    """Persist one run; returns its run_id (= filename stem)."""
    now = datetime.now(timezone.utc)
    run_id = f"{now:%Y%m%d-%H%M%S}-{slugify(brief.niche)}-{slugify(brief.platform)}"
    payload = {
        "version": 1,
        "run_id": run_id,
        "saved_at": now.isoformat(timespec="seconds"),
        "params": params or {},
        "brief": {
            "niche": brief.niche, "platform": brief.platform,
            "audience": brief.audience, "vibe": brief.vibe,
        },
        "candidates": [_inf_to_dict(c) for c in candidates],
        "ranked": ranked,
    }
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNS_DIR / f"{run_id}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)  # atomic-ish on both POSIX and Windows
    return run_id


def list_runs() -> list[dict]:
    """Metadata for all stored runs, newest first. Corrupt files are
    skipped (with a log line) rather than breaking the History page."""
    if not RUNS_DIR.exists():
        return []
    runs = []
    for path in RUNS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            brief = data["brief"]
            ranked = data["ranked"]
            runs.append({
                "run_id": data["run_id"],
                "saved_at": data["saved_at"],
                "niche": brief["niche"],
                "platform": brief["platform"],
                "audience": brief.get("audience", ""),
                "vibe": brief.get("vibe", ""),
                "n_results": len(ranked),
                "n_strong": sum(1 for e in ranked if e.get("fit") == "strong"),
            })
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Skipping unreadable run file: %s", path.name)
    runs.sort(key=lambda r: r["saved_at"], reverse=True)
    return runs


def load_run(run_id: str) -> dict | None:
    """Load a full run by id. Returns None if missing, malformed id, or
    corrupt content -- callers render a friendly error either way."""
    if not _RUN_ID_RE.fullmatch(run_id or ""):
        return None
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        candidates = [_inf_from_dict(c) for c in raw["candidates"]]
        brief = Brief(**raw["brief"])
        return {
            "run_id": raw["run_id"],
            "saved_at": raw["saved_at"],
            "params": raw.get("params", {}),
            "brief": brief,
            "candidates": candidates,
            "ranked": raw["ranked"],
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Run file is corrupt: %s", path.name)
        return None


def delete_run(run_id: str) -> bool:
    if not _RUN_ID_RE.fullmatch(run_id or ""):
        return False
    path = RUNS_DIR / f"{run_id}.json"
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


CSV_COLUMNS = [
    "rank", "handle", "name", "niche", "secondary_niches", "platform",
    "city", "country", "followers", "engagement_pct", "average_views",
    "average_likes", "average_comments", "verified", "posts_per_week",
    "account_age_years", "content_style", "language",
    "audience_age", "audience_gender", "audience_country",
    "semantic_similarity", "fit", "source", "rationale",
    "tags", "brand_collaborations",
]


def build_csv(run: dict) -> str:
    """Render a run as CSV for export. List-valued fields are pipe-joined."""
    candidates_by_id = {c.id: c for c in run["candidates"]}
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for i, entry in enumerate(run["ranked"], start=1):
        inf = candidates_by_id[entry["id"]]
        writer.writerow([
            i, inf.handle, inf.name, inf.niche,
            "|".join(inf.secondary_niches), inf.platform,
            inf.city, inf.country, inf.followers, inf.engagement,
            inf.average_views, inf.average_likes, inf.average_comments,
            inf.verified, inf.posts_per_week, inf.account_age_years,
            inf.content_style, inf.language,
            inf.audience_age, inf.audience_gender, inf.audience_country,
            f"{inf.similarity:.4f}" if inf.similarity is not None else "",
            entry.get("fit", ""), entry.get("source", ""),
            entry.get("rationale", ""),
            "|".join(inf.tags), "|".join(inf.brand_collaborations),
        ])
    return buf.getvalue()
