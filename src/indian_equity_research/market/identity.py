"""Decide when two tickers are the same security.

A ticker is not an identity. Over eleven years the archive contains
``MOTHERSUMI`` and ``MOTHERSON``, ``CADILAHC`` and ``ZYDUSLIFE``, ``MCDOWELL-N``
and ``UNITDSPR`` -- six symbols, three companies. Anything that joins two
datasets on the symbol will silently disagree with itself about which of those
existed when.

The ISIN is the identity, with one wrinkle: it changes when the share is
restructured. ``TIDEWATER`` traded under ``INE484C01022`` until its 2021 bonus
and split and ``INE484C01030`` after, and both belong to the same company.

So identity is not "shares an ISIN" but **the transitive closure of it**. Two
symbols are the same security if a chain of shared ISINs connects them, which is
a connected-components problem and is solved here with a union-find.

Transitivity is dangerous, and is bounded
-----------------------------------------
A transitive closure is only as good as its weakest link. Feed it NSE's **debt**
rows and it collapses: short codes are reused across bond series, one reused
code unions two issuers' ISINs, and the merge propagates. Run over the whole
archive without filtering, this produced a single "security" containing
``IBULHSGFIN``, ``SAMMAANCAP``, ``CHOLAFIN`` and roughly two hundred bond lines
-- and it produced it silently, because a union-find has no opinion about
whether a component is plausible.

So callers pass cash-equity rows only, and :func:`canonical_symbols` refuses any
group larger than :data:`MAX_GROUP_SIZE`. A company can be renamed several
times; it cannot be renamed forty times. An implausible component is a symptom
of contaminated input, and returning it as fact is worse than stopping.

What this deliberately does not do
----------------------------------
It never infers identity from a name, a sector, or a price path. Company names
in NSE's files are inconsistent across sources, and two unrelated securities can
look alike in every field except the one that matters. If no ISIN connects two
symbols, this reports them as different securities, and a caller that believes
otherwise must say so explicitly rather than have it guessed.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final

__all__ = ["MAX_GROUP_SIZE", "IdentityError", "canonical_symbols", "group_members"]

# Renames, demergers and re-listings can chain a security through several
# tickers. TIDEWATER/VEEDOL is two, and the longest genuine chain in the
# 2015-2026 equity archive is three. Eight leaves generous room for a history
# nobody anticipated while still catching a contaminated merge, which runs to
# hundreds rather than to nine.
MAX_GROUP_SIZE: Final = 8


class IdentityError(ValueError):
    """Raised when the ISIN graph implies a security that cannot exist."""


def canonical_symbols(
    isins_by_symbol: Mapping[str, Iterable[str]], *, max_group_size: int = MAX_GROUP_SIZE
) -> dict[str, str]:
    """Map every symbol to one representative symbol for its security.

    The representative is the lexicographically smallest symbol in the group,
    chosen only because it is stable: the same input always yields the same
    answer, which matters when a reconstruction is compared against one built
    yesterday.

    Args:
        isins_by_symbol: Every symbol seen, and the ISINs it traded under.
            Usually built from the bhavcopy archive, which carries both. Pass
            **cash-equity rows only**; debt rows reuse short codes and will
            chain unrelated issuers into one component.
        max_group_size: Largest plausible number of tickers for one security.

    Returns:
        ``{symbol: representative}``. A symbol with no ISIN maps to itself,
        because nothing connects it to anything.

    Raises:
        IdentityError: if any component exceeds ``max_group_size``.
    """
    parent: dict[str, str] = {symbol: symbol for symbol in isins_by_symbol}

    def find(symbol: str) -> str:
        root = symbol
        while parent[root] != root:
            parent[root] = parent[parent[root]]
            root = parent[root]
        return root

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    seen_isin: dict[str, str] = {}
    for symbol, isins in isins_by_symbol.items():
        for isin in isins:
            if not isin:
                continue
            first = seen_isin.setdefault(isin, symbol)
            union(first, symbol)

    groups: dict[str, list[str]] = {}
    for symbol in parent:
        groups.setdefault(find(symbol), []).append(symbol)

    oversized = sorted(
        (members for members in groups.values() if len(members) > max_group_size),
        key=len,
        reverse=True,
    )
    if oversized:
        worst = sorted(oversized[0])
        raise IdentityError(
            f"{len(oversized)} security group(s) exceed {max_group_size} tickers; the "
            f"largest has {len(oversized[0])}: {', '.join(worst[:12])}"
            f"{' ...' if len(worst) > 12 else ''}. One security cannot have that many "
            f"names. This is what a contaminated ISIN graph looks like -- almost always "
            f"debt rows, where NSE reuses short codes across series and a single reused "
            f"code chains two issuers together. Filter to cash-equity rows before "
            f"building identity."
        )

    out: dict[str, str] = {}
    for members in groups.values():
        representative = min(members)
        for symbol in members:
            out[symbol] = representative
    return out


def group_members(canonical: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Invert :func:`canonical_symbols`: representative to every ticker it covers.

    Args:
        canonical: Output of :func:`canonical_symbols`.

    Returns:
        ``{representative: (symbol, ...)}``, each tuple sorted.
    """
    out: dict[str, list[str]] = {}
    for symbol, representative in canonical.items():
        out.setdefault(representative, []).append(symbol)
    return {representative: tuple(sorted(v)) for representative, v in out.items()}
