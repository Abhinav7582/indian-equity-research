# Retrospective — where this project actually is

**Written 2026-08-29**, after four trials and one blocked extension. Nothing
here is a new result; it is an audit of what has been done, what was considered
and closed, and what was never tried.

---

## 1. What has been built

| Layer | State |
|---|---|
| Price archive | 2015-01-01 to 2026-08-05, 2,861 sessions, ~5.3M rows |
| Corporate actions | NSE feed parsed, 855 ratio-bearing adjustments routed by ISIN-on-date |
| Adjustment audit | 487 large moves adjudicated, 0 outstanding |
| Cost model | Validated **to the paisa** against two real Groww contract notes and the funds ledger |
| Tax model | FIFO lots, 20% STCG / 12.5% LTCG, April–March years |
| Universe | Point-in-time **Nifty 100, Nifty 50, Nifty Next 50** — all reconstruct with **0 unapplied changes** |
| Engine | Event-driven, next-open fills, structural look-ahead guard |
| Statistics | Deflated Sharpe, PBO, purged walk-forward, Newey-West HAC |
| Tests | 890, ruff clean, mypy strict clean |

**Defects found and fixed along the way**, every one of which would have
silently corrupted a result:

`Re` vs `Rs` in split subjects (29 splits) · symbol-vs-ISIN matching · the
date-ranged endpoint omitting renamed companies · `&` breaking a URL · the
`EQ`-only filter deleting surveillance-series bars · feed actions keyed by the
vendor's *current* symbol (61 of 841 ratios) · compound `Bonus/Split` subjects
read as one action (11 rows) · abbreviated `Fv Splt Frm` subjects (14 splits) ·
purge sized by feature lookback instead of outcome horizon · DP charged per
**order** not per scrip.

---

## 2. What has been found

| Trial | What | Verdict |
|---|---|---|
| #1 | H4 regime overlay | **REJECTED** — 0 of 7 exit-and-re-enter cycles helped |
| #2 | H2 net outperformance, Nifty 100 top decile | **REJECTED** — 10.85% vs 17.13%; lost **3.32%/yr before any cost** |
| #3 | H1 decile monotonicity, Nifty 100 | **REJECTED** — IC +0.0378, t 1.47, D10 *negative* |
| #6 | Size tiers, Nifty 50 vs Next 50 | **SUGGESTIVE NEGATIVE** — +0.0414 vs +0.0360, t 1.57 |

Trials **#4 and #5 were never spent**: the Nifty 200 would not reconstruct.

**The one-line summary.** Across every universe this archive can reconstruct,
12-1 momentum produces a rank IC of **0.036 to 0.041** and a t-statistic between
**1.14 and 1.57**. Weak, consistent, and never distinguishable from noise.

---

## 3. The number that reframes it

Given the observed effect sizes and IC volatility, how long a sample would be
needed to clear the registered bar of **t ≥ 3.0**?

| Study | IC | t | n | **Months for t=3** | **Years** |
|---|---:|---:|---:|---:|---:|
| H1 Nifty 100 | 0.0378 | 1.47 | 70 | 292 | **24.3** |
| Nifty 50 | 0.0360 | 1.14 | 70 | 485 | **40.4** |
| Nifty Next 50 | 0.0414 | 1.57 | 70 | 256 | **21.3** |

*Approximate: back-solves the standard error from the reported HAC t and assumes
the effect size and IC volatility both persist.*

**The development window is 5.9 years.** Detecting an effect this size at this
bar needs **twenty to forty years** of monthly observations.

This does not mean the criteria are wrong. Harvey, Liu & Zhu's t ≥ 3.0 exists
precisely because a t of 2 across a multiple-tested literature means little. But
it does mean something important:

> **These hypotheses were registered with a bar that the available data cannot
> clear for an effect of this magnitude — whether or not the effect is real.**

That is worth knowing before spending more trials. A rejection here is
substantially a statement about sample size, not only about the market.

---

## 4. Routes considered and closed

| Route | Why closed |
|---|---|
| Nifty 200, parsing its own sections | 13 unapplied changes, size drifts to 208 |
| Nifty 200 as `Nifty 100 ∪ Nifty Midcap 100` | 14 unapplied, 31 of 38 snapshots off 200 |
| Start the study later (2018+, 2021+) | Still 3 unapplied even from 2021 — gaps are spread, not clustered |
| Backfill 2015–17 releases | Necessary but **not sufficient**, per the above |
| Trade D8/D9 instead of D10 | Selection — the rank was not registered in advance |
| Widen to Nifty 500 | 88 changes, 7 anomalies, far worse churn |

---

## 5. Routes never pursued — and the honest case for each

This is the part worth the retrospective.

### 5.1 We have only ever tested **one signal**

Everything has varied around it — universe, breadth, tiers, costs, window — but
the signal has been **raw 12-1 momentum** in every single trial.

**NSE's own investable momentum product does not use raw momentum.** The Nifty
200 Momentum 30 index is built on **risk-adjusted** momentum: 6-month and
12-month returns each divided by the volatility of daily returns. That is a
different signal, and it is the one an Indian retail investor can actually buy.

We have never tested it. This is the single largest untested variable in the
project.

### 5.2 Baseline **B3 was declared mandatory, never scored — and it changes the answer**

