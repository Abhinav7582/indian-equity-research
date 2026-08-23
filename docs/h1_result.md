# H1 — rejected, and it explains H2 exactly

**Trial #3, run 2026-08-23.** Criteria fixed at registration on 2026-08-04.
Gross. Holdout untouched.

H2 asked whether a portfolio could capture the effect and answered no. H1 asks
the prior question — **is the effect there** — and the answer turns out to
explain the first one precisely.

---

## The result

**2016-02-09 to 2021-11-01 · 70 monthly rebalances · 94–101 securities ranked per date**

| Criterion | Observed | Required | |
|---|---|---|---|
| Mean rank IC | **+0.0378** | > 0 | PASS |
| Newey-West \|t\| on mean IC | **1.47** (naive 1.30, lag 3) | ≥ 3.0 | **FAIL** |
| Decile monotonicity | **+0.758** | ≥ 0.6 | PASS |
| D10−D1 positive in sub-periods | **2 of 5** | ≥ 3 of 5 | **FAIL** |

Two of four pass. H1 is rejected because **any** failure rejects.

---

## The decile pattern, which is the whole finding

Mean excess return over the Nifty 100 TRI, per month, gross:

```
D1    -0.599%  ----------------------------------
D2    -0.198%  -----------
D3    -0.441%  -------------------------
D4    -0.445%  -------------------------
D5    -0.425%  ------------------------
D6    -0.240%  --------------
D7    -0.320%  ------------------
D8    +0.376%  +++++++++++++++++++++
D9    +0.403%  +++++++++++++++++++++++
D10   -0.138%  --------          <-- the decile H2 traded
```

**The effect exists in a weak form and is absent from the very top.**

D8 and D9 are the only deciles that made money. D10 — the highest-momentum ten
names, the ones a concentrated portfolio must hold — lost.

Hit rates over 70 months make the same point without relying on means:

| Decile | Mean | Months positive |
|---|---:|---:|
| D10 | −0.138% | **32 / 70 (46%)** |
| D9 | +0.403% | 40 / 70 (57%) |
| D8 | +0.376% | 41 / 70 (59%) |
| D1 | −0.599% | 28 / 70 (40%) |

D10 is worse than a coin flip. **H2 bought it every month for 5.89 years and
lost 3.32% a year gross.** That is not a mystery any more.

---

## Why it failed the other criterion

The D10−D1 spread by non-overlapping sub-period, each block holding fourteen
rebalances:

```
2016-02 .. 2017-03    -0.427% / month
2017-04 .. 2018-05    +1.992%
2018-06 .. 2019-07    +3.645%
2019-08 .. 2020-09    -2.559%
2020-10 .. 2021-11    -0.346%
```

A spread swinging from +3.6% to −2.6% per month is not a stable effect. It was
positive in 43 of 70 individual months (61%) — the sign is more often right than
wrong — but the losing months are far larger than the winning ones.

That is also why the t-statistic is 1.47 rather than 3.0. The mean IC of +0.0378
is an ordinary magnitude for a real monthly factor; what is missing is
consistency, not size.

---

## A post-hoc check, recorded as a diagnostic and not as a result

Excluding the four COVID-window rebalances (March–June 2020):

```
monotonicity   +0.758  ->  +0.867
D10 - D1       +0.461% ->  +0.992% per month
D10             -0.138% ->  +0.03%
```

**This changes nothing and must not.** Choosing which months to exclude after
seeing the answer is precisely the selection the trial register exists to make
expensive. H1 stays rejected on the criteria as registered.

It is recorded for exactly one reason: even with COVID removed, **D10 (+0.03%)
still trails D8 (+0.42%) and D9 (+0.48%)**. The top-decile weakness is not a
COVID artefact — it survives the most favourable post-hoc treatment available.

---

## What this establishes

Within the **Nifty 100**, 12-1 momentum carries weak positive cross-sectional
information that is:

- not statistically distinguishable from noise at the registered bar,
- unstable across sub-periods, and
- **absent in the extreme top decile**, where a small concentrated portfolio has
  to live.

## What it does not establish

That momentum is absent from Indian equities. The Nifty 100 is the largest,
most-covered, most-arbitraged hundred names in the market. This result says
nothing about mid-caps — and NSE's own momentum index draws from the **Nifty
200**, not the Nifty 100.

---

## The trap, named so it can be avoided

The obvious reading is *"trade D8 and D9 instead of D10."*

That is the single most dangerous sentence produced by this project so far.

The rank at which the effect lives was **not registered in advance**. Picking it
now, from this output, is selection — the same mechanism that turns twenty
strategy ideas into one impressive-looking backtest. It would be legitimate only
as a new dated amendment written **before** the run, and it would be trial #4,
raising the Deflated Sharpe bar for anything that eventually passes.

The honest position: D8/D9 outperforming D10 is a **hypothesis suggested by this
data**, not a finding from it, and it cannot be tested on the same data that
suggested it without the result meaning considerably less.

---

## Consequences

**Amendment A1** named H3, H4 and H6 as the only plausible sources of edge over a
0.22% momentum ETF — resting on the assumption that momentum itself worked.

```
H4  rejected  (trial #1, regime overlay)
H2  rejected  (trial #2, net outperformance)
H1  rejected  (trial #3, the effect itself)
```

All three of A1's candidate sources were refinements to a foundation. **The
foundation has not held.**

**H3 (quality filter) and H6 (governance exclusions)** were registered as
improvements to a working strategy. They would now have to create the edge, not
refine it — a much stronger claim than either was written to make. Testing them
is still legitimate; expecting them to rescue momentum in the Nifty 100 is not.

**H5 (monthly versus weekly rebalancing)** is close to moot. Weekly means more
turnover, more charges, and more short-term capital gains tax on an effect that
did not survive monthly.

---

## Reproducing it

```bash
uv run python scripts/run_h1.py
```

Gross by construction. Window ends 2021-12-31 and the script accepts no later
one, so the holdout is not reachable from here.
