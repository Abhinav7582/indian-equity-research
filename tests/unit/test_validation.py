"""Tests for purged, embargoed walk-forward splitting.

The test that matters is :func:`test_purging_removes_a_leak_a_naive_split_lets_through`.
Everything else is scaffolding around it. A splitter that produced tidy-looking
folds while still leaking would be worse than none, because it would carry the
authority of the word "cross-validated".
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.backtest.validation import (
    DEFAULT_EMBARGO_FRACTION,
    SplitError,
    WalkForwardSplit,
    purged_walk_forward,
    sessions_between,
)

START = dt.date(2015, 1, 1)


def sessions(n: int) -> list[dt.date]:
    """``n`` consecutive days. Weekends are irrelevant to the splitting logic."""
    return [START + dt.timedelta(days=i) for i in range(n)]


def forward_outcome(values: list[float], index: int, horizon: int) -> float:
    """The outcome under test: a mean over ``[index, index + horizon]``.

    This is the shape of every result the project will measure -- a position
    entered on a session and held for some period. Its value is not known at
    ``index``; it is known ``horizon`` sessions later, which is precisely why
    an observation near a fold boundary reaches across it.
    """
    window = values[index : index + horizon + 1]
    return sum(window) / len(window)


# ---------------------------------------------------------------------------
# The leak
# ---------------------------------------------------------------------------


def test_purging_removes_a_leak_a_naive_split_lets_through() -> None:
    """The test the module exists to pass.

    Construct a series that is zero everywhere except inside the test window.
    A forward-spanning outcome measured from a *training* session is then
    non-zero if and only if it reaches into the test period -- that is, exactly
    when the observation is contaminated.

    Both halves are asserted. Showing the purged split is clean proves nothing
    on its own: a splitter returning an empty training set would also be clean.
    The naive split must be shown to leak on the same data.
    """
    n, horizon = 400, 30
    days = sessions(n)
    split = purged_walk_forward(days, folds=1, horizon=horizon, embargo=0)[0]

    test_start_index = days.index(split.test[0])
    values = [0.0] * n
    for i in range(test_start_index, n):
        values[i] = 1.0

    # Naive: everything before the test window, nothing dropped.
    naive_train = days[:test_start_index]
    naive_leaked = [
        day for day in naive_train if forward_outcome(values, days.index(day), horizon) > 0.0
    ]
    purged_leaked = [
        day for day in split.train if forward_outcome(values, days.index(day), horizon) > 0.0
    ]

    assert naive_leaked, "the naive split must leak, or this test proves nothing"
    assert len(naive_leaked) == horizon
    assert purged_leaked == []


def test_disabling_the_purge_restores_the_leak() -> None:
    """horizon=0 is the broken version, and it must leak.

    Same mutation-testing logic as the self-deception suite: an assertion that
    cannot fail is decoration. If understating the horizon did *not*
    reintroduce the leak, purging would not be what removes it.
    """
    n, true_horizon = 400, 30
    days = sessions(n)
    unpurged = purged_walk_forward(days, folds=1, horizon=0, embargo=0)[0]

    test_start_index = days.index(unpurged.test[0])
    values = [0.0] * n
    for i in range(test_start_index, n):
        values[i] = 1.0

    leaked = [
        day
        for day in unpurged.train
        if forward_outcome(values, days.index(day), true_horizon) > 0.0
    ]
    assert len(leaked) == true_horizon


def test_a_backward_feature_cannot_leak_under_walk_forward() -> None:
    """The distinction the module docstring insists on, made executable.

    A backward-looking feature is the classic k-fold leak, and it is *already*
    impossible here because training precedes testing. Asserting it keeps
    anyone (including me) from later "fixing" the purge to be sized by the
    feature lookback, which would protect against nothing while leaving the
    real leak in place.
    """
    n, lookback = 400, 30
    days = sessions(n)
    split = purged_walk_forward(days, folds=1, horizon=0, embargo=0)[0]

    test_start_index = days.index(split.test[0])
    values = [0.0] * n
    for i in range(test_start_index, n):
        values[i] = 1.0

    def backward_feature(index: int) -> float:
        window = values[max(0, index - lookback) : index + 1]
        return sum(window) / len(window)

    # No purging at all, and still nothing leaks.
    assert all(backward_feature(days.index(day)) == 0.0 for day in split.train)


def test_the_purged_sessions_are_exactly_the_contaminated_ones() -> None:
    """Not merely sufficient -- purging must not be wasteful either.

    Dropping far more than necessary would look equally "safe" while quietly
    starving every fold of data.
    """
    days = sessions(400)
    split = purged_walk_forward(days, folds=1, horizon=30, embargo=0)[0]
    assert len(split.purged) == 30
    assert split.purged[-1] == days[days.index(split.test[0]) - 1]


# ---------------------------------------------------------------------------
# The embargo
# ---------------------------------------------------------------------------


def test_the_embargo_drops_a_buffer_beyond_the_purge() -> None:
    days = sessions(400)
    without = purged_walk_forward(days, folds=1, horizon=30, embargo=0)[0]
    with_gap = purged_walk_forward(days, folds=1, horizon=30, embargo=10)[0]
    assert len(with_gap.embargoed) == 10
    assert len(with_gap.train) == len(without.train) - 10
    assert with_gap.train[-1] < with_gap.embargoed[0] < with_gap.test[0]


def test_purged_and_embargoed_sessions_are_reported_separately() -> None:
    """When a fold is starved, which mechanism did it matters."""
    split = purged_walk_forward(sessions(400), folds=1, horizon=30, embargo=10)[0]
    assert not set(split.purged) & set(split.embargoed)
    assert split.dropped == 40
    assert "30 purged, 10 embargoed" in split.describe()


def test_the_default_embargo_is_one_percent_of_the_sample() -> None:
    days = sessions(1000)
    split = purged_walk_forward(days, folds=1, horizon=30)[0]
    assert len(split.embargoed) == int(1000 * DEFAULT_EMBARGO_FRACTION)


def test_a_short_sample_still_gets_a_one_session_embargo() -> None:
    """int(200 * 0.01) is 2, but the floor matters for smaller samples."""
    split = purged_walk_forward(sessions(60), folds=1, horizon=5)[0]
    assert len(split.embargoed) >= 1


# ---------------------------------------------------------------------------
# Walk-forward, not k-fold
# ---------------------------------------------------------------------------


def test_every_fold_trains_strictly_before_it_tests() -> None:
    """A model fitted on the future cannot be run in the present."""
    for split in purged_walk_forward(sessions(2861), folds=5, horizon=126):
        assert max(split.train) < min(split.test)


def test_test_windows_are_contiguous_and_do_not_overlap() -> None:
    splits = purged_walk_forward(sessions(2861), folds=5, horizon=126)
    seen: set[dt.date] = set()
    previous_end: dt.date | None = None
    for split in splits:
        assert not seen & set(split.test)
        seen |= set(split.test)
        if previous_end is not None:
            assert split.test[0] > previous_end
        previous_end = split.test[-1]


def test_the_training_window_expands() -> None:
    """Later folds see more history. Documented, because it biases fold results.

    Reporting a mean across folds would blend a fold trained on 900 sessions
    with one trained on 1,700 as though they were comparable measurements.
    """
    splits = purged_walk_forward(sessions(2861), folds=5, horizon=126)
    sizes = [len(s.train) for s in splits]
    assert sizes == sorted(sizes)
    assert sizes[-1] > sizes[0]


def test_folds_are_returned_in_chronological_order() -> None:
    splits = purged_walk_forward(sessions(2861), folds=4, horizon=126)
    assert [s.fold for s in splits] == [0, 1, 2, 3]
    assert [s.test[0] for s in splits] == sorted(s.test[0] for s in splits)


def test_a_realistic_configuration_produces_usable_folds() -> None:
    """2,861 sessions and a 126-session window -- the project's actual shape."""
    splits = purged_walk_forward(sessions(2861), folds=5, horizon=126)
    assert len(splits) == 5
    for split in splits:
        assert len(split.train) > 126
        assert len(split.test) == 2861 // 6
        assert len(split.purged) == 126


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_too_little_history_is_refused_not_silently_reduced() -> None:
    """Returning fewer folds than asked for would be the dangerous answer.

    The caller would believe it had cross-validated when it had not.
    """
    with pytest.raises(SplitError, match="is not enough for"):
        purged_walk_forward(sessions(200), folds=5, horizon=126)


