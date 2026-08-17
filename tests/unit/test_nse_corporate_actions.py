"""Tests for the NSE corporate-actions feed parser.

Every ``subject`` string below is **verbatim** from the live API. Inventing
them would only prove the regexes match the regexes.

The multiplier sign convention is the thing most worth pinning. A split and a
bonus move the price the same direction but are described completely
differently, and inverting either produces a number that is plausible, wrong,
and invisible once it reaches the price series.
"""

from __future__ import annotations

import datetime as dt

import pytest

from indian_equity_research.market.corporate_actions import ActionType
from indian_equity_research.market.nse_corporate_actions import (
    CorporateActionParseError,
    ParsedSubject,
    load_actions_json,
    parse_action_record,
    parse_subject,
)


def record(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "symbol": "TCS",
        "isin": "INE467B01029",
        "series": "EQ",
        "exDate": "23-Jan-2020",
        "faceVal": "1",
        "subject": " Interim Dividend - Rs 5 Per Share",
        "comp": "Tata Consultancy Services Limited",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# The sign convention
# ---------------------------------------------------------------------------


def test_a_face_value_split_halves_the_price() -> None:
    """Verbatim subject from SIS Limited, ex-date 15 January 2020."""
    parsed = parse_subject(
        "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share"
    )
    assert parsed.action_type is ActionType.SPLIT
    action = parse_action_record(
        record(
            subject="Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share"
        )
    )
    assert action is not None
    assert action.price_multiplier == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [(10, 1, 0.1), (10, 2, 0.2), (10, 5, 0.5), (5, 1, 0.2), (2, 1, 0.5)],
)
def test_split_multipliers_match_the_price_archive(old: int, new: int, expected: float) -> None:
    """These are the ratios actually observed in the bhavcopy.

    BAJFINANCE fell to x0.2 on 2016-09-08 and IRCTC to x0.2 on 2021-10-28,
    both documented 1:5 splits.
    """
    subject = f"Face Value Split (Sub-Division) - From Rs {old}/- Per Share To Rs {new}/- Per Share"
    action = parse_action_record(record(subject=subject))
    assert action is not None
    assert action.price_multiplier == pytest.approx(expected)


def test_a_one_for_one_bonus_halves_the_price() -> None:
    """Bonus a:b is a NEW shares for every b HELD -- not a share-count ratio.

    Reading "1:1" as "one becomes one" would give a multiplier of 1.0 and no
    adjustment at all.
    """
    action = parse_action_record(record(subject="Bonus 1:1"))
    assert action is not None
    assert action.action_type is ActionType.BONUS
    assert action.price_multiplier == pytest.approx(0.5)


def test_a_one_for_two_bonus_gives_two_thirds() -> None:
    """The origin of every x0.6667 in the price archive.

    ITC, LT, ONGC, MOTHERSON and IOC all show x0.667 moves that are 1:2
    bonuses. Treating the "1:2" as a split would give 0.5 and overstate the
    adjustment by a third.
    """
    action = parse_action_record(record(subject="Bonus 1:2"))
    assert action is not None
    assert action.price_multiplier == pytest.approx(2 / 3)


def test_a_consolidation_raises_the_price() -> None:
    """The reverse of a split, and the direction is taken from the numbers."""
    action = parse_action_record(
        record(subject="Face Value Consolidation - From Rs 1/- Per Share To Rs 10/- Per Share")
    )
    assert action is not None
    assert action.action_type is ActionType.CONSOLIDATION
    assert action.price_multiplier == pytest.approx(10.0)


def test_a_decimal_face_value_is_not_truncated() -> None:
    """Face values of 2.50 and 0.50 both occur on NSE.

    Integer division would turn a 5-to-2.5 split into 5-to-2.
    """
    action = parse_action_record(
        record(
            subject="Face Value Split (Sub-Division) - From Rs 5/- Per Share To Rs 2.50/- Per Share"
        )
    )
    assert action is not None
    assert action.price_multiplier == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Actions that must NOT produce a multiplier
# ---------------------------------------------------------------------------


