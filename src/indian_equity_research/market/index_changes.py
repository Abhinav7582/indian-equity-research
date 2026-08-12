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
    "DEFERRED_RELEASES",
    "MANUAL_REGISTER_PATH",
    "IndexChange",
    "IndexChangeError",
    "ManualRegister",
    "drop_deferred",
    "extract_effective_date",
    "load_manual_register",
    "parse_index_list_exclusion",
    "parse_index_section",
    "parse_release",
    "read_release_pdf",
    "reconstruct_membership",
]

_MONTHS: Final = frozenset(
    {
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    }
)


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
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
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
    r"((?:" + "|".join(_spaced(month) for month in _MONTH_NAMES) + r"))\s*(\d{1,2})\s*,?\s*(\d{4})",
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

# NSE calls the listed entities "companies" in most years and "scrips" in
# others -- 2016 uses "The following scrips are being excluded". Requiring
# "companies" silently lost every 2016 release, and 2016 is the one year with
# no membership data at all. "securities" is included pre-emptively because the
# archive has already changed this noun once.
_ENTITY: Final = r"(?:compan(?:y|ies)|scrips?|securit(?:y|ies))"
_EXCLUDED_RE: Final = re.compile(rf"following\s+{_ENTITY}\s+(?:is|are)\s+being\s+excluded")
_INCLUDED_RE: Final = re.compile(rf"following\s+{_ENTITY}\s+(?:is|are)\s+being\s+included")
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
    sections = _isolate_sections(text, index_name)

    # A release can carry more than one section for the same index. Real
    # example, ind_prs20082020.pdf, titled "Revision in criteria AND
    # replacements in Indices": one "NIFTY 100" section is a table of eligibility
    # criteria, another is the actual replacement list. Taking the first match
    # found the criteria table, saw no companies in it, and reported the
    # September 2020 reconstitution as absent.
    #
    # So try every candidate and keep the one that actually carries a
    # membership table. Failing over is safe because a criteria section has no
    # exclusion or inclusion rows at all -- there is nothing to confuse it with.
    excluded: tuple[str, ...] = ()
    included: tuple[str, ...] = ()
    section = sections[0]
    for candidate in sections:
        candidate_excluded = _rows_after(candidate, _EXCLUDED_RE)
        candidate_included = _rows_after(candidate, _INCLUDED_RE)
        if candidate_excluded or candidate_included:
            section, excluded, included = candidate, candidate_excluded, candidate_included
            break

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


def _isolate_sections(text: str, index_name: str) -> list[str]:
    """Return every block of text belonging to a heading for this index.

    A release contains twenty or more sections with identical table structure,
    and occasionally **more than one** for the same index -- see the note in
    :func:`parse_index_section`. Each section runs from its own heading to the
    next one.

    Every known alias of ``index_name`` is tried, so a pre-2015 release naming
    the index "CNX 100 Index" is found when "Nifty 100" is asked for. A trailing
    "Index" is optional because older releases include it and current ones do
    not.
    """
    aliases = INDEX_ALIASES.get(index_name, (index_name,))
    next_heading = re.compile(rf"^\s*{_SECTION_NUMBER}\s*\S", re.MULTILINE)
    sections: list[str] = []

    for alias in aliases:
        # "Nifty 100" must also match a heading written "Nifty100".
        flexible = re.escape(alias).replace(r"\ ", r"\s*")
        heading = re.compile(
            rf"^\s*{_SECTION_NUMBER}\s*{flexible}(?:\s+Index)?\s*$",
            re.IGNORECASE | re.MULTILINE,
        )
        for match in heading.finditer(text):
            start = match.end()
            following = next_heading.search(text, start)
            end = following.start() if following else len(text)
            sections.append(text[start:end])
        if sections:
            # Aliases are alternative names for one index, not different
            # indices. Once one has matched, the others cannot also apply.
            break

    if not sections:
        tried = ", ".join(repr(a) for a in aliases)
        raise IndexChangeError(
            f"no section heading found for {index_name!r} (tried {tried}). Headings "
            f"look like '3) Nifty 100' or '2) CNX 100 Index' on their own line. "
            f"Either this release does not change that index, or the index used a "
            f"name not yet listed in INDEX_ALIASES — IISL renamed every index on "
            f"{REBRAND_DATE}, so pre-2015 releases use the CNX names."
        )
    return sections


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


