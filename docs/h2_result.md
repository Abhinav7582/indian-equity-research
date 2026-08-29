# H2 — rejected, and not for the reason this project prepared for

> **ADDENDUM, 2026-08-29 — the mechanism section below is now doubtful.**
> Baseline B3, which Amendment A1 declared mandatory on 2026-08-04, was never
> scored. Run since: the **NIFTY 200 Momentum 30 index returned 25.10% a year
> over exactly this window**, against the Nifty 100 TRI's 17.13% and this
> strategy's 10.85%. ₹3,00,000 would have become ₹11,22,652 rather than
> ₹5,50,426.
>
> Momentum did not have a poor window in India in 2016–2021. It had an
> exceptional one. The rejection stands — the criteria named the Nifty 100 TRI
> and it failed them — but "the signal lost" is very unlikely to be the right
> reading. The likelier reading is that **we tested a different signal from the
> one that worked**: raw 12-1 return, where NSE's index uses *risk-adjusted*
> momentum. See `docs/retrospective_2026_08.md` and the trial #2 addendum in
> `HYPOTHESES.md`.

**Trial #2, run 2026-08-23.** Specification fixed in advance by Amendment A9;
criteria fixed at registration on 2026-08-04. The declared holdout
(2022-01-01 to 2025-12-31) was **not touched**.

---

## The result

Top decile of 12-1 momentum in the point-in-time Nifty 100. Ten equal-weighted
names, rebalanced on the first session of each month, decided on the previous
close and filled at the next open, on ₹3,00,000.

**2016-02-09 to 2021-12-31 · 5.89 years · 71 rebalances · 70 monthly observations**

| | Strategy | Nifty 100 TRI |
|---|---:|---:|
| Gross CAGR, before any cost | **14.04%** | 17.36% |
| After charges | 12.13% | — |
| After charges and tax | **10.85%** | 17.13% *(net of 0.20% expense ratio)* |
| Maximum drawdown | 47.79% | 37.94% |
| Volatility | 23.23% | 17.52% |
| Final value | ₹5,50,426 | ₹7,61,607 |

₹3,00,000 in a Nifty 100 index fund would have ended **₹2,11,181 ahead** of the
strategy, having required no work and no decisions.

---

## The decomposition, which is the actual finding

```
Strategy gross vs raw TRI      -3.32%   annualised, before a single rupee of cost
  charges                      -1.92%
  capital gains tax            -1.28%
                               ------
Net excess                     -6.28%
```

**The signal lost before it paid anything.**

That is worth sitting with, because this project spent most of its effort
preparing for the opposite conclusion. Amendments A1, A6, A7 and A8 are all
about costs. The cost model was validated to the paisa against real Groww
contract notes. The breadth frontier was computed to find the cheapest workable
book. A whole amendment exists to fix the DP charging unit.

All of that was correct, and **none of it was the deciding factor**. Costs took
a 3.32% annual deficit and made it 6.28%. They doubled the loss; they did not
create it.

Had the cost work been skipped, the conclusion would have been the same. Had
the strategy been costless, it would still have lost to a Nifty 100 index fund
by more than three percentage points a year.

---

## Criteria, as declared

H2 is rejected if **any** criterion fails.

| Criterion | Observed | Required | |
|---|---|---|---|
| Net return exceeds Nifty 100 TRI | 10.85% vs 17.13% | strategy > benchmark | **FAIL** |
| Newey-West \|t\| on net excess | 0.98 | ≥ 3.0 | **FAIL** |
| Max drawdown vs benchmark | 1.26× | ≤ 1.3× | PASS |
| DSR, PBO, 1.5× cost stress, 40% concentration | — | — | moot |

The last four ask whether a positive excess return is real. This one is
negative, so none of them can change the verdict.

**The t-statistic cuts both ways and should not be over-read.** 0.98 means the
underperformance is *also* not statistically significant. Over 70 monthly
observations the difference is indistinguishable from noise. The criteria
require |t| ≥ 3.0 for a positive claim — deliberately strict, following Harvey,
Liu & Zhu (2016) — and this is nowhere near it in either direction.