def test_the_error_names_the_binding_fold_and_the_arithmetic() -> None:
    """An error that says only "not enough data" teaches nothing.

    The non-obvious part is that fold 0 binds: in an expanding window it has
    the least history, so a sample that is comfortable overall can still fail.
    """
    with pytest.raises(SplitError) as excinfo:
        purged_walk_forward(sessions(200), folds=5, horizon=126)
    message = str(excinfo.value)
    assert "the first fold trains on only" in message
    assert "purged" in message and "embargoed" in message
    assert "in an expanding window the first is always the tight one" in message


def test_a_fold_starved_by_purging_is_refused() -> None:
    with pytest.raises(SplitError, match="the first fold trains on only"):
        purged_walk_forward(sessions(400), folds=5, horizon=30, min_train=200)


def test_degenerate_arguments_are_refused() -> None:
    days = sessions(400)
    with pytest.raises(SplitError, match="folds must be at least 1"):
        purged_walk_forward(days, folds=0, horizon=30)
    with pytest.raises(SplitError, match="horizon must not be negative"):
        purged_walk_forward(days, folds=2, horizon=-1)
    with pytest.raises(SplitError, match="embargo must not be negative"):
        purged_walk_forward(days, folds=2, horizon=30, embargo=-5)
    with pytest.raises(SplitError, match="cannot be divided"):
        purged_walk_forward(sessions(3), folds=5, horizon=1)


