"""Tests for the guard that stops a registered baseline being silently skipped.

The failure this exists to prevent: Amendment A1 made the momentum index a
blocking baseline on 2026-08-04, trial #2 ran on 2026-08-23 scoring only the
Nifty 100 TRI, and nothing noticed for six days and three documents. The data
was on disk the whole time.
"""

from __future__ import annotations

from pathlib import Path

from indian_equity_research.research.h2_experiment import (
    REQUIRED_BASELINES,
    Baseline,
    BaselineOmitted,
)


def test_the_momentum_index_is_a_registered_baseline() -> None:
    """B3 is what A1 required and trial #2 omitted.

    If this assertion is ever deleted, the guard stops guarding the thing it
    was built for.
    """
    tags = {baseline.tag for baseline in REQUIRED_BASELINES}
    assert "B3" in tags
    b3 = next(b for b in REQUIRED_BASELINES if b.tag == "B3")
    assert "momentum30" in str(b3.directory).lower()
    assert b3.declared_by == "Amendment A1"


def test_every_baseline_names_the_amendment_that_requires_it() -> None:
    """A baseline nobody can trace to a declaration is one nobody can defend."""
    for baseline in REQUIRED_BASELINES:
        assert baseline.declared_by, f"{baseline.tag} does not say who declared it"
        assert baseline.expense_ratio >= 0.0
        assert isinstance(baseline.directory, Path)


def test_the_baselines_are_distinct() -> None:
    """Two entries pointing at one series would look like two checks and be one."""
    assert len({b.tag for b in REQUIRED_BASELINES}) == len(REQUIRED_BASELINES)
    assert len({b.directory for b in REQUIRED_BASELINES}) == len(REQUIRED_BASELINES)


def test_the_omission_error_exists_and_is_not_a_value_error() -> None:
    """It must be hard to catch by accident.

    A bare ``except ValueError`` around a run should not swallow the one signal
    that a declared comparison was never made.
    """
    assert issubclass(BaselineOmitted, RuntimeError)
    assert not issubclass(BaselineOmitted, ValueError)


def test_a_baseline_is_immutable() -> None:
    """A registry that can be edited at runtime is not a registry."""
    b = REQUIRED_BASELINES[0]
    assert isinstance(b, Baseline)
    try:
        b.tag = "changed"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Baseline should be frozen")