---

## What was ruled out before accepting the number

**Cash drag.** With ₹30,000 positions and whole shares, a name trading above
₹30,000 cannot be bought at all — SHREECEM reached ₹23,300 in this window.
Measured: the book held a mean of **1.96%** cash. Not the cause.

**Unadjusted corporate actions.** `residual_moves()` reported 21 surviving large
moves. Every one was checked. All are real events — YESBANK's moratorium week,
the PNB and Canara Bank recapitalisation announcement of 2017-10-25, Vodafone
Idea, RCom, the Zee-Sony merger announcement, the March 2020 crash and bounce,
the Crompton Greaves and Aditya Birla Nuvo demergers, which carry no
computable price ratio.

**One genuine defect was found and fixed** before the reported run: for one
quarter, October 2016 to February 2017, NSE filed splits in an abbreviated form
— `Fv Splt Frm Rs 10 To Rs 2` — that matched neither the keyword list nor the
ratio pattern. Fourteen real splits carried no multiplier. JSWSTEEL had been
recovered by hand in the audit; SOLARINDS, KARURVYSYA, KPRMILL and CAPLIPOINT
had not, because they traded below the audit's liquidity floor. It surfaced as
an unexplained `x0.2001` in the output, not from any check on the inputs.

Fixing it did not change the result.

**Selection.** The picks were inspected at four rebalances and are what 12-1
momentum should produce: metals in early 2017 (Vedanta, Hindalco, Hindustan
Zinc, Tata Steel, JSW), quality and IT in early 2019 (TCS, Tech Mahindra,
Infosys, HUL, Britannia), Adani and Tata Motors in late 2021. The signal was
computed correctly; it simply did not pay.

---

## What this establishes, and what it does not

**It rejects this specification.** Top decile, ten names, monthly, on the Nifty
100, over this window.

**It does not establish that momentum is absent in Indian equities.** Three
explanations are plausible and none is tested. Each would require a new dated
amendment and would count as a new trial:

1. **The universe may be too large-cap.** Published Indian momentum results
   concentrate in mid-caps. The Nifty 100 is the top hundred by size — the most
   researched, most arbitraged segment of the market. NSE's own momentum index
   draws from the Nifty 200, not the Nifty 100.
2. **The window may be unkind.** 2018-2020 was poor for momentum globally, and
   it is a third of this sample.
3. **Ten names may be too few.** 23.23% volatility against the index's 17.52%
   is the price of concentration. A9 chose ten for continuity with H1 and for
   cost, not because ten best expresses a cross-sectional effect.

Note what these three have in common: each is a reason to run **another** trial,
and each would raise the Deflated Sharpe bar for anything that eventually
passes. That is the cost of a rejection, and it is the reason the trial register
exists.

---

## Consequences

**Amendment A1** named H3, H4 and H6 as the only plausible sources of edge over
a 0.22% momentum ETF. H4 is rejected. H2's base case is now negative *before
costs*, so H3 (a quality filter) and H6 (governance exclusions) are no longer
refinements to a working strategy — they would have to create the edge rather
than improve it. That is a much stronger claim than either was registered to
make.

**H1** is not refuted. It concerns cross-sectional rank correlation, not one
portfolio against an index. But decile 10 underperforming the index gross for
5.89 years is not what a strong momentum effect looks like, and H1 should now
be approached expecting a weak result rather than a confirmation.

**Amendment A6**'s abandonment rule is not yet triggered — it governs deployed
capital, and nothing has been deployed. Nothing should be.

---

## Reproducing it

```bash
uv run python scripts/run_h2.py
```

Reads no holdout data and refuses to, unless explicitly permitted. Every
distinct configuration run through it is a trial and belongs in the register in
`HYPOTHESES.md`, including any that is run and then abandoned.