Amendment A1 (2026-08-04) added the Nifty 200 Momentum 30 index, net of 0.22%
and LTCG, as a **blocking baseline**: the strategy must beat an investable
momentum product, not merely an index fund.

H2 was scored against the Nifty 100 TRI only. **A1's requirement was not carried
out**, and the data had been sitting in
`data/raw/indices/nifty200_momentum30/` since before trial #2 ran.

Scoring it now, over **exactly** the H2 window of 2016-02-09 to 2021-12-31:

```
NIFTY 200 Momentum 30 TRI      25.38%  CAGR
Nifty 100 TRI                  17.36%
H2 strategy, gross             14.04%
H2 strategy, net of everything 10.85%
```

**Momentum did not have a bad window in India. It had an extraordinary one.**
The investable momentum index beat the Nifty 100 by **eight percentage points a
year** over precisely the period in which our momentum strategy lost to it by
six.

This is the most important thing in this document, and it inverts the reading of
trial #2. The registered conclusion — H2 rejected — stands, because the criteria
were about the Nifty 100 TRI and it failed them. But the *explanation* recorded
in `docs/h2_result.md`, that the signal simply did not work in this window, is
now doubtful. Something that is recognisably momentum returned 25.4% a year here.

The specification differences between ours and NSE's are numerous, and any of
them could carry the gap:

| | This project | NIFTY 200 Momentum 30 |
|---|---|---|
| Signal | raw 12-1 return | **risk-adjusted**: 6m and 12m returns ÷ volatility |
| Universe | Nifty 100 | Nifty 200 |
| Holdings | 10 | 30 |
| Rebalance | monthly | semi-annual |
| Weighting | equal | momentum-score weighted, capped |

**Every one of those is untested by us.** The one that stands out is the first:
we tested raw momentum, and the product that worked uses risk-adjusted momentum.

A1 was right to make B3 blocking. Not scoring it is the largest process failure
in this project so far — the amendment existed, the data existed, and the check
was simply not run.

### 5.3 The archive could be extended backwards

Bhavcopy exists well before 2015. Extending to ~2005 would roughly double the
sample — which section 3 says is exactly what the bar requires. It would not
reach 24 years, but it would move t from 1.47 toward ~2.1.

Cost: a large download and a re-run of the whole adjustment audit on unfamiliar
years. Real work, and the payoff is bounded by the arithmetic above.

### 5.4 The engine has never been validated end-to-end

Components are heavily tested. But the pipeline has never been asked to
reproduce a **known external result**.

We hold the Nifty 200 Momentum 30 TRI and NSE publishes its methodology. If the
engine can approximately reproduce that index's returns from bhavcopy, it
validates universe, adjustments, costs and execution in one test — the strongest
verification available, and it reads no returns as a *selection* device.

### 5.5 H3, H5, H6 remain untested

Registered on 2026-08-04 and never run. H5 (weekly vs monthly) is close to moot —
more turnover on an effect that did not survive monthly. H3 and H6 were
registered as *refinements to a working strategy*; with the base negative they
would have to create the edge.

### 5.6 Holding period was never varied

Every test uses a **one-month** forward return. Three- or six-month horizons are
a different question and were never asked.

### 5.7 The orders-per-exit sensitivity was never run

A7 requires every result to report 1, 1.5 and 3 sell orders per exit. Trial #2
reported only 1.0. Moot for a failed result, but the obligation stands.

---

## 6. What I would do, and why

**First, the two that cost nothing and might change the conclusion:**

1. **Score H2 against Baseline B3.** Completing a declared obligation, not a new
   trial. If the momentum ETF also underperformed the Nifty 100 TRI over
   2016–2021, then H2's failure says something quite different — it says the
   *entire momentum category* had a poor window, rather than that our
   implementation was bad.
2. **Record the power calculation in `HYPOTHESES.md`.** It changes how every
   past and future rejection should be read.

**Then the one substantive gap:**

3. **Test risk-adjusted momentum** — the signal NSE actually uses. New
   amendment, new trial, and the strongest remaining candidate for "we tested
   the wrong thing" rather than "there is nothing here."

**Then, optionally:**

4. **Route 3 hand-adjudication.** Honest data repair, but it serves a Nifty 200
   study that trial #6 has largely deprived of purpose. Worth doing for the
   archive's integrity, not for the answer.

**What I would not do:** spend trials #4 and #5 on the Nifty 200 bands. Trial #6
asked the same question on universes that reconstruct perfectly and answered it.

---

## 7. The honest position

Three hypotheses rejected and one suggestive negative is not a failed project;
it is four questions answered. The instrumentation is genuinely good and has
caught ten defects that would each have produced a confident, wrong number.

But three things should be said plainly:

**The investable momentum index returned 25.4% a year over the exact window our
momentum strategy returned 10.85%.** Whatever went wrong, "momentum did not work
in India in 2016–2021" is not it.

**The bar may be unreachable with this data.** Twenty to forty years, against
six available. Every rejection so far is partly a statement about sample size.

**One signal has been tested, not momentum.** Raw 12-1 is not what the
investable Indian momentum product uses, and the declared blocking baseline that
would have revealed this was never scored.

None of this undoes the rejections — they were scored against criteria fixed in
advance and they failed those criteria. But the question is considerably less
closed than four red verdicts make it look, and the reason is a check that was
declared mandatory two amendments before the first trial and never run.
