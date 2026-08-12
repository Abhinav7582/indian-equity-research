"""Parse index membership changes from NSE Indices press releases.

What this reads
---------------
NSE Indices publishes constituent changes as *"Replacements in indices"* press
releases, not as circulars. Each covers every Nifty index; this module extracts
one index's section. See ``docs/universe_reconstruction.md`` for how to obtain
them.

The text is regular enough to parse reliably:

    3) Nifty 100
    The following companies are being excluded:
    Sr. No. Company Name Symbol
    1 Dabur India Ltd. DABUR
    ...
    The following companies are being included:
    Sr. No. Company Name Symbol
    1 Hindustan Zinc Ltd. HINDZINC
    ...

Two things this module refuses to guess
---------------------------------------
**The effective date.** It is stated in the release ("effective from September
30, 2025") and differs from the announcement date in the filename by about five
weeks. Inferring it from a rule of thumb would put every membership change in
the wrong place by a month, which is precisely the kind of error that produces a
plausible and wrong backtest. If it cannot be read from the text, parsing fails.

**Which index a table belongs to.** Section headings are matched exactly. A
release contains twenty or more index sections with near-identical table
structure, and attaching Nifty 500's changes to Nifty 100 would be undetectable
downstream.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

__all__ = [
    "IndexChange",
    "IndexChangeError",
    "extract_effective_date",
    "parse_index_section",
    "read_release_pdf",
    "reconstruct_membership",
]

_MONTHS: Final = frozenset({
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
})


def _spaced(literal: str) -> str:
    """Regex for ``literal`` tolerating spaces inserted between its characters.

    PDF text extraction routinely breaks words apart where the document used
    letter-spacing for layout. Real examples from this archive:

        "shall become eff ective from"
        "with effect from Ju ne 10, 2013"

    A regex written against the words as a human reads them misses both. This
    was worth 263 unparseable releases out of 1,037 before it was handled.
    """
    return r"\s*".join(re.escape(char) for char in literal if not char.isspace())


_MONTH_NAMES: Final = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Every phrasing observed across 1998-2026. NSE has used at least four:
#
#   "shall become effective from September 30, 2025"
#   "w.e.f. September 22, 2006"
#   "with effect from June 10, 2013"
#   "effective date of the above changes would be October 22, 2009"
_EFFECTIVE_RE: Final = re.compile(
    "(?:"
    + "|".join(
        _spaced(phrase)
        for phrase in ("effective from", "w.e.f.", "w.e.f", "with effect from", "would be")
    )
    + r")\s*(?:"
    + "|".join(_spaced(month) for month in _MONTH_NAMES)
    + r")\s*\d{1,2}\s*,?\s*\d{4}",
    re.IGNORECASE,
)
_DATE_PARTS_RE: Final = re.compile(
    r"((?:"
    + "|".join(_spaced(month) for month in _MONTH_NAMES)
    + r"))\s*(\d{1,2})\s*,?\s*(\d{4})",
    re.IGNORECASE,
)

# A table row: "1 Dabur India Ltd. DABUR". The symbol is the trailing token;
# NSE symbols are upper case and may contain digits, & and -.
_ROW_RE: Final = re.compile(r"^\s*\d+\s+(.+?)\s+([A-Z0-9&\-]{2,})\s*$")

# Section numbering is not consistent across the archive. All of these are real
# headings for the same index:
#
#     3) Nifty 100          (current)
#     (3) CNX 100 Index     (2013-2014, parenthesised)
#     d) Nifty 100          (2024, lettered once a release runs past nine)
#
# Requiring a bare "3)" missed 103 of 1,037 releases. Each looked exactly like
# a release that simply did not touch the index, which is a different and wrong
# conclusion -- and a silent one.
_SECTION_NUMBER: Final = r"\(?\s*(?:\d{1,2}|[A-Za-z])\s*\)"

_EXCLUDED_RE: Final = re.compile(r"following\s+compan(?:y|ies)\s+(?:is|are)\s+being\s+excluded")
_INCLUDED_RE: Final = re.compile(r"following\s+compan(?:y|ies)\s+(?:is|are)\s+being\s+included")
_HEADER_RE: Final = re.compile(r"^\s*Sr\.?\s*No\.?\s+Company\s+Name\s+Symbol\s*$", re.IGNORECASE)

# IISL rebranded every index on 22 September 2015: "CNX 100" became "Nifty 100",
# "CNX Nifty" became "Nifty 50", and so on. Releases before that date use the old
# names, and older headings often carry a trailing "Index" that current ones drop.
#
# This matters more than it looks. Searching a 2015 release for "Nifty 100" finds
# nothing, and the honest failure is an exception -- but only if the aliases are
# known. Without them the correct conclusion ("this release does not touch the
# index") and the wrong one ("it is called something else here") are
# indistinguishable.
REBRAND_DATE: Final = date(2015, 9, 22)

INDEX_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "Nifty 100": ("Nifty 100", "CNX 100"),
    "Nifty 50": ("Nifty 50", "CNX Nifty", "S&P CNX Nifty"),
    "Nifty Next 50": ("Nifty Next 50", "CNX Nifty Junior", "Nifty Junior"),
    "Nifty 200": ("Nifty 200", "CNX 200"),
    "Nifty 500": ("Nifty 500", "CNX 500"),
    "Nifty Midcap 100": ("Nifty Midcap 100", "CNX Midcap"),
    "Nifty Smallcap 100": ("Nifty Smallcap 100", "CNX Smallcap"),
}


class IndexChangeError(ValueError):
    """Raised when a press release cannot be parsed without guessing."""


@dataclass(frozen=True, slots=True)
class IndexChange:
    """Membership changes for one index at one review."""

    index_name: str
    effective_from: date
    announced_on: date | None
    excluded: tuple[str, ...]
    included: tuple[str, ...]
    source: str = ""

    def __post_init__(self) -> None:
        """Reject changes that cannot describe a real reconstitution."""
        overlap = set(self.excluded) & set(self.included)
        if overlap:
            raise IndexChangeError(
                f"{sorted(overlap)} appear as both excluded and included for "
                f"{self.index_name} on {self.effective_from}; the section was "
                f"probably mis-delimited"
            )

    @property
    def net_size_change(self) -> int:
        """Change in constituent count. Should be zero for a fixed-size index."""
        return len(self.included) - len(self.excluded)

    def describe(self) -> str:
        """One line a human can check against the source PDF."""
        return (
            f"{self.effective_from} {self.index_name}: "
            f"-{len(self.excluded)} +{len(self.included)} "
            f"(out: {', '.join(self.excluded) or 'none'}; "
            f"in: {', '.join(self.included) or 'none'})"
        )


def read_release_pdf(path: Path) -> str:
    """Extract the text of a press-release PDF.

    Args:
        path: The downloaded release.

    Returns:
        Text of every page, joined by newlines.

    Raises:
        IndexChangeError: if the file cannot be read, or yields no usable text.
            A scanned or image-only PDF produces an empty string, and returning
            that would present a document nobody has read as one containing no
            index changes.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IndexChangeError(
            "pypdf is required to read press releases; run `uv sync --extra dev`"
        ) from exc

    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise IndexChangeError(f"could not read {path.name}: {exc}") from exc

    if len(text.strip()) < 200:
        raise IndexChangeError(
            f"{path.name} yielded {len(text.strip())} characters of text. It is "
            f"probably a scan or an image-only PDF. Treating it as 'no changes' "
            f"would silently drop a reconstitution, so it is refused instead."
        )
    return text


