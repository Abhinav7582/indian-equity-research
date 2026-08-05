"""Series container and causal rolling statistics."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from indian_equity_research.research.series import (
    PriceSeries,
    align,
    rolling_mean,
    rolling_quantile,
    simple_returns,
)

START = date(2020, 1, 1)


def days(n: int) -> tuple[date, ...]:
    return tuple(START + timedelta(days=i) for i in range(n))


class TestPriceSeries:
    def test_valid_series(self) -> None:
        s = PriceSeries("X", days(3), (1.0, 2.0, 3.0))
        assert len(s) == 3

    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError, match="dates but"):
            PriceSeries("X", days(3), (1.0, 2.0))

    def test_unsorted_dates_rejected(self) -> None:
        with pytest.raises(ValueError, match="strictly increasing"):
            PriceSeries("X", (START + timedelta(days=1), START), (1.0, 2.0))

    def test_duplicate_dates_rejected(self) -> None:
        with pytest.raises(ValueError, match="strictly increasing"):
            PriceSeries("X", (START, START), (1.0, 2.0))

    def test_non_positive_close_rejected(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PriceSeries("X", days(2), (1.0, 0.0))

    def test_from_mapping_sorts_by_date(self) -> None:
        d = days(3)
        s = PriceSeries.from_mapping("X", {d[2]: 3.0, d[0]: 1.0, d[1]: 2.0})
        assert s.dates == d
        assert s.closes == (1.0, 2.0, 3.0)

    def test_slice_from(self) -> None:
        d = days(5)
        s = PriceSeries("X", d, (1.0, 2.0, 3.0, 4.0, 5.0))
        assert s.slice_from(d[2]).closes == (3.0, 4.0, 5.0)


class TestAlign:
    def test_restricts_to_common_dates(self) -> None:
        d = days(5)
        a = PriceSeries("A", d[:4], (1.0, 2.0, 3.0, 4.0))
        b = PriceSeries("B", d[2:], (30.0, 40.0, 50.0))
        dates, (va, vb) = align(a, b)
        assert dates == (d[2], d[3])
        assert va == (3.0, 4.0)
        assert vb == (30.0, 40.0)

    def test_single_series_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least two"):
            align(PriceSeries("A", days(2), (1.0, 2.0)))

    def test_no_overlap_rejected(self) -> None:
        d = days(6)
        a = PriceSeries("A", d[:2], (1.0, 2.0))
        b = PriceSeries("B", d[4:], (3.0, 4.0))
        with pytest.raises(ValueError, match="No overlapping dates"):
            align(a, b)


class TestRollingMean:
    def test_known_values(self) -> None:
        assert rolling_mean([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]

    def test_warmup_is_none_not_partial(self) -> None:
        """A partial average is not the statistic that was declared."""
        out = rolling_mean([10, 20, 30], 3)
        assert out[0] is None
        assert out[1] is None
        assert out[2] == 20.0

    def test_window_of_one_is_identity(self) -> None:
        assert rolling_mean([5, 6, 7], 1) == [5.0, 6.0, 7.0]

    def test_invalid_window_rejected(self) -> None:
        with pytest.raises(ValueError, match="window must be positive"):
            rolling_mean([1, 2, 3], 0)

    def test_is_causal(self) -> None:
        """Appending future observations must not change earlier values."""
        base = [1, 2, 3, 4, 5]
        short = rolling_mean(base, 3)
        long = rolling_mean([*base, 99, 100, 101], 3)
        assert long[: len(short)] == short


class TestRollingQuantile:
    def test_matches_linear_interpolation(self) -> None:
        # numpy.quantile([1,2,3,4,5], 0.8) == 4.2 with linear interpolation.
        out = rolling_quantile([1, 2, 3, 4, 5], 5, 0.8)
        assert out[:4] == [None, None, None, None]
        assert out[4] == pytest.approx(4.2)

    def test_median(self) -> None:
        assert rolling_quantile([1, 2, 3], 3, 0.5)[2] == pytest.approx(2.0)

    def test_window_slides_and_drops_stale_values(self) -> None:
        out = rolling_quantile([100, 1, 2, 3, 4, 5], 5, 1.0)
        assert out[4] == pytest.approx(100.0)  # window still contains the spike
        assert out[5] == pytest.approx(5.0)  # spike has aged out

    def test_handles_repeated_values(self) -> None:
        out = rolling_quantile([7, 7, 7, 7], 4, 0.8)
        assert out[3] == pytest.approx(7.0)

    @pytest.mark.parametrize("bad", [-0.1, 1.1])
    def test_invalid_quantile_rejected(self, bad: float) -> None:
        with pytest.raises(ValueError, match=r"quantile must be in \[0, 1\]"):
            rolling_quantile([1, 2, 3], 2, bad)

    def test_is_causal(self) -> None:
        base = [3, 1, 4, 1, 5, 9, 2, 6]
        short = rolling_quantile(base, 4, 0.8)
        long = rolling_quantile([*base, 100, 200], 4, 0.8)
        assert long[: len(short)] == short


class TestSimpleReturns:
    def test_known_values(self) -> None:
        assert simple_returns([100.0, 110.0, 99.0]) == pytest.approx([0.10, -0.10])

    def test_length_is_one_less(self) -> None:
        assert len(simple_returns([1.0, 2.0, 3.0, 4.0])) == 3
