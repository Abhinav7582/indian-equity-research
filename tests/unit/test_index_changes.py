"""Tests for the NSE press-release parser.

The fixture below is taken **verbatim** from the real release published on
22 August 2025 (``ind_prs22082025.pdf``), including its neighbouring sections.
Testing against invented text would prove only that the regexes match the
regexes; the point is that they match what NSE actually publishes.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.market.index_changes import (
    IndexChange,
    IndexChangeError,
    extract_effective_date,
    parse_index_section,
    reconstruct_membership,
)

# Verbatim extract from ind_prs22082025.pdf, trimmed to the surrounding
# sections so the section-isolation logic is genuinely exercised.
RELEASE = """PRESS RELEASE
Mumbai, August 22, 2025
Replacements in indices
The Index Maintenance Sub-Committee (Equity) of NSE Indices Limited has decided
to make replacement of stocks in various indices as part of its review. These changes
shall become effective from September 30, 2025 (close of September 29, 2025).
A. Replacements on account of semi-annual review of broad market indices:
1) Nifty 50
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Hero MotoCorp Ltd. HEROMOTOCO
2 IndusInd Bank Ltd. INDUSINDBK
The following companies are being included:
Sr. No. Company Name Symbol
1 InterGlobe Aviation Ltd. INDIGO
2 Max Healthcare Institute Ltd. MAXHEALTH
Note:
1. Hero MotoCorp Ltd. (free-float market cap Rs. 52,336 crores) and IndusInd Bank Ltd.
have been removed from Nifty 50 pursuant to its exclusion from Nifty 100 index.
2) Nifty 500
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Alivus Life Sciences Ltd. ALIVUS
2 Gujarat Narmada Valley Fertilizers and Chemicals Ltd. GNFC
The following companies are being included:
Sr. No. Company Name Symbol
1 Aditya Birla Lifestyle Brands Ltd. ABLBL
2 Aegis Vopak Terminals Ltd. AEGISVOPAK
3) Nifty 100
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Dabur India Ltd. DABUR
2 Hero MotoCorp Ltd. HEROMOTOCO
3 ICICI Prudential Life Insurance Company Ltd. ICICIPRULI
4 IndusInd Bank Ltd. INDUSINDBK
5 Swiggy Ltd. SWIGGY
The following companies are being included:
Sr. No. Company Name Symbol
1 Hindustan Zinc Ltd. HINDZINC
2 Max Healthcare Institute Ltd. MAXHEALTH
3 Mazagoan Dock Shipbuilders Ltd. MAZDOCK
4 Siemens Energy India Ltd. ENRIN
5 Solar Industries India Ltd. SOLARINDS
The above replacements will also be applicable to Nifty100 Equal Weight index.
4) Nifty Next 50
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Dabur India Ltd. DABUR
Sr. No. Company Name Symbol
2 ICICI Prudential Life Insurance Company Ltd. ICICIPRULI
3 InterGlobe Aviation Ltd. INDIGO
4 Swiggy Ltd. SWIGGY
Note:
1. InterGlobe Aviation Ltd. removed from Nifty Next 50 on inclusion in Nifty 50 index
The following companies are being included:
Sr. No. Company Name Symbol
1 Hindustan Zinc Ltd. HINDZINC
2 Mazagoan Dock Shipbuilders Ltd. MAZDOCK
3 Siemens Energy India Ltd. ENRIN
4 Solar Industries India Ltd. SOLARINDS
"""


# Verbatim extract from ind_prs24082015.pdf — a real release from *before* the
# 22 September 2015 rebrand, when the index was called "CNX 100 Index". Also a
# real example of an interim change: a demerger, not a semi-annual review.
RELEASE_2015 = """IISL
INDIA INDEX SERVICES & PRODUCTS LIMITED
Date: August 24, 2015
PRESS RELEASE
The Index Maintenance Sub-Committee has decided to make the following replacements
in various indices on account of proposed schemes of arrangement for demerger of Max
India Ltd. and Crompton Greaves Ltd. These changes shall become effective from
September 28, 2015 (close of September 24, 2015).
1) CNX Nifty Junior Index
The following company is being excluded:
Sr. No. Company Name Symbol
1 Crompton Greaves Ltd. CROMPGREAV
The following company is being included:
Sr. No. Company Name Symbol
1 Ashok Leyland Ltd. ASHOKLEY
2) CNX 100 Index
The following company is being excluded:
Sr. No. Company Name Symbol
1 Crompton Greaves Ltd. CROMPGREAV
The following company is being included:
Sr. No. Company Name Symbol
1 Ashok Leyland Ltd. ASHOKLEY
The above replacement will also be applicable to CNX 100 Equal Weight Index.
3) CNX 200 Index
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Crompton Greaves Ltd. CROMPGREAV
2 Max India Ltd. MAX
The following companies are being included:
Sr. No. Company Name Symbol
1 Balkrishna Industries Ltd. BALKRISIND
2 Kajaria Ceramics Ltd. KAJARIACER
8) CNX Infrastructure Index
The following company is being excluded and no inclusion shall be made:
Sr. No. Company Name Symbol
1 Crompton Greaves Ltd. CROMPGREAV
"""


# --------------------------------------------------------------------------
# The pre-2015 CNX naming
# --------------------------------------------------------------------------


def test_cnx_100_is_found_when_nifty_100_is_asked_for() -> None:
    """IISL renamed every index on 22 September 2015.

    A release from before that date calls the index "CNX 100 Index". Searching
    it for "Nifty 100" finds nothing, so without the alias table every
    pre-rebrand release would look like one that simply did not touch the
    index -- which is a different and wrong conclusion.
    """
    change = parse_index_section(
        RELEASE_2015, "Nifty 100", announced_on=dt.date(2015, 8, 24)
    )
    assert change.effective_from == dt.date(2015, 9, 28)
    assert change.excluded == ("CROMPGREAV",)
    assert change.included == ("ASHOKLEY",)


def test_old_names_for_other_indices_also_resolve() -> None:
    junior = parse_index_section(RELEASE_2015, "Nifty Next 50")
    assert junior.excluded == ("CROMPGREAV",)
    assert junior.included == ("ASHOKLEY",)

    two_hundred = parse_index_section(RELEASE_2015, "Nifty 200")
    assert two_hundred.excluded == ("CROMPGREAV", "MAX")
    assert two_hundred.included == ("BALKRISIND", "KAJARIACER")


def test_trailing_index_word_is_optional() -> None:
    """2015 headings read 'CNX 100 Index'; current ones read 'Nifty 100'."""
    assert parse_index_section(RELEASE_2015, "Nifty 100").included == ("ASHOKLEY",)
    assert parse_index_section(RELEASE, "Nifty 100").included[0] == "HINDZINC"


def test_an_exclusion_with_no_replacement_is_captured() -> None:
    """Capture an exclusion made without a replacement.

    'The following company is being excluded and no inclusion shall be made' is
    real phrasing from the 2015 release, and a genuine one-sided change.
    """
    change = parse_index_section(RELEASE_2015, "CNX Infrastructure")
    assert change.excluded == ("CROMPGREAV",)
    assert change.included == ()
    assert change.net_size_change == -1


def test_an_unknown_index_name_says_what_was_tried() -> None:
    with pytest.raises(IndexChangeError, match="CNX 100"):
        parse_index_section(RELEASE, "Nifty 100 Momentum 500")  # not in aliases
    with pytest.raises(IndexChangeError, match="renamed every index"):
        parse_index_section(RELEASE_2015, "Nifty 500")


# --------------------------------------------------------------------------
# The effective date must be read, never inferred
# --------------------------------------------------------------------------


def test_effective_date_is_read_from_the_text() -> None:
    """Not 22 August, which is when it was announced."""
    assert extract_effective_date(RELEASE) == dt.date(2025, 9, 30)


def test_missing_effective_date_raises_rather_than_guessing() -> None:
    """A change placed a month out corrupts every backtest spanning it."""
    text = RELEASE.replace(
        "shall become effective from September 30, 2025 (close of September 29, 2025).",
        "shall become effective in due course.",
    )
    with pytest.raises(IndexChangeError, match="no effective date"):
        extract_effective_date(text)


def test_alternative_date_phrasing_is_accepted() -> None:
    text = "These changes shall become effective from March 28, 2024 (close of March 27, 2024)."
    assert extract_effective_date(text) == dt.date(2024, 3, 28)


# --------------------------------------------------------------------------
# The right section, from a document full of near-identical ones
# --------------------------------------------------------------------------


def test_nifty_100_section_parses_exactly() -> None:
    change = parse_index_section(
        RELEASE, "Nifty 100", announced_on=dt.date(2025, 8, 22), source="ind_prs22082025.pdf"
    )
    assert change.effective_from == dt.date(2025, 9, 30)
    assert change.announced_on == dt.date(2025, 8, 22)
    assert change.excluded == ("DABUR", "HEROMOTOCO", "ICICIPRULI", "INDUSINDBK", "SWIGGY")
    assert change.included == ("HINDZINC", "MAXHEALTH", "MAZDOCK", "ENRIN", "SOLARINDS")
    assert change.net_size_change == 0


def test_neighbouring_sections_do_not_bleed_in() -> None:
    """The single most dangerous failure mode.

    Nifty 50, Nifty 500 and Nifty Next 50 all sit adjacent to Nifty 100 with
    identical table structure. Attaching the wrong index's changes would be
    completely invisible downstream.
    """
    nifty100 = parse_index_section(RELEASE, "Nifty 100")
    assert "ALIVUS" not in nifty100.excluded, "Nifty 500's exclusions leaked in"
    assert "ABLBL" not in nifty100.included, "Nifty 500's inclusions leaked in"
    assert "INDIGO" not in nifty100.included, "Nifty 50's inclusions leaked in"

    nifty50 = parse_index_section(RELEASE, "Nifty 50")
    assert nifty50.excluded == ("HEROMOTOCO", "INDUSINDBK")
    assert nifty50.included == ("INDIGO", "MAXHEALTH")
    assert "DABUR" not in nifty50.excluded


def test_a_note_block_does_not_become_table_rows() -> None:
    """Ignore a numbered Note block.

    Nifty 50's section has one after its tables, and numbered prose looks
    enough like a table row to be picked up if the parser is careless.
    """
    nifty50 = parse_index_section(RELEASE, "Nifty 50")
    assert len(nifty50.included) == 2
    assert all(len(s) <= 12 for s in nifty50.included + nifty50.excluded)


def test_repeated_header_from_a_page_break_is_ignored() -> None:
    """Ignore a header repeated by a page break.

    Nifty Next 50's exclusion table repeats 'Sr. No. Company Name Symbol'
    mid-table where the PDF broke across pages.
    """
    change = parse_index_section(RELEASE, "Nifty Next 50")
    assert change.excluded == ("DABUR", "ICICIPRULI", "INDIGO", "SWIGGY")


def test_absent_section_raises() -> None:
    with pytest.raises(IndexChangeError, match="no section heading"):
        parse_index_section(RELEASE, "Nifty Midcap 150")


def test_section_with_no_tables_raises() -> None:
    """A heading with no tables under it must fail rather than record nothing."""
    text = (
        "These changes shall become effective from September 30, 2025.\n"
        "3) Nifty 100\n"
        "No changes are being made in this index.\n"
        "4) Nifty Next 50\n"
        "The following companies are being excluded:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Dabur India Ltd. DABUR\n"
    )
    with pytest.raises(IndexChangeError, match="no exclusion or inclusion table"):
        parse_index_section(text, "Nifty 100")


def test_inclusions_without_exclusions_are_valid() -> None:
    """Accept a one-sided change.

    Real releases contain sections reading 'No exclusion is being made from the
    index'. That is legitimate, not a parse failure.
    """
    text = (
        "These changes shall become effective from September 30, 2025.\n"
        "2) Nifty India Corporate Group Index - Aditya Birla Group\n"
        "The following companies are being included:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Aditya Birla Lifestyle Brands Ltd. ABLBL\n"
        "2 India Cements Ltd. INDIACEM\n"
        "No exclusion is being made from the index.\n"
    )
    change = parse_index_section(text, "Nifty India Corporate Group Index - Aditya Birla Group")
    assert change.included == ("ABLBL", "INDIACEM")
    assert change.excluded == ()
    assert change.net_size_change == 2


def test_a_symbol_in_both_lists_is_rejected() -> None:
    with pytest.raises(IndexChangeError, match="both excluded and included"):
        IndexChange(
            index_name="Nifty 100",
            effective_from=dt.date(2025, 9, 30),
            announced_on=None,
            excluded=("DABUR", "SWIGGY"),
            included=("SWIGGY",),
        )


# --------------------------------------------------------------------------
# Walking backwards
# --------------------------------------------------------------------------


def test_reversing_a_change_restores_the_prior_membership() -> None:
    change = parse_index_section(RELEASE, "Nifty 100")
    current = {"HINDZINC", "MAXHEALTH", "MAZDOCK", "ENRIN", "SOLARINDS", "RELIANCE", "TCS"}

    before = reconstruct_membership(current, [change], dt.date(2025, 9, 1))
    assert before == {
        "DABUR",
        "HEROMOTOCO",
        "ICICIPRULI",
        "INDUSINDBK",
        "SWIGGY",
        "RELIANCE",
        "TCS",
    }

    after = reconstruct_membership(current, [change], dt.date(2025, 10, 1))
    assert after == current


def test_the_effective_date_boundary_is_inclusive() -> None:
    """On the effective date itself the new membership is already in force."""
    change = parse_index_section(RELEASE, "Nifty 100")
    current = {"HINDZINC", "MAXHEALTH", "MAZDOCK", "ENRIN", "SOLARINDS"}
    assert reconstruct_membership(current, [change], dt.date(2025, 9, 30)) == current
    assert "DABUR" in reconstruct_membership(current, [change], dt.date(2025, 9, 29))


def test_a_wrong_size_raises_instead_of_being_padded() -> None:
    """Catch a missing release via the size self-check.

    Under Amendment A5 a gap is reported, not patched.
    """
    change = parse_index_section(RELEASE, "Nifty 100")
    current = {"HINDZINC", "MAXHEALTH", "MAZDOCK", "ENRIN", "SOLARINDS"}
    with pytest.raises(IndexChangeError, match="press release is almost certainly missing"):
        reconstruct_membership(current, [change], dt.date(2025, 9, 1), expected_size=100)


def test_multiple_changes_reverse_in_the_right_order() -> None:
    older = IndexChange(
        index_name="Nifty 100",
        effective_from=dt.date(2024, 3, 28),
        announced_on=None,
        excluded=("OLDCO",),
        included=("MIDCO",),
    )
    newer = IndexChange(
        index_name="Nifty 100",
        effective_from=dt.date(2025, 9, 30),
        announced_on=None,
        excluded=("MIDCO",),
        included=("NEWCO",),
    )
    current = {"NEWCO", "STABLE"}

    assert reconstruct_membership(current, [older, newer], dt.date(2025, 1, 1)) == {
        "MIDCO",
        "STABLE",
    }
    assert reconstruct_membership(current, [older, newer], dt.date(2024, 1, 1)) == {
        "OLDCO",
        "STABLE",
    }
    assert reconstruct_membership(current, [newer, older], dt.date(2024, 1, 1)) == {
        "OLDCO",
        "STABLE",
    }


def test_describe_is_human_checkable() -> None:
    change = parse_index_section(RELEASE, "Nifty 100")
    text = change.describe()
    assert "2025-09-30" in text
    assert "DABUR" in text
    assert "HINDZINC" in text
