"""Display helpers, kept separate from pipeline logic so they're easy to
swap out (e.g. if you later render results in a web UI instead of stdout)."""

from .models import Brief, Influencer


def format_followers(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def niche_coverage(candidates: list[Influencer], niche: str) -> tuple[int, int]:
    """How many of the retrieved candidates actually match the requested
    niche, out of how many were retrieved. A low ratio (especially 0) means
    the platform filter (or retrieval itself) left little or nothing
    on-niche to choose from -- worth surfacing, since the ranker will still
    confidently pick *something* from what's available even if none of it
    is a good fit."""
    matches = sum(1 for c in candidates if c.niche == niche)
    return matches, len(candidates)


def print_brief(brief: Brief) -> None:
    print("\nBrief:")
    print(f"  Niche: {brief.niche} | Platform: {brief.platform}")
    print(f"  Audience: {brief.audience}")
    print(f"  Vibe: {brief.vibe}")


def print_results(ranked: list[dict], candidates_by_id: dict[int, Influencer], niche: str) -> None:
    matches, total = niche_coverage(list(candidates_by_id.values()), niche)
    if total and matches < total:
        print(f"\nHeads up: only {matches}/{total} retrieved candidates are actually tagged '{niche}'.")
        print("The rest passed your platform filter but didn't match the niche as closely.")

    fallback_entries = [e for e in ranked if e.get("source") == "fallback"]
    filled_entries = [e for e in ranked if e.get("source") == "filled"]
    if fallback_entries:
        reason = fallback_entries[0].get("fallback_reason", "unknown error")
        print(f"\nWARNING: Gemini ranking failed ({reason}); this list is retrieval order, not LLM-reasoned.")
    elif filled_entries:
        print(
            f"\nNote: the model only ranked {len(ranked) - len(filled_entries)} of {len(ranked)} requested "
            f"slots; the rest were filled from retrieval order (marked [filled] below)."
        )

    print(f"\nTop {len(ranked)} matches (fit is AI-assessed, cross-checked against niche match):\n")
    for i, entry in enumerate(ranked, start=1):
        inf = candidates_by_id[entry["id"]]
        fit_tag = f"[{entry.get('fit', 'unknown')} fit] " if entry.get("fit") else ""
        print(f"{i}. {fit_tag}{inf.handle}  ({inf.niche}, {inf.platform})")
        print(f"   {format_followers(inf.followers)} followers · {inf.engagement}% engagement · ${inf.rate}/post")
        print(f"   {entry['rationale']}\n")