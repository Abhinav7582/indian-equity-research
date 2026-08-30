"""Tests for measuring drift against a declared allocation.

The refusals matter more than the arithmetic. A drift report built from a
template, from a policy that does not total 100, or from a misspelled bucket
name is not an error anyone would see — it is a plausible table of percentages
measured against something nobody chose.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from indian_equity_research.backtest.drift import (
    Band,
    DriftError,
    TargetPolicy,
    load_policy,
    measure_drift,
)

ON = dt.date(2026, 8, 30)


def policy(
    targets: dict[str, float] | None = None,
    absolute_pp: float = 5.0,
    relative_pct: float = 25.0,
    min_trade: float = 25_000.0,
    max_cost: float = 0.02,
) -> TargetPolicy:
    return TargetPolicy(
        version=1,
        declared_on=dt.date(2026, 8, 30),
        targets=targets or {"Equity": 40.0, "Gold": 10.0, "Debt": 50.0},
        band=Band(absolute_pp=absolute_pp, relative_pct=relative_pct),
        min_trade_rupees=min_trade,
        max_cost_fraction=max_cost,
    )


def write_policy(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The band rule
# ---------------------------------------------------------------------------


def test_the_relative_band_binds_on_a_small_target() -> None:
    """Five points is meaningless on a 3% target.

    The holding would have to nearly quadruple before an absolute band noticed,
    by which time it is no longer a small position at all.
    """
    band = Band(absolute_pp=5.0, relative_pct=25.0)
    assert band.width_for(3.0) == pytest.approx(0.75)


def test_the_absolute_band_binds_on_a_large_target() -> None:
    """Twenty-five percent relative would permit an 11pp swing on a 45% target."""
    band = Band(absolute_pp=5.0, relative_pct=25.0)
    assert band.width_for(45.0) == pytest.approx(5.0)


def test_a_bucket_inside_the_binding_band_is_not_drifted() -> None:
    report = measure_drift(policy(), {"Equity": 41.0, "Gold": 10.0, "Debt": 49.0}, ON)
    assert report.drifted == ()


def test_a_small_bucket_drifts_on_a_gap_a_large_one_would_not() -> None:
    """The same 3pp gap breaches at a 10% target and not at a 40% one.

    This is the whole reason both bands exist, so it is pinned down directly:
    Gold's band is 2.5pp (relative binds) and Equity's is 5pp (absolute binds),
    so an identical gap lands on opposite sides of the rule.
    """
    report = measure_drift(policy(), {"Equity": 37.0, "Gold": 13.0, "Debt": 50.0}, ON)
    by_name = {bucket.name: bucket for bucket in report.buckets}
    assert by_name["Equity"].gap_pp == pytest.approx(-3.0)
    assert by_name["Gold"].gap_pp == pytest.approx(+3.0)
    assert {bucket.name for bucket in report.drifted} == {"Gold"}


# ---------------------------------------------------------------------------
# The trade, and whether it is worth making
# ---------------------------------------------------------------------------


def test_the_correcting_trade_closes_the_gap_exactly() -> None:
    holdings = {"Equity": 300_000.0, "Gold": 250_000.0, "Debt": 450_000.0}
    report = measure_drift(policy(), holdings, ON)
    for bucket in report.buckets:
        corrected = bucket.value + bucket.trade_rupees
        assert 100.0 * corrected / report.total == pytest.approx(bucket.target_pct)


def test_an_overweight_bucket_gives_a_sale_and_an_underweight_one_a_purchase() -> None:
    holdings = {"Equity": 300_000.0, "Gold": 250_000.0, "Debt": 450_000.0}
    report = measure_drift(policy(), holdings, ON)
    by_name = {bucket.name: bucket for bucket in report.buckets}
    assert by_name["Gold"].gap_pp > 0
    assert by_name["Gold"].trade_rupees < 0
    assert by_name["Equity"].gap_pp < 0
    assert by_name["Equity"].trade_rupees > 0


def test_a_drifted_bucket_too_small_to_trade_is_still_reported_as_drifted() -> None:
    """The drift is real even where a trade is the wrong way to fix it.

    Suppressing it would hide a genuine breach behind an economic judgement,
    and the two questions deserve separate answers.
    """
    holdings = {"Equity": 3_700.0, "Gold": 1_300.0, "Debt": 5_000.0}
    report = measure_drift(policy(min_trade=25_000.0), holdings, ON)
    assert any(bucket.name == "Gold" for bucket in report.drifted)
    assert report.worth_making == ()


def test_an_expensive_correction_is_excluded_from_worth_making() -> None:
    """Friction above the declared budget fails the economic test.

    The DP charge and the brokerage floor are flat rupee amounts, so a small
    correcting trade can cost several percent of the sum it moves.
    """
    holdings = {"Equity": 3_700.0, "Gold": 1_300.0, "Debt": 5_000.0}
    report = measure_drift(policy(min_trade=0.0, max_cost=0.001), holdings, ON)
    assert report.drifted
    assert report.worth_making == ()


def test_a_large_cheap_correction_clears_both_tests() -> None:
    holdings = {"Equity": 3_000_000.0, "Gold": 2_500_000.0, "Debt": 4_500_000.0}
    report = measure_drift(policy(), holdings, ON)
    assert {bucket.name for bucket in report.worth_making} == {
        bucket.name for bucket in report.drifted
    }


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------


def test_a_holding_naming_an_undeclared_bucket_is_refused() -> None:
    """A typo would create a bucket at 0% target and empty the real one.

    Both halves of that error produce a plausible-looking row.
    """
    with pytest.raises(DriftError, match="does not declare"):
        measure_drift(policy(), {"Equity": 1.0, "Gold": 1.0, "Debt": 1.0, "Eqiuty": 1.0}, ON)


def test_a_declared_bucket_with_no_holding_is_refused() -> None:
    """An omission must not be readable as a zero."""
    with pytest.raises(DriftError, match="Pass 0 explicitly"):
        measure_drift(policy(), {"Equity": 1.0, "Gold": 1.0}, ON)


def test_an_empty_portfolio_is_refused() -> None:
    with pytest.raises(DriftError, match="no weight can be computed"):
        measure_drift(policy(), {"Equity": 0.0, "Gold": 0.0, "Debt": 0.0}, ON)


def test_a_template_policy_is_refused(tmp_path: Path) -> None:
    """The shipped file has null targets and must never run as a default."""
    path = write_policy(
        tmp_path / "t.yaml",
        "version: 0\ndeclared_on: 2026-08-30\nbuckets:\n"
        "  - name: Equity\n    target_pct: null\n"
        "  - name: Debt\n    target_pct: 100\n",
    )
    with pytest.raises(DriftError, match="still a template"):
        load_policy(path)


def test_targets_that_do_not_total_one_hundred_are_refused(tmp_path: Path) -> None:
    """Every weight is a share of the whole, so the whole has to be the whole."""
    path = write_policy(
        tmp_path / "t.yaml",
        "version: 1\ndeclared_on: 2026-08-30\nbuckets:\n"
        "  - name: Equity\n    target_pct: 40\n"
        "  - name: Debt\n    target_pct: 45\n",
    )
    with pytest.raises(DriftError, match="not 100%"):
        load_policy(path)


def test_rounding_to_one_decimal_place_is_tolerated(tmp_path: Path) -> None:
    """Three buckets at 33.3 total 99.9, which is arithmetic, not an error."""
    path = write_policy(
        tmp_path / "t.yaml",
        "version: 1\ndeclared_on: 2026-08-30\nbuckets:\n"
        "  - name: A\n    target_pct: 33.3\n"
        "  - name: B\n    target_pct: 33.3\n"
        "  - name: C\n    target_pct: 33.3\n",
    )
    assert sum(load_policy(path).targets.values()) == pytest.approx(99.9)


def test_a_duplicated_bucket_is_refused(tmp_path: Path) -> None:
    """One of the two would silently win, and the other vanish."""
    path = write_policy(
        tmp_path / "t.yaml",
        "version: 1\ndeclared_on: 2026-08-30\nbuckets:\n"
        "  - name: Equity\n    target_pct: 40\n"
        "  - name: Equity\n    target_pct: 60\n",
    )
    with pytest.raises(DriftError, match="twice"):
        load_policy(path)


def test_a_policy_without_a_date_is_refused(tmp_path: Path) -> None:
    """An undated policy cannot be told apart from one written after the fact."""
    path = write_policy(
        tmp_path / "t.yaml",
        "version: 1\nbuckets:\n  - name: Equity\n    target_pct: 100\n",
    )
    with pytest.raises(DriftError, match="no declared_on"):
        load_policy(path)


def test_a_missing_policy_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(DriftError, match="no target allocation"):
        load_policy(tmp_path / "absent.yaml")


# ---------------------------------------------------------------------------
# The shipped template
# ---------------------------------------------------------------------------


def test_the_committed_template_is_still_a_template() -> None:
    """The file in configs/ must not acquire targets by accident.

    If someone fills it in, this test fails and they must delete it deliberately
    — which is the point at which the policy stops being this project's default
    and starts being the owner's declaration.
    """
    shipped = Path(__file__).resolve().parents[2] / "configs" / "target_allocation.yaml"
    if not shipped.exists():  # pragma: no cover - repo layout guard
        pytest.skip("template not present")
    with pytest.raises(DriftError, match="still a template"):
        load_policy(shipped)


def test_no_output_names_an_action() -> None:
    """The report states a gap. It does not say whether to close it."""
    report = measure_drift(policy(), {"Equity": 300.0, "Gold": 250.0, "Debt": 450.0}, ON)
    forbidden = {"recommendation", "verdict", "should_rebalance", "advice", "action"}
    assert not forbidden & set(dir(report))
    assert not forbidden & set(dir(report.buckets[0]))
