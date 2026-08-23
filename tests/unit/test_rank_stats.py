"""Tests for the rank statistics H1 is measured with.

The test that justifies using rank rather than level is
:func:`test_one_enormous_mover_cannot_decide_the_answer`. The one that
justifies the tie handling is :func:`test_ties_take_their_average_rank`.
"""

from __future__ import annotations

import pytest

from indian_equity_research.research.rank_stats import (
    RankStatsError,
    decile_of,
    deciles,
    ranks,
    spearman,
)


def test_ties_take_their_average_rank() -> None:
    """Three values sharing positions 4, 5 and 6 each rank 5.0.

    Assigning them 4, 5, 6 in arrival order makes the statistic depend on dict
    ordering -- reproducible and meaningless.
    """
    assert ranks([10.0, 20.0, 20.0, 20.0, 30.0]) == [1.0, 3.0, 3.0, 3.0, 5.0]


def test_a_perfect_ordering_gives_plus_one() -> None:
    assert spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) == pytest.approx(1.0)


def test_a_reversed_ordering_gives_minus_one() -> None:
    assert spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0]) == pytest.approx(-1.0)


def test_one_enormous_mover_cannot_decide_the_answer() -> None:
    """Why H1 is measured on rank and not on level.

    Here the signal is *inversely* ordered against the outcome for every
    security except one, whose return is a hundredfold. A Pearson correlation
    on the raw values is dominated by that single name and comes out strongly
    positive; the rank correlation reports the ordering that actually holds.
    """
    signal = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    outcome = [0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 100.0]

    count = len(signal)
    mean_s = sum(signal) / count
    mean_o = sum(outcome) / count
    cov = sum((a - mean_s) * (b - mean_o) for a, b in zip(signal, outcome, strict=True))
    var_s = sum((a - mean_s) ** 2 for a in signal) ** 0.5
    var_o = sum((b - mean_o) ** 2 for b in outcome) ** 0.5
    pearson = cov / (var_s * var_o)

    # Opposite signs from the same data. That is the whole point: the level
    # correlation is decided by one security, the rank correlation by the
    # ordering that holds for the other seven.
    assert pearson > 0.5, "the level correlation is dragged positive by one name"
    assert spearman(signal, outcome) == pytest.approx(-1 / 3)


def test_subtracting_a_constant_leaves_the_ic_unchanged() -> None:
    """Excess returns and raw returns give the same rank IC.

    Worth pinning, because it is the reason nobody needs to agonise over what
    to subtract before computing an information coefficient.
    """
    signal = [3.0, 1.0, 4.0, 1.5, 5.0]
    outcome = [0.02, -0.01, 0.03, 0.00, 0.05]
    shifted = [value - 0.012 for value in outcome]
    assert spearman(signal, outcome) == pytest.approx(spearman(signal, shifted))


def test_a_constant_series_is_refused() -> None:
    """No correlation exists, and 0.0 would claim 'no relationship'."""
    with pytest.raises(RankStatsError, match="no measurement"):
        spearman([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])


def test_two_observations_are_refused() -> None:
    """With two points the answer is always exactly +1 or -1."""
    with pytest.raises(RankStatsError, match="at least 3"):
        spearman([1.0, 2.0], [3.0, 4.0])


def test_mismatched_lengths_are_refused() -> None:
    with pytest.raises(RankStatsError, match="lengths differ"):
        spearman([1.0, 2.0, 3.0], [1.0, 2.0])


# ---------------------------------------------------------------------------
# Deciles
# ---------------------------------------------------------------------------


def test_decile_one_holds_the_lowest_scores() -> None:
    """H1 is written as 'decile 10 outperforming decile 1'.

    Inverting this would flip the sign of every reported spread while leaving
    the monotonicity magnitude intact -- plausible output, opposite conclusion.
    """
    scored = [(f"S{i:02d}", float(i)) for i in range(20)]
    buckets = deciles(scored)
    assert buckets[0].symbols == ("S00", "S01")
    assert buckets[-1].symbols == ("S18", "S19")


def test_a_hundred_names_split_ten_and_ten() -> None:
    scored = [(f"S{i:03d}", float(i)) for i in range(100)]
    assert [b.size for b in deciles(scored)] == [10] * 10


def test_a_hundred_and_one_names_put_the_extra_in_the_lowest_decile() -> None:
    """The Nifty 100 ran at 101 while Tata Motors DVR was a constituent.

    The remainder has to go somewhere; spreading it across the lowest buckets
    is arbitrary but declared, and it is deterministic.
    """
    scored = [(f"S{i:03d}", float(i)) for i in range(101)]
    sizes = [b.size for b in deciles(scored)]
    assert sizes == [11, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    assert sum(sizes) == 101


def test_ties_break_on_symbol_so_the_split_is_reproducible() -> None:
    """Two runs over the same cross-section must produce the same deciles."""
    scored = [("CCC", 1.0), ("AAA", 1.0), ("BBB", 1.0), ("DDD", 2.0)]
    first = deciles(scored, buckets=2)
    second = deciles(list(reversed(scored)), buckets=2)
    assert [b.symbols for b in first] == [b.symbols for b in second]


def test_fewer_securities_than_deciles_is_refused() -> None:
    """An empty decile has no mean return.

    Reporting one as zero would place a fabricated observation in the middle of
    the monotonicity test.
    """
    with pytest.raises(RankStatsError, match="fabricated"):
        deciles([("A", 1.0), ("B", 2.0)], buckets=10)


def test_decile_of_finds_the_bucket() -> None:
    buckets = deciles([(f"S{i}", float(i)) for i in range(10)], buckets=5)
    assert decile_of("S0", buckets) == 1
    assert decile_of("S9", buckets) == 5
    assert decile_of("NOPE", buckets) is None
