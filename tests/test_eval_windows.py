"""Tests for evaluate.batch_windows scheduling math."""

from evaluate import batch_windows


def test_exact_single_window():
    assert batch_windows(10, 10) == [list(range(10))]


def test_even_split():
    windows = batch_windows(15, 10)
    assert windows == [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [10, 11, 12, 13, 14]]


def test_multiple_full_windows():
    windows = batch_windows(25, 10)
    assert len(windows) == 3
    assert windows[0][0] == 0 and windows[-1] == [20, 21, 22, 23, 24]


def test_all_indices_covered_exactly_once():
    flat = [i for w in batch_windows(37, 5) for i in w]
    assert flat == list(range(37))


def test_degenerate_inputs():
    assert batch_windows(0, 10) == []
    assert batch_windows(5, 0) == []