def test_a_dividend_carries_an_amount_and_no_multiplier() -> None:
    """Dividend adjustment is a separate decision with its own conventions."""
    action = parse_action_record(record(subject=" Interim Dividend - Rs 5 Per Share"))
    assert action is not None
    assert action.action_type is ActionType.DIVIDEND
    assert action.amount == pytest.approx(5.0)
    assert action.price_multiplier is None


def test_a_demerger_claims_no_ratio_even_when_it_states_one() -> None:
    """A demerger's share-exchange ratio is not a price ratio.

    The value of the demerged entity is not in this feed. Using the exchange
    ratio as a price multiplier would be arithmetic applied to the wrong
    quantity -- and would look entirely reasonable in the output.
    """
    action = parse_action_record(
        record(subject="Demerger - Scheme of Arrangement in the ratio of 1:1")
    )
    assert action is not None
    assert action.action_type is ActionType.DEMERGER
    assert action.price_multiplier is None


def test_a_rights_issue_claims_no_ratio() -> None:
    """Correct only with the subscription price, which the feed omits."""
    action = parse_action_record(record(subject="Rights Issue 1:4"))
    assert action is not None
    assert action.action_type is ActionType.RIGHTS
    assert action.price_multiplier is None


@pytest.mark.parametrize(
    "subject",
    [
        "Annual General Meeting",
        "Buy Back",
        "Interest Payment",
        "Scheme of Amalgamation",
        "",
    ],
)
def test_an_unrecognised_subject_is_never_given_a_ratio(subject: str) -> None:
    """The safe direction. A subject we did not understand adjusts nothing."""
    parsed = parse_subject(subject)
    assert parsed.ratio_from is None
    assert parsed.ratio_to is None


def test_a_half_formed_ratio_is_refused_at_construction() -> None:
    with pytest.raises(CorporateActionParseError, match="half a ratio is not a ratio"):
        ParsedSubject(ActionType.SPLIT, ratio_from=1, ratio_to=None)


# ---------------------------------------------------------------------------
# Record-level filtering
# ---------------------------------------------------------------------------


def test_government_securities_are_dropped() -> None:
    """They dominate the feed by count and have no cash-equity price series."""
    assert parse_action_record(record(series="GS", symbol="717GS2028")) is None


def test_a_missing_ex_date_is_dropped_not_guessed() -> None:
    """Book-closure notices carry '-' where the ex-date would be."""
    assert parse_action_record(record(exDate="-")) is None
    assert parse_action_record(record(exDate="")) is None


def test_an_eq_row_without_an_isin_is_refused() -> None:
    """Symbols are reassigned after a delisting; ISIN is the stable key."""
    with pytest.raises(CorporateActionParseError, match="has no ISIN"):
        parse_action_record(record(isin=""))


def test_a_malformed_ex_date_is_refused() -> None:
    """Refuse a malformed ex-date.

    A date read wrongly moves a split by days and corrupts every return that
    spans it.
    """
    with pytest.raises(CorporateActionParseError, match="DD-Mon-YYYY"):
        parse_action_record(record(exDate="2020-01-23"))
    with pytest.raises(CorporateActionParseError, match="DD-Mon-YYYY"):
        parse_action_record(record(exDate="23-Xyz-2020"))


def test_the_source_carries_enough_to_re_check_by_hand() -> None:
    action = parse_action_record(record(), source="ca_2020Q1.json")
    assert action is not None
    assert "ca_2020Q1.json" in action.source
    assert "TCS" in action.source
    assert "Interim Dividend" in action.source


# ---------------------------------------------------------------------------
# Whole payloads
# ---------------------------------------------------------------------------

