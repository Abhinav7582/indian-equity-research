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
    drop_deferred,
    extract_effective_date,
    parse_index_list_exclusion,
    parse_index_section,
    parse_release,
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
    change = parse_index_section(RELEASE_2015, "Nifty 100", announced_on=dt.date(2015, 8, 24))
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


# --------------------------------------------------------------------------
# PDF layout defects that produce plausible, wrong answers
# --------------------------------------------------------------------------

# Verbatim from ind_prs01102010.pdf, whose tables are laid out away from their
# headings. Extraction emits every heading first, then every table body.
DETACHED_2010 = """The Committee has decided to make the following changes
which will become effective from October 7, 2010:
1) CNX Nifty Junior
The following companies are being excluded :
The following companies are being included:
2) CNX 100 Index
The following companies are being excluded :
The following companies are being included:
Sr. No. Company Name  Symbol
1 Zee Entertainment Enterprises Ltd. ZEEL
2 Reliance Natural Resources Ltd. RNRL
Sr. No. Company Name  Symbol
1 Exide Industries Ltd. EXIDEIND
2 Tata Chemicals Ltd. TATACHEM
"""


def test_a_heading_with_no_rows_beneath_it_is_refused() -> None:
    """Regression test for the most dangerous failure seen in this archive.

    Parsed naively this release returns "0 excluded, 4 included" -- which for
    a fixed-size index is impossible, and which silently mislabels the excluded
    set as the included one. It looked entirely plausible and was caught only
    because the net size change across all releases came out non-zero.

    Refusing here means the error surfaces on the release that caused it.
    """
    with pytest.raises(IndexChangeError, match="followed by no table rows"):
        parse_index_section(DETACHED_2010, "Nifty 100")


def test_the_refusal_names_the_cause_not_just_the_symptom() -> None:
    try:
        parse_index_section(DETACHED_2010, "Nifty 100")
    except IndexChangeError as exc:
        message = str(exc)
    assert "laid its tables out away from their" in message
    assert "by hand" in message, "the reader needs to know what to do next"


def test_a_genuinely_one_sided_change_still_parses() -> None:
    """The guard must not reject the legitimate case it resembles.

    Here the *included* marker is absent entirely rather than present and
    empty, which is how NSE writes a removal with no replacement.
    """
    text = (
        "These changes shall become effective from September 28, 2015.\n"
        "8) CNX Infrastructure Index\n"
        "The following company is being excluded and no inclusion shall be made:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Crompton Greaves Ltd. CROMPGREAV\n"
    )
    change = parse_index_section(text, "CNX Infrastructure")
    assert change.excluded == ("CROMPGREAV",)
    assert change.included == ()


def test_alternate_effective_date_phrasings_all_parse() -> None:
    """Parse every effective-date wording NSE has used.

    At least four across 1998-2026, and PDF extraction splits words
    mid-letter. Between them these were worth 148 unparseable releases.
    """
    cases = {
        "shall become effective from September 30, 2025": dt.date(2025, 9, 30),
        "w.e.f. September 22, 2006:": dt.date(2006, 9, 22),
        "shall become eff ective from March 28, 2014": dt.date(2014, 3, 28),
        "with effect from Ju ne 10, 2013": dt.date(2013, 6, 10),
        "effective date of the above changes would be October 22, 2009": dt.date(2009, 10, 22),
    }
    for text, expected in cases.items():
        assert extract_effective_date(text) == expected, text


# Modelled on ind_prs20082020.pdf, titled "Revision in criteria and replacements
# in Indices". It carries two NIFTY 100 sections: an eligibility-criteria table
# and, further down, the actual replacement list.
TWO_SECTIONS = """Press Release August 20, 2020
Revision in criteria and replacements in Indices
These changes shall become effective from September 25, 2020.
A. Revision in eligibility criteria
B) NIFTY 100
Parameter Existing Criteria Revised Criteria
Eligible universe 1. Constituent of NIFTY 500 index
2. Investible weight factor of at least 0.10
C) NIFTY 500
Parameter Existing Criteria Revised Criteria
Eligible universe 1. Listed on NSE
D. Replacements on account of semi-annual review
B) NIFTY 100
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Bharti Infratel Ltd. INFRATEL
2 Vodafone Idea Ltd. IDEA
The following companies are being included:
Sr. No. Company Name Symbol
1 Adani Green Energy Ltd. ADANIGREEN
2 Aurobindo Pharma Ltd. AUROPHARMA
E) NIFTY 50
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Zee Entertainment Enterprises Ltd. ZEEL
"""


