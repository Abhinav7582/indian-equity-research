"""Tests for deciding when two tickers are the same security.

The test that justifies the module is
:func:`test_a_rename_chain_resolves_to_one_security`. The one that justifies the
guard is :func:`test_a_contaminated_graph_is_refused_rather_than_returned`.
"""

from __future__ import annotations

import pytest

from indian_equity_research.market.identity import (
    IdentityError,
    canonical_symbols,
    group_members,
)


def test_a_rename_chain_resolves_to_one_security() -> None:
    """MOTHERSUMI and MOTHERSON are one company under two tickers.

    Nothing joining on the ticker can know that, which is how three bonuses
    filed under the 2022 name failed to reach 2015 bars.
    """
    canonical = canonical_symbols(
        {
            "MOTHERSUMI": {"INE775A01035"},
            "MOTHERSON": {"INE775A01035"},
            "TATASTEEL": {"INE081A01020"},
        }
    )
    assert canonical["MOTHERSUMI"] == canonical["MOTHERSON"]
    assert canonical["TATASTEEL"] != canonical["MOTHERSON"]


def test_identity_survives_the_isin_changing_on_a_split() -> None:
    """The ISIN is not constant either.

    TIDEWATER traded under INE484C01022 before its 2021 bonus and split and
    INE484C01030 after. A rule matching on a single ISIN sees two securities;
    the transitive closure sees one, which is correct.
    """
    canonical = canonical_symbols(
        {
            "TIDEWATER": {"INE484C01022", "INE484C01030"},
            "VEEDOL": {"INE484C01030"},
        }
    )
    assert canonical["TIDEWATER"] == canonical["VEEDOL"]


def test_a_symbol_with_no_isin_stands_alone() -> None:
    """Nothing connects it, so nothing may be assumed about it."""
    canonical = canonical_symbols({"AAA": set(), "BBB": {"INE001A01001"}})
    assert canonical["AAA"] == "AAA"
    assert canonical["AAA"] != canonical["BBB"]


def test_the_representative_is_stable() -> None:
    """Two runs over the same data must name the same representative.

    A reconstruction that renames its own groups between runs cannot be
    compared against the one built yesterday.
    """
    data = {"ZZZ": {"I1"}, "AAA": {"I1"}, "MMM": {"I1"}}
    assert canonical_symbols(data) == canonical_symbols(dict(reversed(list(data.items()))))
    assert canonical_symbols(data)["ZZZ"] == "AAA"


def test_a_contaminated_graph_is_refused_rather_than_returned() -> None:
    """The failure that made the guard necessary.

    Run over debt rows, where NSE reuses short codes across bond series, one
    reused code chained IBULHSGFIN, CHOLAFIN and some two hundred bond lines
    into a single "security". A union-find has no opinion about whether a
    component is plausible, so the caller must.
    """
    contaminated = {f"BOND{i}": {"SHARED", f"I{i}"} for i in range(40)}
    with pytest.raises(IdentityError, match="cannot have that many names"):
        canonical_symbols(contaminated)


def test_a_plausible_rename_chain_is_allowed() -> None:
    """The guard must not fire on a company renamed a few times."""
    chain = {"A": {"I1"}, "B": {"I1", "I2"}, "C": {"I2", "I3"}, "D": {"I3"}}
    canonical = canonical_symbols(chain)
    assert len(set(canonical.values())) == 1


def test_group_members_inverts_the_mapping() -> None:
    canonical = canonical_symbols({"MOTHERSUMI": {"I1"}, "MOTHERSON": {"I1"}})
    groups = group_members(canonical)
    assert groups["MOTHERSON"] == ("MOTHERSON", "MOTHERSUMI")