# Verbatim from the API for January 2020, trimmed to four rows.
PAYLOAD = """[
 {"comp":"GOVERNMENT OF INDIA","exDate":"06-Jan-2020","faceVal":"100",
  "isin":"IN0020170174","recDate":"07-Jan-2020","series":"GS",
  "subject":" Interest Payment","symbol":"717GS2028"},
 {"comp":"SIS LIMITED","exDate":"15-Jan-2020","faceVal":"5",
  "isin":"INE285J01010","recDate":"16-Jan-2020","series":"EQ",
  "subject":" Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 5/- Per Share",
  "symbol":"SIS"},
 {"comp":"Tata Consultancy Services Limited","exDate":"23-Jan-2020","faceVal":"1",
  "isin":"INE467B01029","recDate":"25-Jan-2020","series":"EQ",
  "subject":" Interim Dividend - Rs 5 Per Share","symbol":"TCS"},
 {"comp":"Suven Life Sciences Limited","exDate":"21-Jan-2020","faceVal":"1",
  "isin":"INE495B01038","recDate":"22-Jan-2020","series":"EQ",
  "subject":" Demerger","symbol":"SUVEN"}
]"""


def test_a_real_payload_yields_only_the_equity_rows_in_date_order() -> None:
    actions = load_actions_json(PAYLOAD, source="ca_2020Q1.json")
    assert len(actions) == 3, "the GS row must be dropped"
    assert [a.source.split(":")[1] for a in actions] == ["SIS", "SUVEN", "TCS"]
    assert [a.ex_date for a in actions] == sorted(a.ex_date for a in actions)
    split = next(a for a in actions if a.action_type is ActionType.SPLIT)
    assert split.ex_date == dt.date(2020, 1, 15)
    assert split.price_multiplier == pytest.approx(0.5)


def test_an_html_challenge_page_is_reported_as_such() -> None:
    """NSE returns HTML, not JSON, when cookies are missing.

    Without this the failure surfaces as a bare JSONDecodeError halfway
    through a download run, with no hint of the cause.
    """
    with pytest.raises(CorporateActionParseError, match="challenge page"):
        load_actions_json("<html><body>Access Denied</body></html>", source="ca.json")


def test_a_non_array_payload_is_refused() -> None:
    with pytest.raises(CorporateActionParseError, match="expected a JSON array"):
        load_actions_json('{"data": []}')


def test_a_non_object_item_is_refused() -> None:
    with pytest.raises(CorporateActionParseError, match="expected an object"):
        load_actions_json("[1, 2, 3]")


def test_an_empty_response_is_not_an_error() -> None:
    """Quiet quarters exist and must not be confused with a failed download."""
    assert load_actions_json("[]") == []


# ---------------------------------------------------------------------------
# "Re" is the singular of rupee
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        # All verbatim from the feed. Every one is a split down to a Re 1 face
        # value, and every one silently yielded no ratio until "Re" was accepted.
        ("Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share", 0.1),
        ("Face Value Split (Sub-Division) - From Rs 5/- Per Share To Re 1/- Per Share", 0.2),
        ("Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per Share", 0.5),
        ("Face Value Split From Rs 10 To Re 2", 0.2),
        ("Face Value Split (Sub-Division): From Rs 10/- Per Share To Re 1/- Per Share", 0.1),
        ("Face Value Split (Sub-Division) - From Rs10/- Per Share To Re 1/- Per Share", 0.1),
        ("Face Value Split (Sub-Division) - From Rs 10 Per Share To Re 1 Per Share", 0.1),
    ],
)
def test_a_split_to_a_one_rupee_face_value_is_read(subject: str, expected: float) -> None:
    """The single defect that hid 29 real splits.

    In Indian usage "Re" is the singular of rupee, used for exactly one. NSE
    therefore writes every split down to a Re 1 face value as "To Re 1/-".
    Accepting only "Rs" dropped the ratio from all of them -- NESTLEIND,
    TATASTEEL, DRREDDY, KOTAKBANK, EICHERMOT among others -- and each then
    appeared in the adjustment audit as an unexplained collapse rather than a
    documented corporate action.

    The failure direction is the dangerous one: a real split left unadjusted
    puts a fake -90% return into the price series.
    """
    action = parse_action_record(record(subject=subject))
    assert action is not None
    assert action.price_multiplier == pytest.approx(expected)


def test_the_rupee_abbreviation_does_not_loosen_the_match() -> None:
    """Accepting "Re" must not make the pattern fire on unrelated prose."""
    assert parse_subject("Reduction of capital").ratio_from is None
    assert parse_subject("Redemption of preference shares").ratio_from is None