def test_a_criteria_section_does_not_hide_the_replacement_section() -> None:
    """Regression test for the missing September 2020 reconstitution.

    A release headed "Revision in criteria AND replacements" carries two
    sections for the same index. Taking the first match found the criteria
    table, saw no company rows in it, and reported the reconstitution as
    absent -- which read as "NSE skipped a review", not as a parse failure.
    """
    change = parse_index_section(TWO_SECTIONS, "Nifty 100", announced_on=dt.date(2020, 8, 20))
    assert change.effective_from == dt.date(2020, 9, 25)
    assert change.excluded == ("INFRATEL", "IDEA")
    assert change.included == ("ADANIGREEN", "AUROPHARMA")


def test_the_wrong_section_is_not_silently_preferred() -> None:
    """The criteria section must not contribute rows of its own.

    Its table has a "Parameter / Existing / Revised" shape and numbered lines,
    which is close enough to a company table to be picked up by a careless
    row matcher.
    """
    change = parse_index_section(TWO_SECTIONS, "Nifty 100")
    for symbol in change.excluded + change.included:
        assert symbol not in {"NIFTY", "500"}
    assert change.net_size_change == 0


def test_scrips_wording_parses_as_well_as_companies() -> None:
    """NSE says "scrips" in 2016 and "companies" elsewhere.

    Requiring "companies" lost every 2016 release, and 2016 was the only year
    with no membership data at all.
    """
    text = (
        "These changes shall become effective from April 1, 2016.\n"
        "15) Nifty 100 Index\n"
        "The following scrips are being excluded:\n"
        "Sr. No. Scrip Name Symbol\n"
        "1 Bank of India BANKINDIA\n"
        "The following scrips are being included:\n"
        "Sr. No. Scrip Name Symbol\n"
        "1 ABB India Ltd. ABB\n"
    )
    change = parse_index_section(text, "Nifty 100")
    assert change.excluded == ("BANKINDIA",)
    assert change.included == ("ABB",)


def test_parenthesised_and_lettered_headings_are_found() -> None:
    """Find headings numbered every way NSE has used.

    They are '3)', '(3)' and 'd)' in different years. Requiring a bare '3)'
    lost 103 releases, each looking like one that did not touch the index.
    """
    for heading in ("3) Nifty 100", "(3) Nifty 100", "d) Nifty 100", "(d) Nifty 100 Index"):
        text = (
            "effective from September 30, 2025\n"
            f"{heading}\n"
            "The following companies are being excluded:\n"
            "Sr. No. Company Name Symbol\n"
            "1 Dabur India Ltd. DABUR\n"
        )
        assert parse_index_section(text, "Nifty 100").excluded == ("DABUR",), heading


# ---------------------------------------------------------------------------
# Sibling indices whose names begin with the index we want
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sibling",
    [
        "NIFTY100 Equal Weight",
        "NIFTY100 Liquid 15",
        "NIFTY100 Low Volatility 30",
        "NIFTY100 Quality 30",
        "NIFTY100 Alpha 30",
        "NIFTY100 ESG",
        "NIFTY100 Enhanced ESG",
        "Nifty 100 Equal Weight Index",
    ],
)
def test_a_sibling_index_is_never_mistaken_for_the_parent(sibling: str) -> None:
    """Reject headings that merely *start* with the index name.

    NSE publishes at least seven indices called ``NIFTY100 <something>``. Their
    sections sit in the same release, with identical table structure, a few
    pages from the real one. Matching a prefix would silently attach the wrong
    constituents -- a failure that produces a complete, plausible membership
    history that is simply not the Nifty 100.

    Found in ``ind_prs10092018.pdf``, whose only mention of the string is
    ``4) NIFTY100 Low Volatility 30: No Change``.
    """
    text = (
        "effective from September 30, 2018\n"
        f"3) {sibling}\n"
        "The following companies are being excluded:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Dabur India Ltd. DABUR\n"
    )
    with pytest.raises(IndexChangeError, match="no section heading found"):
        parse_index_section(text, "Nifty 100")