# ---------------------------------------------------------------------------
# Announced, then withdrawn
# ---------------------------------------------------------------------------
#
# A release can announce a reconstitution that never happens. In March 2020 NSE
# deferred one "until further notice" and replaced it three months later:
#
#   18 Feb 2020  semi-annual review, to take effect 27 March 2020
#   16 Mar 2020  YES BANK removed early, effective 19 March -- this DID happen
#   23 Mar 2020  "Deferment of Index Rebalancing" -- the 27 March rebalancing is
#                deferred, citing circuit breakers, margins and travel curbs
#   25 Mar 2020  the SEBI-concentration changes deferred too, citing the lockdown
#   13 May 2020  revised plan announced
#   10 Jun 2020  the replacements that actually happened, effective 26 June
#
# Parsing alone cannot see this. The February release is a normal, well-formed
# document announcing changes on a stated date; nothing inside it says it was
# withdrawn. Applying both it and the June release removes five companies twice
# and leaves the membership wrong from March to June 2020.
#
# The giveaway, had it not been documented: ADANITRANS is an *inclusion* in both
# the deferred February release and the 16 March one that took effect. A company
# cannot join an index it is already in, which is why `IndexChange` rejects a
# symbol appearing on both sides and why `reconstruct_membership` checks size.
#
# Only the mapping is recorded here -- which release withdrew which. That is
# NSE's editorial history, not its constituent data, so unlike the membership
# lists it can live in version control.

DEFERRED_RELEASES: Final[dict[str, str]] = {
    "ind_prs18022020.pdf": "ind_prs23032020.pdf",
    "ind_prs12032020.pdf": "ind_prs23032020.pdf",
    "ind_prs19032020.pdf": "ind_prs23032020.pdf",
}


def drop_deferred(changes: list[IndexChange]) -> list[IndexChange]:
    """Remove changes from releases NSE later withdrew.

    Args:
        changes: Parsed changes, from any mixture of releases.

    Returns:
        Only the changes that actually took effect, in the order given.

    Raises:
        IndexChangeError: if a change carries no ``source``. A change that
            cannot be attributed to a release cannot be checked against the
            deferral list, and silently keeping it would reintroduce exactly the
            error this function exists to prevent.
    """
    kept: list[IndexChange] = []
    for change in changes:
        if not change.source:
            raise IndexChangeError(
                f"{change.describe()} has no source release, so it cannot be "
                f"checked against the deferral list. Pass source= when parsing."
            )
        if change.source not in DEFERRED_RELEASES:
            kept.append(change)
    return kept


# ---------------------------------------------------------------------------
# The second release format: one security, many indices
# ---------------------------------------------------------------------------
#
# When a security is cancelled, merged away or delisted, NSE does not write a
# per-index section. It writes one paragraph naming the security, then a table
# of the *index names* it drops out of:
#
#     Tata Motors Ltd., 'A' Ordinary Shares - DVR (Symbol: TATAMTRDVR) shall be
#     excluded from the following indices:
#
#     Sr. No.  Index Name
#     1        Nifty 100
#     ...
#     11       Nifty100 Equal Weight
#
# There is no "3) Nifty 100" heading anywhere, so `parse_index_section` reports
# that the release does not touch the index -- confidently, and wrongly.
#
# Exactly one release in the 2015-2026 archive uses this shape
# (`ind_prs23082024_1.pdf`, the Tata Motors DVR cancellation). It was found
# because the reconstructed index gained a net member over twelve years and a
# fixed-size index cannot do that. One release in 1,037 is easy to dismiss as
# not worth parsing; it is worth parsing precisely because it is rare enough to
# be missed and structural enough to recur at the next cancellation.
#
# Note rows 1 and 11 above. The same prefix trap as the section headings, in a
# different guise, which is why row matching is exact rather than by prefix.