def extract_effective_date(text: str) -> date:
    """Read the effective date stated in the release.

    Raises:
        IndexChangeError: if no effective date is stated. It is never inferred.
    """
    match = _EFFECTIVE_RE.search(text)
    if not match:
        raise IndexChangeError(
            "no effective date found in the release text. NSE has used at "
            "least four phrasings ('effective from', 'w.e.f.', 'with effect "
            "from', 'would be'), and PDF extraction sometimes splits words "
            "mid-letter. All are handled; if this still fails the document is "
            "probably a scan. The date must not be guessed: it is roughly five "
            "weeks after the announcement date in the filename, and a change "
            "placed a month out corrupts every backtest that spans it."
        )
    parts = _DATE_PARTS_RE.search(match.group(0))
    if not parts:  # pragma: no cover - the outer pattern guarantees this matches
        raise IndexChangeError(f"could not split {match.group(0)!r} into a date")

    month_name = re.sub(r"\s+", "", parts.group(1)).title()
    day, year = parts.group(2), parts.group(3)
    if month_name not in _MONTHS:
        raise IndexChangeError(f"unrecognised month {month_name!r} in effective date")
    # A date, not a timestamp: an index reconstitution has no time of day.
    return datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").replace(tzinfo=UTC).date()


def parse_index_section(
    text: str,
    index_name: str,
    *,
    announced_on: date | None = None,
    source: str = "",
) -> IndexChange:
    """Extract one index's changes from a press release.

    Args:
        text: Full extracted text of the release.
        index_name: Exact heading to match, e.g. ``"Nifty 100"``.
        announced_on: Publication date, usually from the filename.
        source: Filename or URL, retained for provenance.

    Returns:
        The parsed changes.

    Raises:
        IndexChangeError: if the section is absent, if no effective date is
            stated, or if the section contains neither exclusions nor inclusions.
    """
    effective = extract_effective_date(text)
    section = _isolate_section(text, index_name)

    excluded = _rows_after(section, _EXCLUDED_RE)
    included = _rows_after(section, _INCLUDED_RE)

    # A heading that announces a table and is followed by no rows means the
    # PDF laid its tables out away from their headings, and extraction has
    # emitted them detached. Real example, ind_prs01102010.pdf:
    #
    #     2) CNX 100 Index
    #     The following companies are being excluded :     <- no rows
    #     The following companies are being included:      <- no rows
    #     Sr. No. Company Name Symbol
    #     1 Zee Entertainment Enterprises Ltd. ZEEL        <- the EXCLUDED set
    #
    # Parsed naively this returns "0 out, 4 in" -- plausible, and wrong in both
    # directions at once. It was caught only because a fixed-size index cannot
    # gain four members, so refuse here rather than rely on that downstream.
    #
    # A genuinely one-sided change reads "excluded and no inclusion shall be
    # made", where the *included* marker is absent entirely rather than present
    # and empty. That case still parses.
    for marker, rows, label in (
        (_EXCLUDED_RE, excluded, "exclusion"),
        (_INCLUDED_RE, included, "inclusion"),
    ):
        if marker.search(section) and not rows:
            raise IndexChangeError(
                f"the {label} heading for {index_name!r} is followed by no table "
                f"rows. The PDF has laid its tables out away from their "
                f"headings, so which symbols belong to which side cannot be "
                f"determined from the extracted text. Read this release by hand."
            )

    if not excluded and not included:
        raise IndexChangeError(
            f"found a section for {index_name!r} but no exclusion or inclusion "
            f"table in it. Releases state 'No changes are being made in ...' for "
            f"unchanged indices; check whether that applies here rather than "
            f"recording an empty change."
        )

    return IndexChange(
        index_name=index_name,
        effective_from=effective,
        announced_on=announced_on,
        excluded=excluded,
        included=included,
        source=source,
    )