def test_the_parent_is_still_found_beside_its_siblings() -> None:
    """The guard above must not make the real section unfindable."""
    text = (
        "effective from September 30, 2018\n"
        "3) Nifty 100\n"
        "The following companies are being excluded:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Abbott India Ltd. ABBOTINDIA\n"
        "The following companies are being included:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Bank of Baroda BANKBARODA\n"
        "4) NIFTY100 Low Volatility 30: No Change\n"
        "5) NIFTY100 Equal Weight\n"
        "The following companies are being excluded:\n"
        "Sr. No. Company Name Symbol\n"
        "1 Wipro Ltd. WIPRO\n"
    )
    change = parse_index_section(text, "Nifty 100")
    assert change.excluded == ("ABBOTINDIA",)
    assert change.included == ("BANKBARODA",)


# ---------------------------------------------------------------------------
# The second published format: one security, a table of index names
# ---------------------------------------------------------------------------

# Verbatim from ind_prs23082024_1.pdf, the Tata Motors DVR cancellation. Rows 1
# and 11 are the point: "Nifty 100" and "Nifty100 Equal Weight" are different
# indices one line apart.
DVR_RELEASE = """PRESS RELEASE
Mumbai, August 23, 2024
Replacements in indices
These changes shall become effective from August 30, 2024 (close of August 29, 2024).
A. Exclusion of Tata Motors Ltd. 'A' Ordinary Shares - DVR:
On account of announcement of record date (September 01, 2024) by Tata Motors Ltd.
for implementation of scheme of arrangement involving reduction of capital by way of
cancellation of the entire 'A' Ordinary Shares, Tata Motors Ltd., 'A' Ordinary Shares -
DVR (Symbol: TATAMTRDVR) shall be excluded from the following indices:
Sr. No. Index Name
1 Nifty 100
2 Nifty 200
3 Nifty 500
4 Nifty Auto
11 Nifty100 Equal Weight
12 Nifty500 Equal Weight
Consequently, the equity shares and investible weight factor (IWF) of Tata Motors Ltd.
shall be revised based on the terms of shares exchange ratio.
B. Replacements on account of monthly review of Nifty Shariah indices:
1) Nifty50 Shariah
The following company is being included:
Sr. No. Company Name Symbol
1 Britannia Industries Ltd. BRITANNIA
"""


def test_a_cancellation_release_is_parsed_from_the_index_list() -> None:
    """The release that closed the net-size discrepancy.

    Twelve years of parsed reviews left the Nifty 100 one member larger than it
    started. A fixed-size index cannot do that, and the missing entry was this
    release -- which has no '3) Nifty 100' heading at all.
    """
    change = parse_index_list_exclusion(
        DVR_RELEASE, "Nifty 100", announced_on=dt.date(2024, 8, 23), source="ind_prs23082024_1.pdf"
    )
    assert change.excluded == ("TATAMTRDVR",)
    assert change.included == ()
    assert change.effective_from == dt.date(2024, 8, 30)
    assert change.net_size_change == -1


def test_the_equal_weight_row_does_not_count_as_the_parent_index() -> None:
    """Rows 1 and 11 of the same table are different indices.

    Matching by prefix would return a change for every ``Nifty100 *`` index in
    the list, each attributed to the parent.
    """
    change = parse_index_list_exclusion(DVR_RELEASE, "Nifty 500")
    assert change.excluded == ("TATAMTRDVR",)
    for absent in ("Nifty 50", "Nifty Midcap 100", "Nifty Next 50"):
        with pytest.raises(IndexChangeError, match="no 'excluded from the following indices'"):
            parse_index_list_exclusion(DVR_RELEASE, absent)


def test_the_section_format_is_not_read_as_an_index_list() -> None:
    """The two parsers must not both claim the same release."""
    with pytest.raises(IndexChangeError, match="no 'excluded from the following indices'"):
        parse_index_list_exclusion(RELEASE, "Nifty 100")


