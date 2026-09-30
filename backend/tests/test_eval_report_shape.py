"""Tests for the report's headline block and the hard-case breakdown.

`summary` carries every field for debugging. `headline` carries only what a
reader should quote, and the two must not drift apart.
"""

import json
from pathlib import Path

import pytest

from evaluate import DEFAULT_CASES

BACKEND = Path(__file__).resolve().parents[1]

HEADLINE_KEYS = {
    "dataset_size",
    "case_count",
    "mean_retrieval_tag_precision_at_k",
    "mean_recall_of_ceiling_at_k",
    "mean_recall_of_ceiling_at_n",
    "mean_topic_overlap_at_k",
    "mean_strong_fits_per_case",
    "ranking_fallback_rate",
}


@pytest.fixture(scope="module")
def written_report(tmp_path_factory):
    """Run the evaluator once against the live schema with the model stubbed."""
    import evaluate as ev
    from src.models import Brief

    out = tmp_path_factory.mktemp("reports") / "report.json"
    ev._run_case = _stub_case
    ev.get_client = lambda: object()
    ev.embed_query = lambda text: [0.0] * 768
    ev.PostgresRunRepository = _StubRepository
    ev.vector_store = _StubVectorStore
    # --rate-limit-per-min is raised so the sequential pacing does not spend a
    # minute of the suite sleeping; it is a report-shape test, not a latency
    # measurement, and the values are stubbed anyway.
    monkey_argv = [
        "evaluate.py", "--sequential", "--rate-limit-per-min", "1000",
        "--output", str(out),
        # The cache is disabled so this fixture can never append to the real
        # .embed-cache directory the way a real evaluation run would.
        "--no-query-cache",
    ]
    import sys
    original = sys.argv
    sys.argv = monkey_argv
    try:
        ev.main()
    finally:
        sys.argv = original
    return json.loads(out.read_text(encoding="utf-8"))


def _stub_case(client, conn, case, top_k, top_n, query_cache=None):
    return {
        "id": case["id"],
        "expected_tags": sorted(case["expected_tags"]),
        "platform": case.get("platform", "Any"),
        "hard": bool(case.get("hard")),
        "retrieved_count": top_k,
        "retrieval_tag_precision_at_k": 0.5,
        "retrieval_tag_hit_at_k": True,
        "topic_overlap_at_k": 0.1,
        "ranked_tag_precision_at_n": 0.4,
        "pool_size": 12,
        "ceiling_precision_at_k": 1.0,
        "recall_of_ceiling_at_k": 0.5,
        "ceiling_precision_at_n": 1.0,
        "recall_of_ceiling_at_n": 0.5,
        "ranking_fallback": False,
        "fallback_count": 0,
        "filled_count": 0,
        "strong_fit_count": 3,
        "retrieval_latency_ms": 1.0,
        "embed_latency_ms": 1.0,
        "search_latency_ms": 1.0,
        "ranking_latency_ms": 1.0,
    }


class _StubRepository:
    def ensure_schema(self):
        return None


class _StubVectorStore:
    DEFAULT_TABLE = "influencers"

    @staticmethod
    def init_schema(conn):
        return None

    @staticmethod
    def count_influencers(conn):
        return 500

    @staticmethod
    def search(conn, query_embedding=None, platform="Any", top_k=1):
        return []

    @staticmethod
    def get_connection():
        class _Ctx:
            def __enter__(self_inner):
                return object()

            def __exit__(self_inner, *a):
                return False

        return _Ctx()


# ------------------------------------------------------------- headline

def test_headline_has_exactly_the_intended_keys(written_report):
    assert set(written_report["headline"]) == HEADLINE_KEYS


def test_headline_values_come_from_the_summary(written_report):
    """The trimmed view must not drift from the full one."""
    h, s = written_report["headline"], written_report["summary"]
    for key in HEADLINE_KEYS - {"dataset_size", "case_count"}:
        assert h[key] == s[key], f"{key} disagrees between headline and summary"
    assert h["dataset_size"] == written_report["dataset_size"] == s["case_count"] * 0 + written_report["dataset_size"]
    assert h["case_count"] == s["case_count"] == len(written_report["cases"])


def test_headline_omits_operational_noise(written_report):
    """Latency and slot counters belong in the JSON, not in a quoted figure."""
    for noisy in ("mean_ranking_latency_ms", "total_filled_slots",
                  "mean_ceiling_precision_at_k", "retrieval_tag_hit_rate_at_k"):
        assert noisy not in written_report["headline"]
        assert noisy in written_report["summary"]


def test_summary_keeps_every_field(written_report):
    assert len(written_report["summary"]) > len(HEADLINE_KEYS)


# ------------------------------------------------------------ hard cases

def test_hard_cases_are_listed_per_case_with_no_mean(written_report):
    """A mean over three briefs is three anecdotes in a trenchcoat."""
    hard = written_report["summary"]["hard_cases"]
    assert set(hard) == {"case_count", "note", "cases"}
    assert hard["case_count"] == len(hard["cases"]) == 3
    assert not any(key.startswith("mean_") for key in hard)
    for row in hard["cases"]:
        assert set(row) == {"id", "retrieval_tag_precision_at_k", "topic_overlap_at_k"}
    assert "too few for a mean" in hard["note"]


def test_hard_case_ids_match_the_flagged_briefs(written_report):
    hard = written_report["summary"]["hard_cases"]
    flagged = {c["id"] for c in written_report["cases"] if c["hard"]}
    assert {row["id"] for row in hard["cases"]} == flagged
    assert len(flagged) < len(written_report["cases"]), "a subset must actually be a subset"


# --------------------------------------------------------- case set

def test_golden_set_is_ten_balanced_cases():
    """Ten cases, one per vertical, spread over as many platforms as possible.

    The set was 15 with Instagram a third of it and Fitness a fifth, so the mean
    was weighted toward two topics. Ten cases at the per-minute ranking limit
    also fits one window, which is what makes the run take about a minute.
    """
    cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    assert len(cases) == 10

    verticals = {c["expected_tags"][0] for c in cases}
    assert len(verticals) == len(cases), "each case should cover a distinct topic"

    assert len({c["platform"] for c in cases}) >= 7
    assert sum(1 for c in cases if c["hard"]) == 3


def test_every_case_has_the_fields_the_runner_reads():
    cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    for case in cases:
        assert case["id"] and case["goal"]
        assert case["expected_tags"], f"{case['id']} has no expected_tags"
        assert isinstance(case["hard"], bool)
        assert "audience" in case and "vibe" in case
