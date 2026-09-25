from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from uuid import UUID

from src.formatting import match_evidence, niche_coverage
from src.models import Brief, Influencer

from .schemas.models import (
    BriefPayload,
    CreatorSnapshot,
    MatchParams,
    RankedCreator,
    RunDetail,
    RunListItem,
    RunSummary,
    Warning,
)


def brief_to_payload(brief: Brief) -> dict:
    return BriefPayload(
        niche=brief.niche,
        platform=brief.platform,
        audience=brief.audience,
        vibe=brief.vibe,
    ).model_dump(mode="json")


def creator_to_snapshot(influencer: Influencer) -> dict:
    return CreatorSnapshot(
        id=influencer.id,
        creator_key=_creator_key(influencer),
        handle=influencer.handle,
        name=influencer.name,
        niche=influencer.niche,
        secondary_niches=influencer.secondary_niches,
        platform=influencer.platform,
        city=influencer.city,
        country=influencer.country,
        language=influencer.language,
        followers=influencer.followers,
        engagement_pct=influencer.engagement,
        average_views=influencer.average_views,
        average_likes=influencer.average_likes,
        average_comments=influencer.average_comments,
        verified=influencer.verified,
        posts_per_week=influencer.posts_per_week,
        account_age_years=influencer.account_age_years,
        content_style=influencer.content_style,
        audience_age=influencer.audience_age,
        audience_gender=influencer.audience_gender,
        audience_country=influencer.audience_country,
        brand_collaborations=influencer.brand_collaborations,
        tags=influencer.tags,
        bio=influencer.bio,
        similarity=influencer.similarity,
    ).model_dump(mode="json")


def ranked_to_snapshot(
    entry: dict,
    influencer: Influencer,
    brief: Brief,
    rank: int,
) -> dict:
    return RankedCreator(
        id=influencer.id,
        creator_key=_creator_key(influencer),
        rank=rank,
        fit=entry.get("fit", "unknown"),
        source=entry.get("source", "filled"),
        rationale=entry.get("rationale", ""),
        evidence=match_evidence(brief, influencer),
    ).model_dump(mode="json")


def build_warnings(
    brief: Brief,
    candidates: list[Influencer],
    ranked: list[dict],
) -> list[dict]:
    warnings: list[Warning] = []
    matches, total = niche_coverage(candidates, brief.niche)
    if total and matches < total:
        warnings.append(
            Warning(
                code="LOW_NICHE_COVERAGE",
                severity="warning",
                message=f"Only {matches}/{total} retrieved creators are tagged {brief.niche}.",
                details={"matches": matches, "retrieved": total},
            )
        )
    if any(item.get("source") == "fallback" for item in ranked):
        warnings.append(
            Warning(
                code="RANKING_FALLBACK",
                severity="error",
                message="Gemini ranking was unavailable; showing retrieval order.",
            )
        )
    elif any(item.get("source") == "filled" for item in ranked):
        filled = sum(item.get("source") == "filled" for item in ranked)
        warnings.append(
            Warning(
                code="RANKING_PARTIALLY_FILLED",
                severity="info",
                message=f"The model ranked {len(ranked) - filled} of {len(ranked)} requested slots.",
                details={"filled": filled, "requested": len(ranked)},
            )
        )
    return [warning.model_dump(mode="json") for warning in warnings]


def build_summary(candidates: list[Influencer], ranked: list[dict], brief: Brief) -> dict:
    by_id = {candidate.id: candidate for candidate in candidates}
    ranked_candidates = [by_id[item["id"]] for item in ranked if item.get("id") in by_id]
    return RunSummary(
        n_results=len(ranked_candidates),
        n_ranked_on_niche=sum(item.niche == brief.niche for item in ranked_candidates),
        n_strong=sum(item.get("fit") == "strong" for item in ranked),
        n_weak=sum(item.get("fit") == "weak" for item in ranked),
        avg_engagement_pct=(
            sum(item.engagement for item in ranked_candidates) / len(ranked_candidates)
            if ranked_candidates
            else 0.0
        ),
        median_followers=int(round(median(item.followers for item in ranked_candidates))) if ranked_candidates else 0,
    ).model_dump(mode="json")


def build_run_record(result: dict, run_id: UUID, indexed_count: int | None = None) -> dict:
    brief: Brief = result["brief"]
    params: dict[str, int] = result["params"]
    candidates: list[Influencer] = result["candidates"]
    ranked: list[dict] = result["ranked"]
    by_id = {candidate.id: candidate for candidate in candidates}
    ranked_snapshots = [
        ranked_to_snapshot(entry, by_id[entry["id"]], brief, rank)
        for rank, entry in enumerate(ranked, start=1)
        if entry.get("id") in by_id
    ]
    candidate_snapshots = [creator_to_snapshot(candidate) for candidate in candidates]
    return {
        "id": run_id,
        "brief": brief_to_payload(brief),
        "params": MatchParams(**params).model_dump(mode="json"),
        "pipeline": {
            "embedding_model": _config_value("LOCAL_EMBED_MODEL"),
            "embed_dimensions": _config_value("EMBED_DIMENSIONS"),
            "gemini_model": _config_value("GEN_MODEL"),
            "indexed_creator_count": indexed_count,
        },
        "result": {
            "candidates": candidate_snapshots,
            "ranked": ranked_snapshots,
        },
        "warnings": build_warnings(brief, candidates, ranked),
        "summary": build_summary(candidates, ranked, brief),
    }


def run_detail(record: dict) -> RunDetail:
    result = _normalize_result(record["result"])
    return RunDetail.model_validate(
        {
            "run_id": record["id"],
            "created_at": record["created_at"],
            "brief": record["brief"],
            "params": record["params"],
            "pipeline": record["pipeline"],
            "warnings": record["warnings"],
            "summary": record["summary"],
            "candidates": result["candidates"],
            "ranked": result["ranked"],
        }
    )


def _normalize_result(result: dict) -> dict:
    candidates = []
    by_id = {}
    for raw in result.get("candidates", []):
        candidate = dict(raw)
        candidate["creator_key"] = _candidate_key(candidate)
        candidates.append(candidate)
        by_id[candidate["id"]] = candidate
    ranked = []
    for raw in result.get("ranked", []):
        entry = dict(raw)
        candidate = by_id.get(entry.get("id"))
        if candidate is not None:
            entry["creator_key"] = candidate["creator_key"]
        ranked.append(entry)
    return {"candidates": candidates, "ranked": ranked}


def _candidate_key(candidate: dict) -> str:
    key = candidate.get("creator_key")
    if key and ":" in key:
        return key
    return f"{candidate.get('platform', '')}:{candidate.get('handle', '')}"


def run_list_item(record: dict) -> RunListItem:
    summary = record.get("summary") or {}
    return RunListItem(
        run_id=record["id"],
        created_at=record["created_at"],
        brief=record["brief"],
        n_results=int(summary.get("n_results", 0)),
        n_strong=int(summary.get("n_strong", 0)),
        has_warnings=bool(record.get("warnings")),
    )


def _creator_key(influencer: Influencer) -> str:
    return f"{influencer.platform}:{influencer.handle}"


def _config_value(name: str):
    from src import config

    return getattr(config, name)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
