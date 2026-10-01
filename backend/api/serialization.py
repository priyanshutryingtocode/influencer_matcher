from __future__ import annotations

from statistics import median
from uuid import UUID

from src import config
from src.formatting import match_evidence
from src.models import Brief, Influencer
from src.ranking import QUOTA_REASON_TAG

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
        goal=brief.goal,
        platform=brief.platform,
        audience=brief.audience,
        vibe=brief.vibe,
    ).model_dump(mode="json")


def creator_to_snapshot(influencer: Influencer) -> dict:
    return CreatorSnapshot(
        id=influencer.id,
        creator_key=creator_key(influencer),
        handle=influencer.handle,
        name=influencer.name,
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
        reach_ratio=influencer.reach_ratio,
        sponsored_ratio=influencer.sponsored_ratio,
        growth_trend=influencer.growth_trend,
        audience_top_countries=influencer.audience_top_countries,
    ).model_dump(mode="json")


def ranked_to_snapshot(
    entry: dict,
    influencer: Influencer,
    brief: Brief,
    rank: int,
) -> dict:
    return RankedCreator(
        id=influencer.id,
        creator_key=creator_key(influencer),
        rank=rank,
        fit=entry.get("fit", "unknown"),
        source=entry.get("source", "filled"),
        rationale=entry.get("rationale", ""),
        evidence=match_evidence(brief, influencer),
        grounding=entry.get("grounding", []),
        fallback_reason=entry.get("fallback_reason", ""),
    ).model_dump(mode="json")


def build_warnings(ranked: list[dict]) -> list[dict]:
    warnings: list[Warning] = []
    fallback = [item for item in ranked if item.get("source") == "fallback"]
    if fallback:
        reason = next((item.get("fallback_reason", "") for item in fallback if item.get("fallback_reason")), "")
        is_quota = reason.startswith(QUOTA_REASON_TAG)
        if is_quota:
            # "Unavailable" would read as an outage, and the sensible response
            # to an outage is to retry immediately -- which cannot help here.
            # Say what actually happened and when it changes.
            message = (
                "Today's free ranking quota is spent, so these are in retrieval order "
                "rather than ranked. It resets at midnight Pacific."
            )
        else:
            message = "Gemini ranking was unavailable; showing retrieval order."
        warnings.append(
            Warning(
                code="RANKING_FALLBACK",
                severity="error",
                message=message,
                details={"reason": reason} if reason else {},
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


#: The six keys a stored summary must carry to be reused instead of recomputed.
SUMMARY_KEYS = (
    "n_results",
    "avg_match_pct",
    "n_strong",
    "n_weak",
    "avg_engagement_pct",
    "median_followers",
)


def build_summary(candidates: list[dict], ranked: list[dict]) -> dict:
    """The one place run statistics are computed.

    Takes the persisted snapshot shape rather than `Influencer` objects, because
    that is what a stored run actually holds -- `compare_service` has to
    recompute from a DB record and was reimplementing this against dicts.

    Every count is taken over the joined set. The previous version counted
    `n_strong`/`n_weak` over the whole ranked list while `n_results` counted
    only joined candidates, so a run with a dangling ranked entry could report
    "4/5 strong fits".
    """
    by_id = {candidate["id"]: candidate for candidate in candidates}
    joined = [(entry, by_id[entry["id"]]) for entry in ranked if entry.get("id") in by_id]
    similarities = [
        float(creator["similarity"])
        for _, creator in joined
        if creator.get("similarity") is not None
    ]
    return RunSummary(
        n_results=len(joined),
        avg_match_pct=round(100 * (sum(similarities) / len(similarities)), 1) if similarities else 0.0,
        n_strong=sum(entry.get("fit") == "strong" for entry, _ in joined),
        n_weak=sum(entry.get("fit") == "weak" for entry, _ in joined),
        avg_engagement_pct=(
            sum(float(creator.get("engagement_pct") or 0.0) for _, creator in joined) / len(joined)
            if joined
            else 0.0
        ),
        median_followers=(
            int(round(median(int(creator.get("followers") or 0) for _, creator in joined)))
            if joined
            else 0
        ),
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
            "embedding_model": config.EMBED_MODEL,
            "embed_dimensions": config.EMBED_DIMENSIONS,
            "gemini_model": config.GEN_MODEL,
            "indexed_creator_count": indexed_count,
        },
        "result": {
            "candidates": candidate_snapshots,
            "ranked": ranked_snapshots,
        },
        "warnings": build_warnings(ranked),
        "summary": build_summary(candidate_snapshots, ranked),
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
        candidate["creator_key"] = candidate_key(candidate)
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


def candidate_key(candidate: dict) -> str:
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


def creator_key(influencer: Influencer) -> str:
    return f"{influencer.platform}:{influencer.handle}"
