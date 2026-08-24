"""Reusable result-card rendering, shared by Search, History, and Compare."""

import streamlit as st

from src.formatting import format_followers, match_evidence
from src.models import Brief, Influencer

FIT_STYLE = {
    "strong": ("\U0001F7E2", "Strong fit"),
    "partial": ("\U0001F7E1", "Partial fit"),
    "weak": ("\U0001F534", "Weak fit"),
    "unknown": ("\u26AA", "Fit unknown"),
}


def follower_tier(followers: int) -> str:
    if followers <= 10_000:
        return "nano"
    if followers <= 100_000:
        return "micro"
    if followers <= 1_000_000:
        return "macro"
    return "mega"


def render_run_warnings(ranked: list[dict], candidates: list[Influencer],
                        niche: str) -> None:
    """Coverage + degradation banners extracted verbatim from the old app."""
    matches = sum(1 for c in candidates if c.niche == niche)
    total = len(candidates)
    if total and matches < total:
        st.warning(
            f"Only {matches}/{total} retrieved candidates are actually tagged **{niche}**. "
            f"The rest passed your platform filter but ranked in on vibe/audience similarity rather than "
            f"niche — check the fit badges on each card, or try a different platform."
        )

    fallback_entries = [e for e in ranked if e.get("source") == "fallback"]
    filled_entries = [e for e in ranked if e.get("source") == "filled"]
    if fallback_entries:
        # The detailed reason (exception type/message) is already logged
        # server-side by ranking.py's logger.warning -- not shown here,
        # since raw exception text can leak internal request/network detail
        # and isn't actionable for the person using the app.
        st.error("Gemini ranking is temporarily unavailable, so this shortlist is retrieval order, not LLM-reasoned.")
    elif filled_entries:
        st.info(
            f"The model only ranked {len(ranked) - len(filled_entries)} of {len(ranked)} requested slots; "
            f"the rest were filled from retrieval order (marked \u26AA below)."
        )


def render_result_card(inf: Influencer, entry: dict, brief: Brief,
                       rank: int | None = None, highlight: bool = False) -> None:
    """One creator card. rank=None renders read-only (history/compare);
    highlight=True marks a creator found in both compared runs."""
    fit = entry.get("fit", "unknown")
    fit_emoji, fit_label = FIT_STYLE.get(fit, FIT_STYLE["unknown"])
    tier = follower_tier(inf.followers)

    title = f"{inf.handle}" if rank is None else f"#{rank} · {inf.handle}"
    flags = f"  {fit_emoji} {fit_label}"
    if highlight:
        flags += "  \U0001F501 in both"
    with st.container(border=True):
        st.markdown(f"**{title}**{flags}")
        st.caption(f"{inf.niche} · {inf.platform} · {inf.city} · {tier}")

        metrics = [format_followers(inf.followers), f"{inf.engagement}%"]
        labels = ["Followers", "Engagement"]
        if inf.similarity is not None:
            metrics.append(f"{inf.similarity:.1%}")
            labels.append("Semantic match")
        mcols = st.columns(len(labels))
        for col, label, value in zip(mcols, labels, metrics):
            col.metric(label, value)

        audience_line = (
            f"{inf.content_style} | {inf.language} | audience: {inf.audience_age}, "
            f"{inf.audience_gender}, {inf.audience_country}"
        )
        st.caption(audience_line)
        if inf.tags:
            st.write(" ".join(f"`{t}`" for t in inf.tags))
        if inf.brand_collaborations:
            st.caption("Past collaborations: " + ", ".join(inf.brand_collaborations))

        rationale = entry.get("rationale", "")
        if rationale:
            if fit == "weak":
                st.warning(rationale)
            else:
                st.info(rationale)

        evidence = match_evidence(brief, inf)
        with st.expander("Why this match?"):
            st.markdown("\n".join(f"- {line}" for line in evidence))