_INDEX_LIST_RE: Final = re.compile(
    r"\(\s*Symbols?\s*:\s*(?P<symbols>[^)]{1,120}?)\s*\)"
    r"[^()]{0,160}?"
    r"(?:shall|will|would)\s+be\s+(?P<verb>excluded|included|removed|added)\s+"
    r"(?:from|in|to)\s+the\s+following\s+indices\s*:",
    re.IGNORECASE | re.DOTALL,
)
_INDEX_ROW_RE: Final = re.compile(r"^\s*(\d{1,2})[.)]?\s+(?P<name>\S.*?)\s*$")
_INDEX_LIST_HEADER_RE: Final = re.compile(r"^\s*Sr\.?\s*No\.?\s+Index\s+Name\s*$", re.IGNORECASE)


def _normalise_index_name(name: str) -> str:
    """Collapse an index name to a form safe to compare for equality.

    Case and internal spacing vary ("Nifty 100", "NIFTY100", "Nifty 100 Index"),
    but the *words* do not. Everything else must survive: "Nifty100 Equal
    Weight" has to stay distinguishable from "Nifty 100".
    """
    stripped = re.sub(r"\s+index\s*$", "", name.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", "", stripped).casefold()


def parse_index_list_exclusion(
    text: str,
    index_name: str,
    *,
    announced_on: date | None = None,
    source: str = "",
) -> IndexChange:
    """Extract a one-security change from a release that lists indices, not stocks.

    Args:
        text: Full text of the release.
        index_name: The index wanted, e.g. ``"Nifty 100"``.
        announced_on: Publication date, carried through for the audit trail.
        source: Filename, carried through for the audit trail.

    Returns:
        The change, with the named security on one side and nothing on the other.

    Raises:
        IndexChangeError: if the release does not use this format, or does not
            name this index. Both are ordinary outcomes for most releases.
    """
    aliases = {_normalise_index_name(a) for a in INDEX_ALIASES.get(index_name, (index_name,))}
    for match in _INDEX_LIST_RE.finditer(text):
        symbols = tuple(
            s.strip().upper() for s in re.split(r"[,;]", match.group("symbols")) if s.strip()
        )
        if not symbols:
            continue

        listed: list[str] = []
        started = False
        for line in text[match.end() :].splitlines():
            if not line.strip() or _INDEX_LIST_HEADER_RE.match(line):
                continue
            row = _INDEX_ROW_RE.match(line)
            if row is None:
                if started:
                    break
                continue
            started = True
            listed.append(_normalise_index_name(row.group("name")))

        if not listed:
            raise IndexChangeError(
                f"{source or 'release'} announces that {', '.join(symbols)} leaves "
                f"'the following indices' but no index table followed. The table has "
                f"probably been detached by PDF extraction. Reporting 'not affected' "
                f"here would silently keep a cancelled security in the index."
            )
        if not aliases & set(listed):
            continue

        removing = match.group("verb").lower() in {"excluded", "removed"}
        return IndexChange(
            index_name=index_name,
            effective_from=extract_effective_date(text),
            announced_on=announced_on,
            excluded=symbols if removing else (),
            included=() if removing else symbols,
            source=source,
        )

    raise IndexChangeError(
        f"no 'excluded from the following indices' block naming {index_name!r} was "
        f"found. This is the format NSE uses for a cancellation, merger or "
        f"delisting; most releases do not use it."
    )


def parse_release(
    text: str,
    index_name: str,
    *,
    announced_on: date | None = None,
    source: str = "",
) -> IndexChange:
    """Extract this index's changes from a release in either published format.

    Tries the per-index section first, then the one-security index-list form.
    Callers should prefer this to either parser alone: the section format covers
    the semi-annual reviews, and the list format covers the corporate actions
    between them.

    Raises:
        IndexChangeError: if neither format yields a change for this index --
            the ordinary outcome for a release about other indices.
    """
    try:
        return parse_index_section(text, index_name, announced_on=announced_on, source=source)
    except IndexChangeError as section_error:
        try:
            return parse_index_list_exclusion(
                text, index_name, announced_on=announced_on, source=source
            )
        except IndexChangeError as list_error:
            raise IndexChangeError(
                f"{source or 'release'} has no changes for {index_name!r} in either "
                f"published format.\n  as a section: {section_error}\n"
                f"  as an index list: {list_error}"
            ) from section_error


# ---------------------------------------------------------------------------
# Releases that only a human can read
# ---------------------------------------------------------------------------
#
# A minority of NSE releases are scans with no text layer. `read_release_pdf`
# refuses them rather than reporting "no changes", so they have to be read by
# eye (or OCR'd and then confirmed by eye) and the result written down.
#
# Why the answers are not committed to this repository
# ----------------------------------------------------
# `docs/data_sources.md` records that NSE prohibits redistribution outside a
# licensing agreement, and this project's rule is "never redistribute". A
# membership list transcribed from a release is still NSE's data. So the file
# read below lives under `data/`, which is git-ignored, and a clean clone finds
# it missing.
#
# That is deliberate. The alternative -- silently proceeding without the
# hand-read releases -- would produce a membership history that is wrong only
# during the periods nobody could parse, which is the hardest kind of error to
# notice. Missing file, loud failure, documented remedy.

MANUAL_REGISTER_PATH: Final = Path("data/reference/index_changes_manual.md")

_MANUAL_COLUMNS: Final = ("source", "index", "effective_from", "excluded", "included", "evidence")
_NO_CHANGE: Final = "no change"
_SYMBOL_RE: Final = re.compile(r"^[A-Z0-9&_.-]{1,20}$")


@dataclass(frozen=True, slots=True)
class ManualRegister:
    """Hand-verified readings of releases no parser could handle.

    ``no_change`` matters as much as ``changes``. A release recorded as leaving
    the index alone has been read and dismissed; one that is simply absent has
    not been read at all. Collapsing the two would let an unread reconstitution
    pass as a considered decision.
    """

    changes: tuple[IndexChange, ...]
    no_change: tuple[tuple[str, str], ...]
    source_path: Path

    def describe(self) -> str:
        """One line summarising what the human contributed."""
        return (
            f"{self.source_path}: {len(self.changes)} hand-read change(s), "
            f"{len(self.no_change)} release(s) read and found not to touch the index"
        )


def _split_symbols(cell: str, *, line_number: int, column: str) -> tuple[str, ...]:
    """Parse a comma-separated symbol cell, rejecting anything unlike a symbol.

    Raises:
        IndexChangeError: on a malformed symbol. OCR turns ``MRF`` into ``MRE``
            and drops characters entirely; a shape check will not catch a
            plausible misreading, but it does catch the obvious damage.
    """
    if not cell.strip():
        return ()
    symbols = tuple(part.strip().upper() for part in cell.split(",") if part.strip())
    for symbol in symbols:
        if not _SYMBOL_RE.match(symbol):
            raise IndexChangeError(
                f"line {line_number}: {symbol!r} in the {column!r} column does not look "
                f"like an NSE symbol. Symbols are upper-case and unspaced, e.g. "
                f"BANKBARODA. Company names belong in the release, not in this file."
            )
    if len(set(symbols)) != len(symbols):
        duplicates = sorted({s for s in symbols if symbols.count(s) > 1})
        raise IndexChangeError(f"line {line_number}: {duplicates} listed twice in {column!r}")
    return symbols


def _parse_manual_row(cells: list[str], line_number: int) -> tuple[IndexChange | None, str, str]:
    """Turn one table row into a change, or into a no-change record.

    Returns:
        ``(change_or_None, source, evidence)``.
    """
    row = dict(zip(_MANUAL_COLUMNS, cells, strict=True))
    source, evidence = row["source"].strip(), row["evidence"].strip()
    if not source:
        raise IndexChangeError(f"line {line_number}: the 'source' column is empty")
    if not evidence:
        raise IndexChangeError(
            f"line {line_number}: the 'evidence' column is empty. Record how the "
            f"release was read -- an unattributed reading cannot be re-checked."
        )

    excluded = _split_symbols(row["excluded"], line_number=line_number, column="excluded")
    included = _split_symbols(row["included"], line_number=line_number, column="included")
    stated = row["effective_from"].strip().lower()

    if stated in {_NO_CHANGE, "none", "-"}:
        if excluded or included:
            raise IndexChangeError(
                f"line {line_number}: recorded as '{_NO_CHANGE}' but lists symbols. "
                f"One of the two is wrong."
            )
        return None, source, evidence

    if not (excluded or included):
        raise IndexChangeError(
            f"line {line_number}: an effective date is given but no symbols. If the "
            f"release leaves the index alone, write '{_NO_CHANGE}' in the "
            f"'effective_from' column so it is unambiguous."
        )
    try:
        effective = datetime.strptime(stated, "%Y-%m-%d").replace(tzinfo=UTC).date()
    except ValueError as exc:
        raise IndexChangeError(
            f"line {line_number}: {row['effective_from']!r} is not a date in "
            f"YYYY-MM-DD form. Copy the date stated in the release text, not the "
            f"one in the filename -- they differ by about five weeks."
        ) from exc

    change = IndexChange(
        index_name=row["index"].strip(),
        effective_from=effective,
        announced_on=None,
        excluded=excluded,
        included=included,
        source=source,
    )
    return change, source, evidence


def load_manual_register(
    path: Path | None = None,
    *,
    index_name: str | None = None,
) -> ManualRegister:
    """Load hand-verified index changes from the git-ignored register.

    The file is a markdown table with the columns named in ``_MANUAL_COLUMNS``.
    Anything outside the table -- headings, prose, the notes explaining a
    judgement call -- is ignored, so the file can be written for a human first.

    Args:
        path: The register. Defaults to :data:`MANUAL_REGISTER_PATH`.
        index_name: If given, keep only rows for this index.

    Returns:
        The parsed register.

    Raises:
        IndexChangeError: if the file is missing, or any row is malformed. Both
            are refusals rather than warnings: a partially-read register would
            produce a membership history wrong only where nobody was looking.
    """
    target = path or MANUAL_REGISTER_PATH
    if not target.exists():
        raise IndexChangeError(
            f"{target} does not exist. Some NSE releases are scans with no text "
            f"layer and cannot be parsed; their contents must be read by eye and "
            f"recorded there. The file is git-ignored because NSE prohibits "
            f"redistribution, so a fresh clone will always need it rebuilt -- see "
            f"docs/circulars_worklist.md for which releases and where to look."
        )

    changes: list[IndexChange] = []
    no_change: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    width = len(_MANUAL_COLUMNS)

    for line_number, raw in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            continue  # the ---|--- separator
        if [cell.lower() for cell in cells] == list(_MANUAL_COLUMNS):
            continue  # the header
        if len(cells) != width:
            raise IndexChangeError(
                f"line {line_number}: {len(cells)} columns, expected {width} "
                f"({', '.join(_MANUAL_COLUMNS)}). A stray '|' inside a cell will do this."
            )

        change, source, evidence = _parse_manual_row(cells, line_number)
        row_index = change.index_name if change else cells[1].strip()
        key = (source, row_index)
        if key in seen:
            raise IndexChangeError(
                f"line {line_number}: {source} recorded twice for {row_index!r}. "
                f"Two readings of one release cannot both be right."
            )
        seen.add(key)

        if index_name is not None and row_index != index_name:
            continue
        if change is None:
            no_change.append((source, evidence))
        else:
            changes.append(change)

    return ManualRegister(
        changes=tuple(sorted(changes, key=lambda c: c.effective_from)),
        no_change=tuple(no_change),
        source_path=target,
    )
