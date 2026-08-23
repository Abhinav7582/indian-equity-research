# Three defects in the adjusted price series

**Found 2026-08-22**, in the first week after `backtest/prices.py` began serving
bars to the backtest engine. All three were silent: no exception, no warning,
plausible-looking prices.

They are recorded together because they share a cause. Each one was a check on
an **input** — is the feed complete, is the register marked, does the ratio
parse — and each input was in fact fine. What was wrong was the **output**, and
only an output check could see it.

---

## How they were found

`residual_moves()` looks at the finished bars and reports any day-over-day move
beyond 35% that survived adjustment. On the first real run it reported:

```
2021-10-18  TIDEWATER  x0.1123
```

The first diagnosis of that line was **wrong**, and it is worth writing down
because the wrong answer was more plausible than the right one. It was read as
a missed split in a thinly traded name: TIDEWATER traded ₹4.03 crore that day,
below the audit's ₹20 crore liquidity filter, and its corporate actions sit in
the feed under the post-rename symbol `VEEDOL`. Two clean reasons, both true
statements about the data, and neither of them the cause.

The actual sequence, from the archive:

```
2021-07-14  TIDEWATER  EQ  15,882.60   last session on EQ
2021-07-15  TIDEWATER  BE  15,088.50   moved to surveillance
2021-07-26  TIDEWATER  BE   3,127.15   ex bonus 1:1 + split, x0.2100
2021-08-18  TIDEWATER  BE   1,829.50   a real decline, uninterrupted
2021-10-14  TIDEWATER  BE   1,799.00   last session on BE
2021-10-18  TIDEWATER  EQ   1,784.40   back on EQ
```

TIDEWATER never stopped trading. It spent three months on the trade-for-trade
series, the loader kept only `SERIES == "EQ"`, and 2021-07-14 was welded
directly onto 2021-10-18 — across a documented corporate action *and* a genuine
43% fall. One fabricated −89% day, on a security that had done nothing of the
sort.

---

## D1 — the settlement-series filter deleted bars

**What it did.** Kept `EQ` only. `BE` and `BZ` are the same share on the same
ISIN under compulsory-delivery settlement; a security is moved there under
surveillance and moved back later.

**Why it is worse than missing data.** The dropped sessions did not become
gaps to be handled. They became *absent*, so the sessions on either side became
adjacent, and every return computed across the hole describes a price path no
holder experienced.

**Fixed by** `CASH_EQUITY_SERIES = {"EQ", "BE", "BZ"}`.

`SM` and `ST` are deliberately excluded — the SME platform is a separate board
and no Nifty 100 constituent trades there. `GB`/`GS`/`TB` are government
securities and `N1`–`NE` debt.

---

## D2 — documented adjustments were keyed by the wrong symbol

**What it did.** NSE's corporate-actions API reports each security's **current**
symbol on every row, however old. Downloading the Q4-2015 window returns Cadila
Healthcare's October 2015 split labelled `ZYDUSLIFE` — a name that first traded
in March 2022. Keyed by symbol, the adjustment lands on an empty bucket.

**Blast radius, measured against the 2015–2026 archive:**

```
841 ratio-bearing actions in the feed
780 landed on a symbol trading on the ex-date
 61 did not                                    7.2%
```

Among the 61: MOTHERSUMI's three bonuses (2015, 2017, 2018), MCDOWELL-N,
MINDAIND, PHILIPCARB, TITAGARH, WELSPUNLIV, EPL. Every one an Indian large- or
mid-cap that a Nifty 100 universe must contain, and every one a rename — which
is precisely the population a survivorship-free universe exists to include.

**Fixed by** `route_adjustments()`, which resolves each action to the ticker
that held its ISIN on the ex-date, using bhavcopy's own `ISIN` column. Symbol
match is retained as a fallback, because the ISIN itself changes across a split
— the two keys fail in opposite directions, so the union is used.

After the fix, 838 of 847 adjustments place. The remaining 9 are pre-2015
(`ASHOKLEY` 2011, `ZEEL` 2010 and 2014, `SINTEX` 2010, `TMPV` 2011) with no
bars to adjust, and are reported rather than dropped.

**Ambiguity is never resolved by preference.** Two live tickers on one ISIN
means an assumption is wrong somewhere, and choosing one would hide it.

---

## D3 — a compound subject was read as one action

Exposed by fixing D2. Once feed actions reached the right symbol, four of them
collided with hand-verified register entries for the same day and **both**
applied. A x0.25 split became x0.125, turning a real 76% fall into a fictitious
94% gain.

That collision was not a new bug — it was the old one surfacing. The six
hand-verified entries exist *because* the feed rows were misrouted; a person
recovered by hand what D2 had thrown away. Fixing the routing made the manual
workaround a duplicate.

**Resolved by precedence:** a verdict is one person's account of a whole day's
move, checked against the move itself, so it **replaces** the feed's account of
that day rather than compounding with it. Two genuinely separate feed actions on
one date still compound — VEEDOL's 2021-07-26 bonus and split are both real, and
the price took x0.5 × x0.4.

Comparing the two accounts then revealed the third defect:

```
2016-03-16 TIDEWATER  feed x0.5000  superseded by verified x0.2500   <-- DISAGREE
```

The subject is `Bonus 1:1/Face Value Split (Sub-Division) - From Rs 10/- Per
Share To Rs 5/- Per Share` — **two actions in one string**. The parser read the
split and stopped. Eleven feed rows in the archive have this shape, including:

| Ex-date | Symbol | Parsed | Correct |
|---|---|---:|---:|
| 2015-03-19 | TECHM | x0.50 | **x0.25** |
| 2016-03-16 | VEEDOL (TIDEWATER) | x0.50 | **x0.25** |
| 2016-09-08 | BAJFINANCE | x0.20 | **x0.10** |

`BAJFINANCE` is the one that stings: the module docstring in
`nse_corporate_actions.py` cited it as a worked example of a correctly handled
split, at x0.2000. The observed move was x0.1021. The example was wrong in the
file whose job was to be right about exactly this. It has been corrected in
place, with the error kept alongside it.

**Fixed by** `ActionType.BONUS_AND_SPLIT` and a bonus-ratio read anchored on the
word "bonus" rather than searched across the whole subject.

With D3 fixed, all four superseded pairs agree — the parser now reaches, from
the document, the same numbers a person reached from the price.

---

## What survives

Eight residuals remain across the securities checked, and all eight are real:

```
2018-09-21  DHFL        x0.5742   IL&FS contagion
2018-09-28  INFIBEAM    x0.2917   the September 2018 collapse
2019-06-18  JETAIRWAYS  x0.5921   grounding
2019-06-20  JETAIRWAYS  x1.8988
2020-03-06  YESBANK     x0.4389   RBI moratorium
2020-03-11  YESBANK     x1.3553
2020-03-16  YESBANK     x1.4521
2020-03-17  YESBANK     x1.5809
```

They are reported, not adjusted. Adjusting on suspicion would erase them, and
that is the failure the entire audit exists to prevent.

---

## The general lesson, stated plainly

The audit was complete. The feed was complete. The register was fully marked.
Every input check passed, and the prices were still wrong — because the defects
lived in places no input check was looking: a settlement-series code, a symbol
rewritten by the vendor, a slash in a sentence.

An output check cannot be enumerated in advance, which is the whole of its
value. `residual_moves()` is therefore not optional, and `strict=True` — which
escalates a residual to a refusal — is correct for any run whose result will be
entered in the trial register.

None of this changes a hypothesis outcome, because no hypothesis has yet been
tested on these bars. That is luck, not process. It is also the last moment at
which it could have been.
