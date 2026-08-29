# Phase 4 — closed. The answer to the question this project was built to ask.

**2026-08-29.** Seven trials registered, five spent, holdout never touched.

---

## The question

Registered 2026-08-04, before any market data was downloaded:

> Does a disciplined, systematic momentum process on Indian cash equities beat a
> Nifty 100 index fund, after every cost and tax, on ₹3,00,000?

## The answer

**No, and not marginally.**

| Trial | What | Result |
|---|---|---|
| #1 | H4, regime overlay | REJECTED — 0 of 7 exit-and-re-enter cycles helped |
| #2 | H2, net outperformance | REJECTED — 10.85% vs 17.13% |
| #3 | H1, decile monotonicity | REJECTED — IC +0.0378, t 1.47 |
| #6 | Size tiers | SUGGESTIVE NEGATIVE — one tier down moved IC by 0.005 |
| #7 | NSE's own signal | NOT SUPPORTED — risk-adjusted scored *worse* |

Every cross-sectional measurement this archive can produce:

```
raw 12-1, Nifty 100        IC +0.0378   t 1.47
raw 12-1, Nifty 50         IC +0.0360   t 1.14
raw 12-1, Next 50          IC +0.0414   t 1.57
risk-adjusted, Nifty 100   IC +0.0239   t 1.04
```

**Two signals, three universes, every cost treatment.** Nothing above t = 1.57
against a registered bar of 3.0.

---

## Three things that stop this being a simple negative

**1. Momentum worked in India in this window — for someone else.** The NIFTY 200
Momentum 30 index returned **25.10% a year** over exactly the window our
strategy returned 10.85%, and beat its own parent universe by **+7.88% a year**.
The effect was there. We did not capture it.

**2. Of four candidate explanations, two are ruled out and one is untestable
here.**

| Candidate | Status |
|---|---|
| Signal — raw vs risk-adjusted | Ruled out, trial #7 |
| Universe — Nifty 100 vs 200 | Largely ruled out, trial #6 |
| Cadence — monthly vs semi-annual | Untested |
| **Concentration and weighting** | **Untestable** — needs free-float market cap this project does not hold, and A7's ₹3L breadth budget would constrain it heavily even with the data |

**3. The bar may be unreachable with six years of data.** The observed effect
sizes need **21 to 40 years** of monthly observations to clear t ≥ 3.0. The
development window is 5.9. Every rejection above is partly a statement about
sample size rather than only about the market.

---

## What was learned that outlasts the answer

Ten defects were found, each of which would have produced a confident wrong
number:

`Re` vs `Rs` in split subjects (29 splits) · symbol-vs-ISIN matching · the
date-ranged endpoint omitting renamed companies · `&` breaking a URL · the
`EQ`-only filter deleting surveillance-series bars (3 months of TIDEWATER) ·
feed actions keyed by the vendor's *current* symbol (61 of 841 ratios) ·
compound `Bonus/Split` subjects read as one action (11 rows) · abbreviated
`Fv Splt Frm` subjects (14 splits) · purge sized by feature lookback instead of
outcome horizon · DP charged per **order** not per scrip.

And one process failure worth more than any of them: **Amendment A1 declared a
mandatory baseline on 2026-08-04 and it was never scored until 2026-08-29.** The
data was on disk the whole time. Nothing in the pipeline checked that a declared
comparison had been made. A guard now refuses to produce a result with a
registered baseline missing — but the lesson is that *rules without enforcement
decay silently*, and this project had gone twenty-five days on one.

---

## The three hypotheses never tested

**H3 — quality filter** and **H6 — governance exclusions** were registered as
*refinements to a working strategy*. With the base case negative before costs,
they would have to **create** the edge rather than improve it — a far stronger
claim than either was written to make. They remain registered and untested.
Testing them is legitimate; expecting them to rescue momentum on the Nifty 100
is not.

**H5 — monthly versus weekly rebalancing** is close to moot. Weekly means more
turnover, more charges, and more short-term capital gains tax on an effect that
did not survive monthly.

None is withdrawn. All three are simply not worth a trial at current odds, and
each would raise the Deflated Sharpe bar for anything after it.

---

## What happens to the ₹3,00,000

**Nothing.** Amendment A6 caps research capital at ₹3,00,000 and requires two
full years of paper trading before any deployment. No strategy has passed
development, so nothing reaches paper trading, so nothing is deployed.

That is the system working. The capital was never at risk because the process
never let it get that far.

---

## Where the money actually is

```
₹3,00,000     research capital, nothing deployed
₹65,40,272    the actual balance sheet, no declared policy
```

One percentage point across the balance sheet is **₹65,403 a year**. A
successful strategy on the research capital, had one existed, would have been
worth roughly **₹15,000**.

Phase 4 spent nine months answering a question worth ₹15,000 a year and
answering it honestly. Phase 5 addresses the number that is four times larger
and currently has no policy at all.

**Phase 4 is closed.**