def test_a_detached_index_table_is_refused_not_ignored() -> None:
    """A marker with no table behind it means extraction lost the table.

    Silently concluding 'not affected' would keep a cancelled security in the
    index for the rest of the backtest.
    """
    text = (
        "effective from August 30, 2024\n"
        "DVR (Symbol: TATAMTRDVR) shall be excluded from the following indices:\n"
    )
    with pytest.raises(IndexChangeError, match="no index table followed"):
        parse_index_list_exclusion(text, "Nifty 100")


def test_an_inclusion_phrased_as_an_index_list_lands_on_the_right_side() -> None:
    text = (
        "effective from August 30, 2024\n"
        "Something Ltd. (Symbol: NEWCO) shall be included in the following indices:\n"
        "Sr. No. Index Name\n"
        "1 Nifty 100\n"
    )
    change = parse_index_list_exclusion(text, "Nifty 100")
    assert change.included == ("NEWCO",)
    assert change.excluded == ()


def test_parse_release_accepts_both_formats() -> None:
    """One entry point, both published shapes, neither result altered."""
    assert parse_release(RELEASE, "Nifty 100") == parse_index_section(RELEASE, "Nifty 100")
    assert parse_release(DVR_RELEASE, "Nifty 100") == parse_index_list_exclusion(
        DVR_RELEASE, "Nifty 100"
    )
    assert parse_release(DVR_RELEASE, "Nifty 100").excluded == ("TATAMTRDVR",)


def test_parse_release_reports_both_failures_when_neither_format_applies() -> None:
    """The error has to say which formats were tried, or it teaches nothing."""
    with pytest.raises(IndexChangeError) as excinfo:
        parse_release(DVR_RELEASE, "Nifty Midcap 100", source="x.pdf")
    message = str(excinfo.value)
    assert "as a section:" in message
    assert "as an index list:" in message


# ---------------------------------------------------------------------------
# Announced, then withdrawn
# ---------------------------------------------------------------------------


def test_a_deferred_release_is_dropped() -> None:
    """March 2020: announced, deferred "until further notice", never applied.

    Nothing inside the February release says it was withdrawn -- it is a normal,
    well-formed document announcing changes on a stated date. Only the later
    "Deferment of Index Rebalancing" release says otherwise.
    """
    deferred = IndexChange(
        index_name="Nifty 100",
        effective_from=dt.date(2020, 3, 27),
        announced_on=dt.date(2020, 2, 18),
        excluded=("ASHOKLEY", "IBULHSGFIN"),
        included=("ADANITRANS", "IDBI"),
        source="ind_prs18022020.pdf",
    )
    applied = IndexChange(
        index_name="Nifty 100",
        effective_from=dt.date(2020, 6, 26),
        announced_on=dt.date(2020, 6, 10),
        excluded=("ASHOKLEY", "IBULHSGFIN"),
        included=("ABBOTINDIA", "IGL"),
        source="ind_prs10062020.pdf",
    )
    assert drop_deferred([deferred, applied]) == [applied]


def test_the_accelerated_yes_bank_removal_survives_the_deferral() -> None:
    """The 16 March release took effect on 19 March, before the deferral.

    Dropping it along with the rest of March would be the opposite error, and
    just as invisible.
    """
    yes_bank = IndexChange(
        index_name="Nifty 100",
        effective_from=dt.date(2020, 3, 19),
        announced_on=dt.date(2020, 3, 16),
        excluded=("YESBANK",),
        included=("ADANITRANS",),
        source="ind_prs16032020.pdf",
    )
    assert drop_deferred([yes_bank]) == [yes_bank]


def test_an_unattributed_change_cannot_be_checked_and_is_refused() -> None:
    """Without a source there is no way to know whether it was withdrawn."""
    orphan = IndexChange(
        index_name="Nifty 100",
        effective_from=dt.date(2020, 3, 27),
        announced_on=None,
        excluded=("ASHOKLEY",),
        included=("IDBI",),
    )
    with pytest.raises(IndexChangeError, match="no source release"):
        drop_deferred([orphan])
