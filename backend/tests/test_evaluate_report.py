"""Tests for the evaluation report's ceiling-aware metrics.

Precision@k is bounded by how many relevant creators exist in the filtered
cell, so these helpers are what make a score comparable across corpus sizes.
Pure functions only: no database, no API.
"""

import pytest

from evaluate import ceiling_precision, pool_for, pool_sizes, recall_of_ceiling, tag_precision


class FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.query = None
        self.params = None

    def execute(self, sql, params=None):
        self.query = sql
        self.params = params
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return (self.rows[0][2] if len(self.rows[0]) > 2 else self.rows[0][1],)


def test_pool_sizes_unnests_tags_and_folds_platform_totals():
    conn = FakeConn([
        ("gym", "TikTok", 3),
        ("gym", "Instagram", 4),
        ("skincare", "Instagram", 3),
    ])

    sizes = pool_sizes(conn)

    assert sizes[("gym", "TikTok")] == 3
    assert sizes[("skincare", "Instagram")] == 3
    assert sizes[("gym", "*")] == 7   # 3 + 4 across platforms
    assert sizes[("skincare", "*")] == 3
    assert "unnest(tags)" in conn.query
    assert "GROUP BY tag, platform" in conn.query
    assert "DISTINCT" in conn.query


def test_pool_for_counts_the_union_of_matching_tags():
    """Relevance is an intersection, so the reachable pool is the union; a
    creator carrying two of the tags is one relevant creator, not two."""
    conn = FakeConn([("any", "any", 9)])

    assert pool_for(conn, {"gym", "running"}, "TikTok") == 9
    assert conn.params[0] == ["gym", "running"]


def test_pool_for_applies_the_platform_filter_and_ignores_any():
    filtered = FakeConn([("any", "any", 4)])
    pool_for(filtered, {"gym"}, "TikTok")
    assert "platform = %s" in filtered.query
    assert filtered.params[1] == "TikTok"

    unfiltered = FakeConn([("any", "any", 12)])
    pool_for(unfiltered, {"gym"}, "Any")
    assert "platform = %s" not in unfiltered.query


def test_pool_for_without_tags_is_zero():
    assert pool_for(FakeConn([("any", "any", 5)]), set(), "Any") == 0


class _Creator:
    def __init__(self, tags):
        self.tags = tags


def test_tag_precision_counts_any_shared_tag():
    creators = [_Creator(["gym"]), _Creator(["skincare"]), _Creator(["gym", "fps"])]
    assert tag_precision(creators, {"gym"}) == pytest.approx(2 / 3)


def test_tag_precision_edge_cases():
    assert tag_precision([], {"gym"}) == 0.0
    assert tag_precision([_Creator(["gym"])], set()) == 0.0


@pytest.mark.parametrize("pool,k,expected", [
    (3, 10, 0.3),    # the floor of a small balanced corpus caps the score
    (11, 10, 1.0),   # a deeper cell lifts the cap entirely
    (18, 10, 1.0),   # never above 1.0
    (0, 10, 0.0),
    (3, 5, 0.6),     # the same pool measured at top_n
    (5, 5, 1.0),
])
def test_ceiling_precision(pool, k, expected):
    assert ceiling_precision(pool, k) == pytest.approx(expected)


def test_ceiling_precision_handles_zero_k():
    assert ceiling_precision(3, 0) == 0.0


@pytest.mark.parametrize("retrieved,pool,k,expected", [
    (3, 3, 10, 1.0),   # every creator that could fit was retrieved
    (2, 3, 10, 0.667), # a real miss
    (10, 11, 10, 1.0), # pool deeper than k: k retrieved is a full score
    (5, 5, 5, 1.0),
    (4, 5, 5, 0.8),
    (0, 0, 10, 1.0),   # nothing to find is nothing missed
    (0, 3, 10, 0.0),
])
def test_recall_of_ceiling(retrieved, pool, k, expected):
    assert recall_of_ceiling(retrieved, pool, k) == pytest.approx(expected, abs=0.001)


def test_capped_case_still_scores_full_marks():
    """The point of the metric: a saturated cell must not look like a miss."""
    pool = 3
    k = 10
    retrieved = 3

    assert ceiling_precision(pool, k) == 0.3
    assert recall_of_ceiling(retrieved, pool, k) == 1.0