def _isolate_section(text: str, index_name: str) -> str:
    """Return the text belonging to one index heading.

    A release contains twenty or more sections with identical table structure.
    The section runs from its own numbered heading to the next one.

    Every known alias of ``index_name`` is tried, so a pre-2015 release naming
    the index "CNX 100 Index" is found when "Nifty 100" is asked for. A trailing
    "Index" is optional because older releases include it and current ones do
    not.
    """
    candidates = INDEX_ALIASES.get(index_name, (index_name,))
    for alias in candidates:
        # "Nifty 100" must also match a heading written "Nifty100".
        flexible = re.escape(alias).replace(r"\ ", r"\s*")
        heading = re.compile(
            rf"^\s*{_SECTION_NUMBER}\s*{flexible}(?:\s+Index)?\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        match = heading.search(text)
        if match:
            start = match.end()
            following = re.compile(rf"^\s*{_SECTION_NUMBER}\s*\S", re.MULTILINE).search(text, start)
            end = following.start() if following else len(text)
            return text[start:end]

    tried = ", ".join(repr(a) for a in candidates)
    raise IndexChangeError(
        f"no section heading found for {index_name!r} (tried {tried}). Headings "
        f"look like '3) Nifty 100' or '2) CNX 100 Index' on their own line. "
        f"Either this release does not change that index, or the index used a "
        f"name not yet listed in INDEX_ALIASES — IISL renamed every index on "
        f"{REBRAND_DATE}, so pre-2015 releases use the CNX names."
    )


def _rows_after(section: str, marker: re.Pattern[str]) -> tuple[str, ...]:
    """Collect symbols from the table following ``marker``.

    Stops at the next marker, the next heading, or the first line that is not a
    table row after the table has begun.
    """
    match = marker.search(section)
    if not match:
        return ()

    symbols: list[str] = []
    started = False
    for line in section[match.end() :].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _HEADER_RE.match(stripped):
            # Repeats when a table spans a page break.
            continue
        if _EXCLUDED_RE.search(stripped) or _INCLUDED_RE.search(stripped):
            break
        if stripped.lower().startswith("note"):
            break
        row = _ROW_RE.match(stripped)
        if row:
            started = True
            symbols.append(row.group(2))
            continue
        if started:
            break

    # Preserve order but drop duplicates from page-break repetition.
    seen: set[str] = set()
    unique = []
    for symbol in symbols:
        if symbol not in seen:
            seen.add(symbol)
            unique.append(symbol)
    return tuple(unique)


def reconstruct_membership(
    current: set[str],
    changes: list[IndexChange],
    as_of: date,
    *,
    expected_size: int | None = None,
) -> set[str]:
    """Membership as it stood on ``as_of``, walked backwards from ``current``.

    For every change effective *after* ``as_of``, the inclusion is removed and
    the exclusion added back.

    Args:
        current: Today's constituents.
        changes: All known changes for this index.
        as_of: The historical date wanted.
        expected_size: If given, the result must have exactly this many members.

    Returns:
        The reconstructed membership.

    Raises:
        IndexChangeError: if ``expected_size`` is given and not met. That
            mismatch means a release is missing, and under Amendment A5 it must
            be reported rather than patched.
    """
    members = set(current)
    for change in sorted(changes, key=lambda c: c.effective_from, reverse=True):
        if change.effective_from <= as_of:
            continue
        members -= set(change.included)
        members |= set(change.excluded)

    if expected_size is not None and len(members) != expected_size:
        applied = sum(1 for c in changes if c.effective_from > as_of)
        raise IndexChangeError(
            f"reconstructed membership on {as_of} has {len(members)} members, "
            f"expected {expected_size}, after reversing {applied} change(s). "
            f"A press release is almost certainly missing — most likely an "
            f"interim replacement for a merger or delisting, which are easy to "
            f"overlook because they fall outside the February and August "
            f"reviews. Report the gap; do not pad the list."
        )
    return members
