"""Tests for the adjustment verdict register.

The register is where a human's judgement enters the price data, so the tests
are about refusing input that would let a wrong judgement through silently.

The governing asymmetry: a real action marked ``crash`` leaves a visible fake
fall and understates the strategy. A real crash marked ``action`` erases the
fall and overstates it, leaving a series that is smooth, plausible and wrong.
The second is the one worth being strict about, and the strictness here is
deliberately one-sided.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from indian_equity_research.market.adjustment_verdicts import (
    VerdictError,
    load_verdicts,
)

HEADER = (
    "# Adjustment audit\n\n"
    "| date | symbol | multiplier | turnover x20d | ratio fit | hint | verdict |\n"
    "|---|---|---:|---:|---|---|---|\n"
)


def write(tmp_path: Path, rows: str) -> Path:
    path = tmp_path / "adjustment_audit.md"
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_a_crash_verdict_needs_nothing_else(tmp_path: Path) -> None:
    """The conservative direction, so it is accepted on its own."""
    path = write(
        tmp_path, "| 2015-06-03 | ADANIENT | 0.1723 | 3.4x | no clean ratio | x | crash |\n"
    )
    register = load_verdicts(path)
    assert len(register.verdicts) == 1
    assert register.verdicts[0].adjusts is False
    assert register.complete


def test_an_action_verdict_must_carry_a_multiplier(tmp_path: Path) -> None:
    """An adjustment with no ratio cannot be applied.

    This is the direction that hides its own errors, so it is refused rather
    than defaulted.
    """
    path = write(tmp_path, "| 2016-09-08 | BAJFINANCE | 0.2000 | 1.1x | 1-for-5 | x | action |\n")
    with pytest.raises(VerdictError, match="no multiplier"):
        load_verdicts(path)


def test_an_action_multiplier_must_match_the_move_it_explains(tmp_path: Path) -> None:
    """A verdict of '1:5 split' against an observed x0.68 is a contradiction.

    One of the two is wrong, and guessing which would defeat the point of
    having asked a human at all.
    """
    path = write(
        tmp_path, "| 2015-07-23 | MOTHERSUMI | 0.6681 | 0.6x | 1-for-2 | x | action x0.2 |\n"
    )
    with pytest.raises(VerdictError, match="disagree by more than"):
        load_verdicts(path)


def test_a_matching_action_multiplier_is_accepted(tmp_path: Path) -> None:
    path = write(
        tmp_path, "| 2015-07-23 | MOTHERSUMI | 0.6681 | 0.6x | 1-for-2 | x | action x0.667 |\n"
    )
    verdict = load_verdicts(path).verdicts[0]
    assert verdict.adjusts
    assert verdict.multiplier == pytest.approx(0.667)


def test_a_blank_verdict_is_outstanding_not_clean(tmp_path: Path) -> None:
    """The distinction the register exists to preserve.

    "Nobody has looked" and "looked, nothing to do" are different states.
    Treating blank as clean would silently reintroduce every error the audit
    was built to catch.
    """
    path = write(
        tmp_path,
        "| 2015-01-08 | BERGEPAINT | 0.5505 | 1.6x | no clean ratio | unclear |  |\n"
        "| 2015-06-03 | ADANIENT | 0.1723 | 3.4x | no clean ratio | x | crash |\n",
    )
    register = load_verdicts(path)
    assert register.outstanding == ((dt.date(2015, 1, 8), "BERGEPAINT"),)
    assert not register.complete
    assert "1 outstanding" in register.describe()


def test_an_invented_category_is_refused(tmp_path: Path) -> None:
    """Blank is honest; a made-up word is not."""
    path = write(
        tmp_path, "| 2015-06-03 | ADANIENT | 0.1723 | 3.4x | no ratio | x | probably fine |\n"
    )
    with pytest.raises(VerdictError, match="is not one of"):
        load_verdicts(path)


def test_a_missing_register_is_refused(tmp_path: Path) -> None:
    with pytest.raises(VerdictError, match="does not exist"):
        load_verdicts(tmp_path / "absent.md")


def test_a_data_verdict_adjusts_nothing(tmp_path: Path) -> None:
    """A bhavcopy defect is neither a crash nor an action."""
    path = write(
        tmp_path, "| 2015-06-03 | ADANIENT | 0.1723 | 3.4x | no ratio | x | data stale prev |\n"
    )
    assert load_verdicts(path).verdicts[0].adjusts is False


def test_verdicts_come_back_in_date_order(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "| 2020-06-03 | BBB | 0.5 | 1x | r | x | crash |\n"
        "| 2015-06-03 | AAA | 0.5 | 1x | r | x | crash |\n",
    )
    assert [v.symbol for v in load_verdicts(path).verdicts] == ["AAA", "BBB"]


def test_prose_outside_the_table_is_ignored(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "| 2015-06-03 | ADANIENT | 0.1723 | 3.4x | no ratio | x | crash |\n\n"
        "## Notes\n\nSome explanation mentioning 2015 and crash.\n",
    )
    assert len(load_verdicts(path).verdicts) == 1