def test_duplicate_and_unsorted_sessions_are_normalised() -> None:
    days = sessions(400)
    shuffled = list(reversed(days)) + days[:50]
    assert purged_walk_forward(shuffled, folds=2, horizon=30) == purged_walk_forward(
        days, folds=2, horizon=30
    )


# ---------------------------------------------------------------------------
# The dataclass guards its own invariants
# ---------------------------------------------------------------------------


def test_a_split_that_overlaps_is_rejected_however_it_was_built() -> None:
    """Reject an overlapping split however it was built.

    The invariant is checked at construction, not only at the point the
    splitter happens to enforce it.
    """
    days = sessions(10)
    with pytest.raises(SplitError, match="appear in both train and test"):
        WalkForwardSplit(
            train=tuple(days[:5]), test=tuple(days[4:]), purged=(), embargoed=(), fold=0
        )


def test_a_split_that_trains_on_the_future_is_rejected() -> None:
    days = sessions(10)
    with pytest.raises(SplitError, match="Walk-forward means"):
        WalkForwardSplit(
            train=tuple(days[5:]), test=tuple(days[:5]), purged=(), embargoed=(), fold=0
        )


def test_an_empty_side_is_rejected() -> None:
    days = sessions(10)
    with pytest.raises(SplitError, match="no training sessions"):
        WalkForwardSplit(train=(), test=tuple(days), purged=(), embargoed=(), fold=0)
    with pytest.raises(SplitError, match="no test sessions"):
        WalkForwardSplit(train=tuple(days), test=(), purged=(), embargoed=(), fold=0)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def test_sessions_between_is_inclusive_at_both_ends() -> None:
    days = sessions(100)
    got = sessions_between(days, days[10], days[20])
    assert got[0] == days[10]
    assert got[-1] == days[20]
    assert len(got) == 11


def test_sessions_between_handles_dates_outside_the_list() -> None:
    days = sessions(100)
    assert sessions_between(days, dt.date(2000, 1, 1), dt.date(2001, 1, 1)) == []
    assert len(sessions_between(days, dt.date(2000, 1, 1), dt.date(2100, 1, 1))) == 100
