"""Display helpers, kept separate from pipeline logic so they're easy to
swap out (e.g. if you later render results in a web UI instead of stdout)."""

from .models import Brief, Influencer


def format_followers(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def print_brief(brief: Brief) -> None:
    print("\nBrief:")
    print(f"  Niche: {brief.niche} | Platform: {brief.platform} | Budget: ${brief.budget_max}")
    print(f"  Audience: {brief.audience}")
    print(f"  Vibe: {brief.vibe}")


def print_results(ranked: list[dict], candidates_by_id: dict[int, Influencer]) -> None:
    print(f"\nTop {len(ranked)} matches:\n")
    for i, entry in enumerate(ranked, start=1):
        inf = candidates_by_id[entry["id"]]
        print(f"{i}. {inf.handle}  ({inf.niche}, {inf.platform})")
        print(f"   {format_followers(inf.followers)} followers · {inf.engagement}% engagement · ${inf.rate}/post")
        print(f"   {entry['rationale']}\n")
