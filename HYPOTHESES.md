# Pre-Registered Research Hypotheses

**Registered: 2026-08-04**
**Registered by: Abhinav Singh**
**Status of every hypothesis at registration: `NOT_TESTED`**

---

## Why this file exists, and why it exists *now*

This file was written **before any market data was downloaded, examined or
plotted**. That ordering is the entire point.

With roughly 20 years of Indian equity history and a universe of a few hundred
stocks, the number of *effectively independent* observations is small — on the
order of 200 monthly periods. The number of strategy variants a motivated
person can try is unbounded. Under those conditions, searching until something
looks good is guaranteed to produce something that looks good, and almost
guaranteed to produce something that is not real.

Three findings govern how this project reads any result, including its own:

- Harvey, Liu & Zhu, *"…and the Cross-Section of Expected Returns"*, **Review
  of Financial Studies 29(1), 2016** — after accounting for the multiple
  testing implicit in decades of collective search, a t-statistic of **3.0**,
  not 2.0, is the appropriate minimum bar for a newly claimed factor.
- Hou, Xue & Zhang, *"Replicating Anomalies"*, **RFS 33(5), 2020** — of 452
  replicated anomalies, roughly **65% fail** to clear |t| ≥ 1.96 under
  consistent methodology.
- McLean & Pontiff, *"Does Academic Research Destroy Stock Return
  Predictability?"*, **Journal of Finance 71(1), 2016** — predictor returns
  decay by roughly **26%** out-of-sample and **58%** after publication.

Writing the criteria down first is the cheapest available defence against
all three.

### Rules binding on the author

1. **Criteria must not be rewritten after observing results.** If a
   hypothesis fails, it is recorded as failed. Adjusting the threshold,
   the window, the universe or the metric *after* seeing the outcome converts
   this document from a safeguard into decoration.
2. **Every configuration tested is logged**, including abandoned ones. The
   Deflated Sharpe Ratio requires an honest trial count; an undercounted
   trial register makes the statistic meaningless.
3. **Amendments are additive and dated.** To change a hypothesis, append a
   new dated entry stating what changed and why, before running the test.
   Never edit history in place.
4. **A rejected hypothesis is a successful experiment.** The purpose of this
   project is to find out what is true, not to find a strategy.
5. **No result may be recorded here that was not actually produced by a run
   of the backtester**, with the commit hash and data snapshot identifier
   recorded alongside it.

### Definitions fixed at registration

| Term | Definition |
|---|---|
| **Universe** | Point-in-time constituents of the **Nifty 100** as of each rebalance date, reconstructed from index rebalance announcements. Never today's membership applied to history. |
| **Benchmark** | **Nifty 100 Total Return Index (TRI)**. Price-return comparisons are not acceptable; they overstate relative performance by the dividend yield. |
| **Costs** | Brokerage, GST, STT, stamp duty, exchange transaction charges, SEBI turnover fees, IPFT, DP charges, modelled spread and modelled slippage — itemised, never a flat basis-point assumption. |
| **Net return** | After every cost above. Gross results are never reported alone. |
| **Delisted securities** | Retained in the historical universe with an explicit terminal return. Silent removal is survivorship bias. |
| **Point-in-time** | A feature on date *T* may use only data whose `published_at` ≤ *T*. |
| **Holdout** | 2022-01-01 to 2025-12-31. Touched **exactly once**, at the end. |

---

## H1 — Momentum monotonicity

**Statement.** Within the point-in-time Nifty 100 universe, deciles formed on
12-1 momentum (the trailing twelve-month total return excluding the most
recent month) exhibit a **monotonic** relationship with forward one-month
excess returns, with decile 10 outperforming decile 1.

**Null hypothesis (H1₀).** There is no monotonic relationship between 12-1
momentum decile and forward one-month excess return.

**Rationale.** Momentum is one of the few anomalies to survive systematic
replication (Hou-Xue-Zhang 2020) after most did not. Published Indian studies
report a momentum effect that is present and often stronger than in developed
markets, with profits concentrated in the **long** leg — which matters because
this project cannot short. NSE publishes a live strategy index built on the
same idea. The most recent month is skipped because short-horizon reversal
runs in the opposite direction and would contaminate the signal.

**Primary metric.** Spearman rank information coefficient between momentum
score and forward one-month excess return, averaged across rebalance dates.

**Secondary metrics.** Decile mean excess returns; decile 10 minus decile 1
spread; monotonicity measured as the Spearman correlation between decile index
and decile mean return.

**Data required.** Adjusted daily prices (≥15 years, including delisted
securities); corporate actions; point-in-time index membership; trading
calendar; Nifty 100 TRI.

**Rejection criteria — H1 is rejected if any of the following holds.**
- Mean rank IC ≤ 0.
- Newey-West-adjusted |t| on the mean rank IC < 3.0.
- Decile monotonicity (Spearman rank correlation between decile index and
  decile mean return) < 0.6.
- The decile 10 − decile 1 spread is not positive in at least 3 of 5
  non-overlapping sub-periods.

**Note on scope.** H1 is a statement about **gross cross-sectional structure
only**. It says nothing about whether the effect is tradeable. That is H2.

**Status:** `REJECTED` on the development window (trial #3, 2026-08-23).
Mean rank IC **+0.0378** (passes) but Newey-West **|t| = 1.47** against a
required 3.0, and the D10−D1 spread was positive in only **2 of 5**
non-overlapping sub-periods. Monotonicity **+0.758** passes. The decisive
detail: **decile 10 returned −0.138% per month** while D8 and D9 returned
+0.376% and +0.403% — the effect, such as it is, is absent from the very top of
the distribution, which is where H2's portfolio lived.
**Registered:** 2026-08-04

---

## H2 — Net benchmark outperformance

**Statement.** A monthly-rebalanced, long-only portfolio of the highest-ranked
momentum names in the point-in-time Nifty 100 outperforms the Nifty 100 Total
Return Index **after every modelled cost**.

**Null hypothesis (H2₀).** The strategy does not outperform the Nifty 100 TRI
net of costs.

**Rationale.** A statistically real cross-sectional effect (H1) and a
profitable strategy are different claims. Novy-Marx & Velikov (*RFS* 29(1),
2016) show that transaction costs eliminate a large fraction of documented
anomalies outright. Indian costs are heavier than the US equivalents on the
dimensions that matter here: STT is charged on **both** legs of a delivery
trade, and DP charges are a **flat rupee amount per sell order**
(*corrected by Amendment A8; registered as "per sell scrip", which is
Zerodha's rule and not the one this account is charged under*), which
penalises small positions specifically. **H2 is the hypothesis that decides
whether this project has a reason to continue.**

**Primary metric.** Annualised net excess return over the Nifty 100 TRI, with
a Newey-West-adjusted t-statistic.

**Secondary metrics.** Net CAGR; net Sharpe; maximum drawdown; Calmar; annual
one-way turnover; total costs in rupees; Deflated Sharpe Ratio; Probability of
Backtest Overfitting.

**Data required.** Everything in H1, plus the full itemised cost schedule
versioned by effective date, plus a spread/slippage model.

**Rejection criteria — H2 is rejected if any of the following holds.**
- Net annualised return ≤ Nifty 100 TRI over the holdout period.
- Newey-West |t| on net excess return < 3.0.
- Deflated Sharpe Ratio p-value ≥ 0.05 using the honest trial count.
- Probability of Backtest Overfitting ≥ 0.5.
- Net excess return turns negative under a 1.5× transaction-cost stress.
- Any single 12-month sub-period contributes more than 40% of cumulative
  excess return.
- Maximum drawdown exceeds 1.3× the benchmark's over the same window.

**Status:** `REJECTED` on the development window (trial #2, 2026-08-23).
Net CAGR **10.85%** against **17.13%** for the Nifty 100 TRI net of a 0.20%
expense ratio, over 2016-02-09 to 2021-12-31. The signal lost by **3.32%
annualised before any cost**; charges and tax took the deficit to 6.28%.
The declared holdout was **not** touched — a strategy that fails in development
does not get to spend it.
**Registered:** 2026-08-04

---

## H3 — Quality filter

**Statement.** Applying a pre-declared quality **eligibility filter** to the
momentum universe reduces maximum drawdown without materially reducing net
CAGR, where "materially" means a reduction greater than 1.5 percentage points
annualised.

**Null hypothesis (H3₀).** The quality filter does not improve risk-adjusted
outcomes.

**Rationale.** Profitability and quality measures have reasonable long-run
support (Novy-Marx, *JFE* 108(1), 2013; Asness, Frazzini & Pedersen,
*Review of Accounting Studies* 24, 2019). The expectation here is **not** that
quality adds alpha. It is that quality removes the financial-distress tail
that concentrated portfolios cannot survive. The filter is therefore evaluated
on drawdown, not on return.

**Exact filter definition is intentionally DEFERRED** to the research-design
phase, because it depends on which fundamental fields prove reliably available
point-in-time. It **must be declared in a dated amendment to this file before
H3 is tested**, and must be a small number of pre-specified, economically
motivated thresholds rather than an optimised screen.

**Primary metric.** Maximum drawdown of the filtered strategy versus the
unfiltered strategy, on identical dates with identical costs.

**Secondary metrics.** Net CAGR delta; Calmar ratio; number of names excluded;
95th-percentile worst stock-month within the portfolio.

**Data required.** Point-in-time quarterly financial statements with a
`published_at` timestamp; restatement history preserved rather than
overwritten.

**Rejection criteria — H3 is rejected if any of the following holds.**
- Maximum drawdown is not reduced by at least 2 percentage points absolute.
- Net CAGR falls by more than 1.5 percentage points annualised.
- The improvement is not present in at least 2 of 3 distinct drawdown episodes.
- The filter excludes more than 60% of the universe (a filter that aggressive
  is a different strategy, not a filter).

**Status:** `NOT_TESTED`
**Registered:** 2026-08-04

---

## H4 — Regime overlay

**Statement.** A simple, pre-declared market-regime overlay reduces the
strategy's maximum drawdown by at least **20% relative** to the unfiltered
strategy.

**Null hypothesis (H4₀).** The regime overlay does not materially reduce
maximum drawdown.

**Rationale.** Momentum strategies suffer rare, violent drawdowns, typically
at market rebounds from panic conditions (Daniel & Moskowitz, *"Momentum
Crashes"*, *JFE* 122(2), 2016). Trend and volatility-based exposure overlays
have moderate evidence for reducing those episodes, at the well-documented
cost of underperforming in V-shaped recoveries. The overlay is judged on
drawdown reduction, and the return cost is measured and accepted or rejected
explicitly rather than hidden.

**Exact regime definition is intentionally DEFERRED** to the research-design
phase and **must be declared in a dated amendment to this file before H4 is
tested.** Constraints fixed now, to prevent the definition from being tuned
into existence:

- At most **two** input variables.
- Each variable must be observable **at the close of the decision date** with
  no revision (index level versus its own moving average, and a volatility
  measure, both qualify; anything revised later does not).
- Thresholds must be **fixed constants or unconditional historical
  percentiles**, never values fitted to the sample.
- The rule must be expressible in one sentence.

**Primary metric.** Maximum drawdown of the overlaid strategy versus the
unoverlaid strategy.

**Secondary metrics.** Net CAGR delta; Calmar; time in the de-risked state;
number of regime switches per year; performance during recovery months
specifically.

**Data required.** Benchmark index history; a volatility measure with full
history; the strategy's own daily net returns.

**Rejection criteria — H4 is rejected if any of the following holds.**
- Relative reduction in maximum drawdown < 20%.
- Net CAGR falls by more than 2 percentage points annualised.
- More than 8 regime switches per year on average (excessive whipsaw).
- The benefit is confined to a single historical episode.

**Status:** `REJECTED` (2026-08-06, trial #1)
**Registered:** 2026-08-04
**Result:** Rejected in both windows. In the governing window W2 the overlay
*increased* maximum drawdown (34.5% vs 28.4%), sacrificed 3.63 pp of annual
return, and lost to the static 75:25 blend on drawdown and return
simultaneously. **All seven exit-and-re-enter cycles repurchased at a higher
price than they sold.** No criterion was rewritten. See trial #1 below.

---

## H5 — Monthly versus weekly rebalancing

**Statement.** Using an **identical underlying signal**, monthly rebalancing
produces higher net returns than weekly rebalancing.

**Null hypothesis (H5₀).** Weekly rebalancing performs equal to or better than
monthly rebalancing on a net basis.

**Rationale.** 12-1 momentum decays over months, not days, so weekly
rebalancing buys little additional signal while multiplying turnover roughly
threefold. On the Indian cost schedule — STT on both legs, a flat per-scrip DP
charge, and a minimum brokerage — this is expected to be a large and
one-directional effect. H5 exists because the expectation is strong enough to
be worth *falsifying explicitly* rather than assumed, and because the answer
directly sets the production rebalance frequency.

**Primary metric.** Net annualised return, monthly versus weekly, on the same
signal, same universe, same dates, same cost model.

**Secondary metrics.** Gross return delta (isolating whether weekly captures
more signal at all); annual one-way turnover; total costs in rupees; net
Sharpe; the gross-minus-net gap for each frequency.

**Data required.** Everything in H2. No additional data.

**Rejection criteria — H5 is rejected if any of the following holds.**
- Weekly net annualised return exceeds monthly by any margin over the holdout.
- The monthly advantage is smaller than the standard error of the difference.

**Interpretation note.** If weekly wins *gross* but loses *net*, H5 is
supported and the cost model is doing exactly the job it exists to do. That
outcome must be reported explicitly, not summarised as "monthly is better."

**Status:** `NOT_TESTED`
**Registered:** 2026-08-04

---

## H6 — Governance and surveillance exclusions

**Statement.** Pre-declared governance and surveillance exclusions reduce the
severity of the **worst 1% of stock-month outcomes** experienced by the
portfolio.

**Null hypothesis (H6₀).** The exclusions do not improve the left tail of the
outcome distribution.

**Rationale.** Certain public, dated, objective facts — a security placed
under an exchange surveillance measure, an auditor resignation, a going-concern
qualification, a high or rapidly rising promoter pledge — are associated with
subsequent severe drawdowns. The claim is deliberately **asymmetric**: these
signals are not expected to predict outperformance, only to remove part of the
catastrophic tail. A 12–15 name portfolio cannot absorb a single −70% holding,
so tail removal is worth paying for in diversification.

**Exclusion inputs are objective and public.** No exclusion may rest on
inference about intent, on media allegation, or on any unadjudicated claim
about a company or an individual. Only dated facts from exchange, regulator or
audited-filing sources are admissible.

**Primary metric.** Mean and 99th-percentile magnitude of the worst 1% of
monthly stock-level returns within the portfolio, with and without exclusions.

**Secondary metrics.** Count of holdings suffering a monthly return worse than
−25%; portfolio maximum drawdown; net CAGR delta; number of names excluded;
realised base rate of severe events among excluded names versus retained ones.

**Data required.** Historical surveillance-measure membership (**archived
prospectively from 2026-08-04 — no reliable historical archive exists, which
is itself a documented limitation of H6**); shareholding and pledge
disclosures; auditor-change and audit-qualification records; regulator
enforcement actions.

**Rejection criteria — H6 is rejected if any of the following holds.**
- The mean of the worst 1% of stock-month returns does not improve by at least
  3 percentage points.
- Net CAGR falls by more than 1.5 percentage points annualised.
- The exclusion set is too small to be statistically meaningful (fewer than 30
  excluded stock-months across the test period).

**Known limitation, recorded at registration.** Surveillance-measure history
before 2026-08-04 cannot be reconstructed reliably from public sources. H6 may
therefore only ever be testable on a forward sample. This is stated now so
that a future weak result is not mistaken for a weak *effect*, and so that no
retrospective surveillance dataset is later constructed by inference and
treated as if it had been observed.

**Status:** `NOT_TESTED`
**Registered:** 2026-08-04

---

---

# AMENDMENT A1 — Benchmark set expanded

**Date: 2026-08-04**
**Made before any data was ingested and before any hypothesis was tested.**
**Nothing above this line has been altered. This amendment is additive.**

## What prompted it

A review of India's investable factor indices (see
[`docs/benchmarks.md`](docs/benchmarks.md)) established that the primary
signal registered in H1 — 12-1 momentum on a Nifty 200 universe — is already
sold as a product. NSE publishes the **Nifty200 Momentum 30** index, and at
least five asset managers offer it as an ETF or index fund at **0.22%–0.30%
a year**.

The benchmark fixed at registration (Nifty 100 TRI) is therefore **necessary
but not sufficient**. An off-the-shelf ETF beats it with no work, so beating
it proves nothing about this project.

## What changes

**Baseline B3 becomes mandatory and blocking for H2, H3, H4 and H6.**

| ID | Baseline | Status |
|---|---|---|
| B1 | Nifty 100 TRI, buy and hold | Mandatory (unchanged) |
| B2 | Equal-weighted Nifty 100, annual rebalance | Mandatory (unchanged) |
| **B3** | **Nifty200 Momentum 30 TRI, less 0.22% expense, taxed as LTCG on exit rather than annually** | **Mandatory and blocking (new)** |
| B4 | The strategy with all signals randomised | Mandatory (unchanged) |

**A strategy that fails to beat B3 net of costs and net of tax is rejected,
regardless of its performance against B1.**

## The arithmetic this reflects

Assuming the DIY system and the ETF capture the same gross momentum return:

| | Momentum ETF | DIY manual | DIY with Groww API |
|---|---|---|---|
| Annual cost drag | 0.22% | 1.32% | 3.68% |
| Tax on gains | 12.5% LTCG, deferred | 20% STCG, annual | 20% STCG, annual |
| **Shortfall vs ETF at 15% gross** | — | **−3.84 pp/yr** | **−5.72 pp/yr** |

**The system must out-perform the momentum index by ~3.8 percentage points a
year just to draw level.** This is the real bar. It was not visible at
registration and is recorded here rather than discovered later.

## What this does to the hypotheses

**H1 and H2 are unchanged in wording.** H2 acquires B3 as an additional
blocking baseline through this amendment.

**H3, H4 and H6 become the investment case.** The index is a fixed, public,
semi-annual rule. It cannot exclude a stock the day it enters ASM/GSM, cannot
apply a governance filter, cannot de-risk into cash in an adverse regime, and
cannot concentrate below 30 names. Those four capabilities are the only
plausible sources of edge over B3 — and they are precisely what H3, H4 and H6
already test.

**No rejection criterion registered above has been weakened.** One baseline
has been added, which makes every test strictly harder.

## Pre-committed consequence

**If H3, H4 and H6 all fail while H1 succeeds, the correct action is to buy
the momentum ETF and stop building.** Recording that now, before any result
exists, is the point of this file.

## Recommended change to the benchmark holding

The report accompanying Phase 1 recommended holding ₹2,25,000 in a Nifty 100
index fund as the live benchmark. This amendment recommends that the
benchmark position be held in a **Nifty200 Momentum 30 ETF or index fund**
instead, or split across both. Holding the thing you are trying to beat, in
size, is the strongest available defence against self-deception.

⚠ This is a portfolio decision, not a research finding. Confirm expense
ratios, AUM, liquidity and tracking error on current AMC factsheets before
acting, and take tax advice on holding-period treatment.

---

# AMENDMENT A2 — H4 regime definition declared

**Date: 2026-08-04**
**Declared before any price series was downloaded, plotted or examined.**
**Nothing above this line has been altered. This amendment is additive.**

## Why this exists

H4 was registered with its regime definition marked **DEFERRED**, under four
constraints: at most two inputs, each observable at the close and never
revised, thresholds that are fixed constants or unconditional percentiles
rather than fitted values, and a rule expressible in one sentence.

This amendment discharges that obligation. It is written first because a
regime rule chosen after looking at the data is not a hypothesis — it is a
description of the data.

## The rule

> **RISK-OFF when the Nifty 100 closes below its 200-day simple moving average
> AND India VIX closes above its trailing three-year 80th percentile.
> Otherwise RISK-ON.**

In RISK-OFF the strategy holds **100% cash**. In RISK-ON it holds **100% of
the underlying strategy**. Binary, with no intermediate exposure, because
intermediate levels are another free parameter.

Regime is evaluated **only on rebalance dates**, using data available at the
previous close. Never intraday.

## Why each choice, stated before results exist

| Choice | Reason |
|---|---|
| **Two inputs only** | Every additional input multiplies the ways to accidentally fit history. |
| **Nifty 100 price index for the trend** | A price index, not total return: a moving average on a TRI drifts upward with reinvested dividends and slowly biases the signal. |
| **200-day SMA** | The most widely used trend threshold in existence, and — critically — a value fixed long before this project. A lookback I had searched for would be indistinguishable from noise-fitting to an outside reader. |
| **India VIX, trailing 3-year 80th percentile** | A *rolling unconditional* percentile, so no future information enters. A percentile rather than an absolute level because VIX levels drift across decades. |
| **AND, not OR** | Requiring both conditions trades responsiveness for far fewer false alarms. The cost is accepted openly: this rule will be **slow to de-risk** and will miss fast crashes. |
| **Binary exposure** | An exposure ladder (100/50/0) adds parameters without adding theory. |
| **Rebalance-date evaluation only** | Daily evaluation would multiply switches, costs and tax events. |

## Data to be used

| Series | Source | Role |
|---|---|---|
| Nifty200 Momentum 30 **TRI**, daily | NSE Indices historical data | The strategy return stream being overlaid |
| Nifty 100 **PR**, daily | NSE Indices historical data | Input to the 200-day SMA |
| India VIX, daily close | NSE | Input to the percentile threshold |
| Nifty 1D Rate Index | NSE Indices | Cash return while RISK-OFF |

If the Nifty 1D Rate series is unavailable, cash earns **0%**. That
understates the overlay's benefit, which is the safe direction to be wrong in.

## Evaluation windows — and an honesty constraint

The Nifty200 Momentum 30 index has a base date of 1 April 2005 but a **launch
date of 25 August 2020**. Everything before the launch is back-tested,
constructed with hindsight about which rules worked. India VIX history begins
around 2008–2009, which sets the practical start.

Two windows will therefore be reported **separately, never blended**:

| Window | Nature |
|---|---|
| **W1 — full available history** (from the first date all four series exist) | Contains a long back-tested segment |
| **W2 — live only** (2020-08-25 onward) | The only genuinely out-of-sample evidence |

**Pre-committed rule: where W1 and W2 disagree materially, W2 governs.** A
result that works only on the simulated segment is not evidence.

## Costs that must be modelled

A regime overlay is not free. Each switch liquidates and repurchases the
entire portfolio.

1. **Transaction costs:** 0.55% per full round trip, applied on every RISK-ON
   → RISK-OFF → RISK-ON cycle.
2. **Tax:** every RISK-OFF exit realises gains at **20% STCG** and resets the
   holding period. An overlay that trades twice a year permanently forfeits
   the 12.5% LTCG treatment its buy-and-hold comparator enjoys. This is the
   overlay's largest hidden cost and it must appear in the result, not a
   footnote.
3. **Signal lag:** regime computed on close of day *T* is acted on at day
   *T+1* at the earliest.

## Pass and fail criteria

**H4 is SUPPORTED only if all of the following hold, in W2:**
- Maximum drawdown is reduced by **at least 20% relative** to the unoverlaid
  index.
- Net CAGR, after transaction costs and STCG, falls by **no more than 2
  percentage points** annualised.
- Average regime switches are **at most 8 per year**.
- The drawdown benefit is present in **more than one distinct episode**.

**H4 is REJECTED if any of the following holds:**
- Relative drawdown reduction < 20%.
- Net CAGR falls more than 2 points.
- More than 8 switches per year on average.
- The entire benefit comes from a single historical episode.
- **The benefit is matched or exceeded by NSE's published
  `Nifty200 Momentum 30 Plus 8-13yr G-Sec 75:25` index** — because if a static
  bond blend achieves the same drawdown reduction with no machinery, no
  switching cost and no tax event, the dynamic overlay has no reason to exist.

That last criterion is the one most likely to fail, and it was added
deliberately.

## What this experiment can and cannot establish

**Can:** whether this specific rule reduces drawdown on the momentum factor's
own return stream, net of costs and tax, on live data.

**Cannot:** whether it would help a 12–15 stock portfolio, which is a noisier
version of the same exposure. A pass here is necessary, not sufficient. A
**fail here is sufficient to reject H4 entirely** — if the overlay cannot help
the clean index, it will not help a noisier proxy of it.

This asymmetry is the reason the cheap experiment runs before the expensive
data pipeline.

## Scope

Phase 1.5. No stock-level data, no corporate actions, no index membership
reconstruction, no survivorship-bias handling — index series only. Estimated
effort ~2 RU, against ~21 RU for the full pipeline needed to test H1 and H2.

---

# AMENDMENT A4 — Delisting treatment declared

**Date: 2026-08-07**
**Declared after observing the distribution of delisting outcomes, before any
strategy has been backtested on stock-level data.**
**Nothing above this line has been altered. This amendment is additive.**

## Why this exists

Phase 2 produced a dataset of **3,905 securities over 2015–2026, of which
1,092 (28%) no longer trade.** What a holder actually recovered on delisting
is not in price data, and the assumption chosen changes every result that
touches that tail. Leaving it undeclared would let it be chosen later, after
seeing which answer it produced.

## What the data showed

Two questions were asked of the 1,092 delistings before any threshold was set.

**Is the outcome distribution bimodal?** No. Measured against the trailing
250-session peak, delistings are spread almost uniformly from 0.10 to 1.05
(median 0.57). Measured against the close 60 sessions earlier, likewise
(median 0.83). **There is no natural split, so no single threshold is
defensible.**

**Are the tails separable?** Yes.

| Evidence | Count | Share |
|---|---|---|
| Rising into the final session (`terminal_slide` ≥ 1.05) | ~315 | 29% |
| Ended below 10% of the 250-session peak | ~87 | 8% |
| Neither | ~690 | **63%** |

A security whose price rises into its last session is converging toward an
offer: an acquisition, where the holder was paid. One that ends far below its
own recent peak is a collapse. The 63% in between is not separable from
prices.

**A correction recorded for the record.** An earlier measure compared the last
close to the *first observed* close. That is confounded by however long a
security traded — a company can triple over eight years and then collapse in
its final quarter, and the two are indistinguishable under that measure. It
was replaced before any threshold was chosen.

## The declared treatment

Delistings are classified three ways, using thresholds **read once from the
distribution above and fixed here**:

| Outcome | Test | Terminal value |
|---|---|---|
| `LIKELY_COLLAPSE` | `final_decline` ≤ **0.10** | 0 |
| `LIKELY_ACQUISITION` | `terminal_slide` ≥ **1.05** | last close |
| `UNCERTAIN` | everything else | **refused** |

The collapse test runs first: a security far below its peak that bounced in
its final weeks is a collapse, not an acquisition.

## Reporting rule — binding

**Every result that includes delisted securities must report two bands:**

1. **Outer bound** — from assuming every delisting recovered its last close,
   down to assuming none did. Never discarded.
2. **Classified band** — the confident tails resolved, only the `UNCERTAIN`
   middle floating.

**A conclusion that holds across the outer bound does not depend on this
amendment at all.** A conclusion that holds only inside the classified band
depends on an inference from price data, and must be reported as such.

## Limitations, stated in advance

- These labels are **inferences, not records**. Deciding an acquisition from a
  collapse properly requires corporate-action filings this project does not
  have.
- A security that spikes and is then *suspended* looks identical to one
  acquired at a premium. This is why the labels remain `LIKELY_`.
- The 63% `UNCERTAIN` share is not a defect to be optimised away. Narrowing it
  by moving thresholds would be fitting the delisting assumption to the
  answer, which is the specific failure this file exists to prevent.
- **Changing either threshold requires a further dated amendment**, and counts
  as an additional trial.

---

# AMENDMENT A5 — Proxy universe declared as scaffolding

**Date: 2026-08-10**
**Declared before the proxy universe has been built, before any strategy has
been run against stock-level data, and before any universe-dependent result
exists.**
**Nothing above this line has been altered. This amendment is additive.**

## Why this exists

Phase 3 needs a tradeable universe. The honest universe is the **actual
historical membership of the Nifty 100**, which changes at semi-annual
rebalances and can only be recovered from roughly 30–40 NSE Indices circulars.
Those circulars have not been collected.

There are two ways to handle that, and only one of them is safe.

The unsafe way is to build a convenient universe, get the engine working,
produce results, and then decide whether the real membership is worth the
effort. By that point the answer is contaminated: the convenient choice has
already produced numbers, and replacing it means throwing away work — which is
exactly the pressure that makes people keep the convenient choice and stop
mentioning it.

The safe way is to declare, in advance and in writing, that the convenient
universe is **scaffolding with no evidentiary status**. That is this amendment.

## The declared proxy

Fixed here, before it is implemented and before any result is seen:

| Parameter | Value | Why this, stated before results exist |
|---|---|---|
| Ranking metric | **Median daily traded value over the trailing 126 sessions** | Median not mean, so a single delivery-driven spike cannot lift a stock into the universe. 126 sessions ≈ six months, matching the rebalance interval. |
| Size | **Top 100** | Matches the Nifty 100 count so position sizing and concentration are comparable, even though membership will not be. |
| Series eligibility | **`EQ` only** | `BE`/`BZ` are trade-to-trade: compulsory delivery, no intraday netting. Their liquidity is not comparable and their costs are different. |
| Minimum history | **126 sessions of observed trading** | A stock cannot be ranked on a window it does not have. Ranking on a partial window silently favours recent listings. |
| Rebalance | **Semi-annual, effective the first session of April and October** | Mirrors NSE's cadence. Fixed here so it cannot later be tuned. |
| Reconstitution lag | **Ranking window ends 5 sessions before the effective date** | The ranking must be computable from data available before it is acted on. |
| Delisted securities | **Retained until they stop trading**, terminal value per Amendment A4 | No survivorship bias. A5 does not weaken A4. |

## What this proxy is, and what it is not

**It is a liquidity ranking. The Nifty 100 is a size ranking.** NSE selects on
full market capitalisation from the Nifty 500 universe and applies liquidity as
a filter, not as the criterion. Turnover and market capitalisation are
correlated but far from identical: this proxy will admit small, heavily traded,
often speculative stocks that the real index excludes, and will drop large,
quietly held ones that it includes.

That difference is not a rounding error. It is a systematic tilt toward exactly
the kind of stock that produces flattering momentum backtests.

## Binding guard — the point of this amendment

1. **No result produced on the proxy universe may be entered in the trial
   register.** Not as a trial, not as a preliminary finding, not as a footnote.
2. **No result produced on the proxy universe may be cited as evidence for or
   against H1, H2, H3, H5 or H6.**
3. The proxy exists **solely** to exercise the engine: to verify that costs are
   charged, that execution lags correctly, that leakage is detectable, and that
   the plumbing does what it claims.
4. **Every H1–H6 test must be run on reconstructed Nifty 100 membership.** If
   the circulars cannot be obtained, that is a finding to be reported — not a
   licence to substitute the proxy.
5. Any output generated on the proxy must be written to paths marked
   `proxy_universe/` and must carry the header
   `SCAFFOLDING — NOT EVIDENCE (Amendment A5)`.

## The failure mode this is designed to prevent

If the proxy produces an encouraging result, the temptation will be to treat
collecting the circulars as optional. If it produces a discouraging one, the
temptation will be to blame the proxy and collect the circulars hoping for
better. **Both are the same error**: letting the result decide the method.
Declaring in advance that the proxy decides nothing removes the incentive in
both directions.

## Limitation stated in advance

Building the engine against a universe with a known tilt risks tuning the
engine — its filters, its liquidity thresholds, its handling of thin names — to
that tilt. Mitigation: no parameter of the strategy may be chosen or adjusted
while looking at proxy-universe output. Only *mechanical* properties
(does it lag correctly, are costs charged, is leakage detected) may be verified
there.

**Superseding this amendment requires a further dated amendment.**

---

# AMENDMENT A6 — Capital limit, abandonment rule, and the derivatives gate

**Date: 2026-08-10**
**Declared before any strategy result exists, before any capital has been
deployed, and before any derivatives work has begun.**
**Nothing above this line has been altered. This amendment is additive.**

## Why this exists

Everything in this file so far constrains *how results are produced*. Nothing
yet constrains *what happens when a result arrives*. That gap is where most
retail capital is lost: not in the research, but in the moment after an
encouraging backtest, when position size and stopping conditions get decided by
enthusiasm rather than by a rule written while nothing was at stake.

The owner has stated an intention to eventually explore derivatives. That
intention is legitimate and this amendment does not forbid it. It fixes the
conditions **now**, while they are still theoretical and therefore cheap to
set honestly.

## Capital limit — binding

| Constraint | Value |
|---|---|
| Maximum capital ever routed through this system | **₹3,00,000** |
| As a share of financial assets at declaration | 4.6% |
| Increase permitted | **Only by a further dated amendment**, and only after the abandonment test below has been *passed*, not merely not-failed |
| Capital may not be increased because | a result improved, a drawdown recovered, or the owner feels more confident |

The limit is a rupee figure, not a percentage. A percentage limit silently
raises the rupee amount every time the portfolio grows — which means it loosens
fastest precisely when success has made overconfidence most likely.

## Abandonment rule — binding

The system is **abandoned** — code archived, no capital deployed, hypotheses
marked `REJECTED` — if, after **two full years of paper trading** from the first
live signal:

1. It has **not** beaten the Nifty200 Momentum 30 index fund (Baseline B3 under
   Amendment A1) net of modelled costs and tax, **or**
2. Its realised Deflated Sharpe Ratio fails to clear the threshold implied by
   the trial register at that date, **or**
3. Fewer than **24 months** of genuine out-of-sample paper results exist,
   because the requirement is time survived, not trials run.

**Two years is deliberately long.** It is long enough to contain a drawdown and
short enough that the sunk cost stays bearable. Any shortening requires a dated
amendment and counts as a trial.

**What abandonment does not mean.** It does not mean the research was wasted, and
it does not bar future work under a new pre-registration. It means *this* set of
hypotheses, tested this way, did not clear the bar.

## Derivatives gate — conditions fixed in advance

F&O work is **out of scope until every condition below is met**. Each is
falsifiable and none depends on how the equity research turns out.

1. A **separate dated amendment** stating the exact strategy, instruments,
   maximum loss per position, and pass/fail criteria, written before any
   derivatives backtest is run.
2. The equity system has **passed** the abandonment test above. Derivatives are
   not a response to cash equities disappointing.
3. Capital cap of **₹50,000** — one sixth of the equity cap — and no position
   whose maximum loss exceeds **₹10,000**.
4. **No naked short options, ever.** Undefined-risk positions are excluded by
   this amendment permanently, not provisionally. A defined-risk structure can
   lose what was staked; an undefined-risk one can lose more than the account.
5. Covered and hedged structures only: covered calls against stock already held,
   protective puts, defined-risk spreads.
6. The base rate must be restated in that amendment: **SEBI found 91% of
   individual traders lost money in equity derivatives in FY25, ₹1,05,603 crore
   net, up 41% year on year.** Not as discouragement — as the prior any claimed
   edge must be measured against.

## The specific failure this is designed to prevent

The sequence that empties retail accounts is well documented and always the
same: a strategy underperforms, the response is to increase size or move to a
higher-leverage instrument to make it back, and the loss that follows is larger
than every gain preceding it. Conditions 2 and 3 above break that sequence at
the exact point it starts.

**Superseding any clause in this amendment requires a further dated amendment,
and each such amendment is logged as a trial.**

---

# AMENDMENT A8 — DP charging unit corrected against real contract notes

**Date: 2026-08-23** · **Made before any hypothesis was tested on stock-level
data.**

## Why this exists

H2's rationale asserted that DP charges are "a flat rupee amount **per sell
scrip**". That is Zerodha's rule. It is not the rule this account is charged
under, and the difference is not cosmetic.

Two Groww contract notes settle it (`docs/cost_model_validation.md`):

```
4 August 2026    6 scrips, 6 sell orders, 7 trades   DP Rs 141.60 = 6 x 23.60
11 August 2026   2 scrips, 3 sell orders             DP Rs  70.80 = 3 x 23.60
```

Jio Financial was sold in **two orders on one day and charged twice**.
Per-scrip-per-day predicts ₹47.20; the note says ₹70.80. The 4 August note
rules out per-trade in the other direction: one order filled in two trades was
charged once.

Both days reconcile to the paisa against the funds ledger, DP included.

## What changes

1. The rationale text in **H2** is corrected in place, with a pointer here. The
   registered *claim* is untouched: DP is still a flat rupee cost that
   penalises small positions. Only the unit it is levied on was wrong.
2. **Nothing in any rejection criterion changes.** The correction makes modelled
   costs equal or higher, never lower, so it cannot turn a rejection into a
   pass.
3. Every result must continue to report its **orders-per-exit assumption**, as
   Amendment A7 already requires. The unit correction is what makes that
   assumption load-bearing rather than decorative: at one order per exit the
   two rules agree, and they diverge only as execution splits.

## Why this is a correction and not a relaxation

The direction matters. A pre-registered document may be corrected freely
towards **stricter** costs; the same edit in the other direction would be
indistinguishable from fitting the rules to a result. Per-order is weakly more
expensive than per-scrip for every possible execution, and strictly more
expensive whenever any position exits in more than one order. This amendment
can only make H2 harder to pass.

## The general rule this sets

Rates in the cost model came from documentation. Documentation was wrong about
the charging unit while being right about the rate — a class of error that no
amount of re-reading the tariff page would have caught, because the tariff page
says what is charged and not what it is charged *per*.

**Any cost parameter not yet checked against a real settled transaction is
marked as documented-only until it is.** `docs/cost_model_validation.md` is the
register of which is which.

## Still unresolved, and stated rather than buried

The Groww ledger contains charges the engine does not model at all:
`TURNOVER_COLLECTED` (₹2,264.80, one debit, meaning unknown) and
`INTEREST_ACCRUED` (₹0.69 every day without a break, alongside pledge and DDPI
charges — the signature of a margin facility rather than plain delivery).

Neither is answerable from the file. Until they are, **measured account costs
exceed modelled trading costs by an amount that has not been quantified**, and
no H2 result may be described as a full accounting of what the account paid.

---

# AMENDMENT A9 — H2 portfolio specification declared

**Date: 2026-08-23** · **Made before the momentum signal was implemented and
before any stock-level backtest was run.**

## Why this exists

H2 says a portfolio of "the highest-ranked momentum names" beats the Nifty 100
TRI net of costs. It never said **how many names**, how they are weighted, or
when they are bought. Those are not details; they change the answer. Leaving
them open until the first run means choosing them while a result is visible,
which is selection whatever it is called afterwards.

Everything below is fixed now, in advance, and each choice is justified from
reasoning that reads **no returns**.

## The specification — binding

| Parameter | Declared value |
|---|---|
| Universe | Point-in-time Nifty 100 on the rebalance date (`market/membership.py`) |
| Signal | 12-1 momentum: total return over the trailing 12 months, excluding the most recent month — **as registered in H1** |
| Holdings | **10** — the top decile |
| Weighting | Equal, at the rebalance |
| Cadence | Monthly, first session of the month |
| Decision data | Closes up to and including the previous session |
| Execution | Next session's open, as the engine already enforces |
| Minimum history | 252 sessions, so the 12-1 window is complete rather than partial |
| Eligibility | Must have traded on the decision date |
| Leaving the index | The book is rebuilt from current members each month, so a departed name is simply not re-selected. No forced intra-month sale |
| Delisting | Amendment A4, both bands reported |
| Orders per exit | Reported at 1, 1.5 and 3 (A7). **1.5 is the measured rate** from the 11 August contract note |
| Capital | ₹3,00,000 (A6) |

## Why ten, and not any other number

**Because H1 tests decile 10.** H1's rejection criteria are written about the
top decile of a hundred-name universe. If H2 holds twenty names it is a
different portfolio, and neither outcome answers the question H2 was registered
to ask: *is the effect H1 measures tradeable?* A positive result would not be
attributable to decile 10, and a negative result could be dilution from names
11–20 rather than costs.

**And because it is the cheapest configuration A7 permits.** One full turnover
at ₹3,00,000 costs 0.458% at one sell order per exit, 0.498% at the measured
1.5, and 0.616% at three. It clears the 1.00% budget under every execution
assumption, with the widest margin of any breadth considered.

Both reasons read no returns. Neither was chosen because a backtest liked it.

**The cost of this choice, stated rather than discovered later.** Ten equal
positions of ₹30,000 is concentrated. One position is 10% of the book, and a
single failure of the DHFL or Jet Airways kind — both present in this archive
and both real — removes roughly a tenth of capital in a session. That is a
genuine property of running a decile portfolio on ₹3L, not an artefact, and it
must appear in the reported drawdown rather than be smoothed by widening the
book after the fact.

## Trial accounting

This is **one** configuration and will be logged as **one** trial. No breadth
sweep will be run. If a later amendment tests a different N, it is a new trial
and enters the Deflated Sharpe denominator, whatever the first result was.

## Window discipline — binding

Development runs **2015-01-01 to 2021-12-31**. The holdout declared in this
file, **2022-01-01 to 2025-12-31**, is not touched until the specification is
final and the development result is recorded. It is touched **once**.

The archive extends to 2026-08-05. That tail is **outside** the declared
holdout and is not a second holdout; it is not to be used to rescue a failed
result.

## What would make this amendment dishonest

Changing N, the weighting, the cadence or the window **after** seeing a
development result, and reporting the second number as though it were the
first. If any of those changes, the original result stays in the trial
register with its outcome, and the new one is logged beneath it.

---

## Trial register

Every backtest configuration executed against project data is recorded here,
including abandoned ones. This register is the denominator in the Deflated
Sharpe Ratio.

| # | Date | Hypothesis | Configuration | Data snapshot | Commit | Outcome |
|---|---|---|---|---|---|---|
| **1** | 2026-08-06 | **H4** | A2 regime rule as declared: Nifty 100 < 200d SMA AND India VIX > trailing 756d 80th pct; monthly evaluation; 1-period lag; 0.55% round trip; 20% STCG; cash at 0% | NSE Indices + NSE: Nifty 100 PR 2003-2026, Momentum 30 TRI 2005-2026, India VIX 2010-2026, Momentum30+G-Sec 75:25 2011-2026 | `5fed927` | **REJECTED** (see below) |
| **2** | 2026-08-23 | **H2** | A9 as declared: 10 holdings, top decile of 12-1 momentum in the point-in-time Nifty 100, equal weight, monthly, decided on previous close and filled at next open, ₹3,00,000, 1 sell order per exit | Bhavcopy 2015-2026 back-adjusted; NSE corporate actions; reconstructed point-in-time Nifty 100; Nifty 100 TRI | `d36ea3e` | **REJECTED** (see below) |
| **3** | 2026-08-23 | **H1** | As registered: 12-1 momentum deciles within the point-in-time Nifty 100, forward one-month excess return over the Nifty 100 TRI, monthly, **gross** | Same as trial #2 | *pending* | **REJECTED** (see below) |

---


### Trial #1 detail - H4 regime overlay

**Run:** 2026-08-06 · **Windows:** W1 2013-07-23 to 2026-08-05 (contains
back-tested index history), W2 2020-08-25 to 2026-08-05 (live; governs).
**Regime fired on 9.8% of dates; ~0.8-1.0 switches per year.**

| Metric | Overlaid | Buy & hold | Static 75:25 blend |
|---|---|---|---|
| W2 net CAGR | 14.59% | **18.21%** | 15.3% |
| W2 max drawdown | 34.49% | 28.37% | **22.0%** |
| W1 net CAGR | 14.13% | **18.66%** | 16.1% |
| W1 max drawdown | 36.30% | 28.37% | **22.0%** |

**Criteria (W2, governing):**

| Criterion | Observed | Required | Outcome |
|---|---|---|---|
| Drawdown reduction | **−21.6%** (i.e. drawdown got *worse*) | ≥ +20% relative | **FAIL** |
| CAGR sacrifice | +3.63% p.a. | ≤ 2% p.a. | **FAIL** |
| Switching frequency | 0.8/yr | ≤ 8/yr | PASS |
| Multiple episodes | 2 | ≥ 2 | PASS |
| Beats static blend | 34.5% vs 22.0% DD | overlay DD < blend DD | **FAIL** |

**Mechanism, verified rather than assumed.** Every one of the seven complete
exit-and-re-enter cycles repurchased at a higher price than it sold:

| Exit | Index | Re-entry | Index | Round trip |
|---|---|---|---|---|
| 2013-09-02 | 3,810 | 2013-11-01 | 4,303 | +12.9% |
| 2015-09-01 | 7,197 | 2015-10-01 | 7,491 | +4.1% |
| 2018-11-01 | 11,741 | 2018-12-03 | 12,374 | +5.4% |
| 2019-02-01 | 12,751 | 2019-04-01 | 13,210 | +3.6% |
| 2020-03-02 | 13,504 | 2020-08-03 | 13,756 | +1.9% |
| 2022-03-02 | 23,321 | 2022-04-01 | 24,773 | +6.2% |
| 2026-04-01 | 34,769 | 2026-06-01 | 37,610 | +8.2% |

**0 of 7 helped.** Both inputs confirm *after* the move: a 200-day average and
a three-year volatility percentile are lagging by construction, and monthly
evaluation adds further delay. The rule sells into weakness and rebuys into
strength. Even the March 2020 exit - well timed, ahead of the worst of the
crash - failed because re-entry did not come until August, missing the
recovery.

**Costs, for the record:** W2 transaction costs Rs 6,989 and capital gains tax
Rs 13,509 on a Rs 3,00,000 book. The tax was roughly twice the trading cost,
as Amendment A2 anticipated.

**What this does and does not establish.** It rejects *this* rule, as declared.
It does not establish that no regime overlay can work. Testing a different
definition is legitimate and requires a new dated amendment *before* testing,
and would be logged here as trial #2 - because the more definitions tried, the
more likely one succeeds by chance.

**Consequence under Amendment A1.** A1 identified H3, H4 and H6 as the only
plausible sources of edge over a 0.22% momentum ETF. **One of the three is now
gone.**

---

### Trial #2 detail — H2 net benchmark outperformance

**Run:** 2026-08-23 · **Window:** 2016-02-09 to 2021-12-31 (5.89 years, 71
rebalances, 70 monthly observations). The window starts thirteen months after
the archive does because 12-1 momentum needs 273 sessions before the first
decision. **The 2022-2025 holdout was not touched.**

| | Strategy | Nifty 100 TRI |
|---|---:|---:|
| Gross CAGR, before any cost | **14.04%** | 17.36% |
| After charges | 12.13% | — |
| After charges and tax | **10.85%** | 17.13% *(after 0.20% expense ratio)* |
| Maximum drawdown | 47.79% | 37.94% |
| Volatility | 23.23% | 17.52% |
| Final value on ₹3,00,000 | ₹5,50,426 | ₹7,61,607 |

**Criteria as declared. H2 is rejected if any fails.**

| Criterion | Observed | Required | Outcome |
|---|---|---|---|
| Net return exceeds Nifty 100 TRI | 10.85% vs 17.13% | strategy > benchmark | **FAIL** |
| Newey-West \|t\| on net excess | 0.98 (naive 0.92, lag 3) | ≥ 3.0 | **FAIL** |
| Max drawdown vs benchmark | 47.79% vs 37.94% = 1.26× | ≤ 1.3× | PASS |
| DSR p-value, PBO, 1.5× cost stress, 40% single-year concentration | — | — | **moot** |

The last four are not scored because they cannot rescue a rejection: each asks
whether a positive excess return is real, and this excess return is negative.

**The mechanism, and it is not the one this project expected.**

```
Strategy gross vs raw TRI      -3.32%   <-- before a single rupee of cost
  charges                      -1.92%
  capital gains tax            -1.28%
                               ------
Net excess                     -6.28%
```

**The signal lost before it paid anything.** Every prior amendment in this file
treats Indian transaction costs as the thing that would decide H2 — A1, A6, A7
and A8 are all about costs, and the cost model was validated to the paisa
against real contract notes precisely so this moment would be trustworthy. The
costs turned out to be real, correctly modelled, and **not the cause**. They
took a 3.32% annual deficit and made it 6.28%.

Cash drag was measured and ruled out: the book held a mean of **1.96%** cash,
so the shortfall is not an artefact of ₹30,000 positions failing to fill in
high-priced names.

**What this does and does not establish.**

It rejects **this** specification — top decile, ten names, monthly, on the Nifty
100 large-cap universe, over this window. It does not establish that momentum
is absent in Indian equities. A t-statistic of 0.98 is not evidence of
underperformance either; it says the difference is indistinguishable from noise
over 70 observations, and 70 is not many.

The most likely explanations, none of them tested and each of which would be a
new amendment and a new trial:

1. **The universe is too large-cap.** Published Indian momentum results
   concentrate in mid-caps; the Nifty 100 is the top hundred by size, where the
   effect is weakest and most arbitraged. NSE's own momentum index draws from
   the Nifty 200.
2. **The window is unkind.** 2018-2020 was a poor stretch for momentum globally,
   and it is a third of this sample.
3. **Ten names is too few to express a cross-sectional effect.** The strategy's
   23.23% volatility against the index's 17.52% is the cost of concentration,
   and A9 chose ten for continuity with H1 and for cost, not for signal
   fidelity.

**Consequence under Amendment A1.** A1 named H3, H4 and H6 as the only plausible
sources of edge over a 0.22% momentum ETF. H4 is rejected. H2's base case is now
**negative before costs**, which means H3 and H6 are no longer improvements on a
working strategy — they would have to create the edge, not refine it.

**Consequence for H1.** H1 predicts monotonic deciles with decile 10 beating
decile 1. It is not refuted by this, because H1 is a statement about
cross-sectional rank and this is a statement about one portfolio against an
index. But decile 10 underperforming the index gross for 5.89 years is not what
a strong momentum effect looks like, and H1 should now be tested expecting a
weak result rather than a confirmation.

---

### Trial #3 detail — H1 momentum monotonicity

**Run:** 2026-08-23 · **Window:** 2016-02-09 to 2021-11-01, 70 monthly
rebalances, 94-101 securities ranked per date. **Gross.** Holdout untouched.

| Criterion | Observed | Required | Outcome |
|---|---|---|---|
| Mean rank IC | **+0.0378** | > 0 | PASS |
| Newey-West \|t\| on mean IC | **1.47** (naive 1.30, lag 3) | ≥ 3.0 | **FAIL** |
| Decile monotonicity | **+0.758** | ≥ 0.6 | PASS |
| D10−D1 positive in sub-periods | **2 of 5** | ≥ 3 of 5 | **FAIL** |

**Decile mean excess return, per month, gross:**

```
D1   -0.599%      D6   -0.240%
D2   -0.198%      D7   -0.320%
D3   -0.441%      D8   +0.376%
D4   -0.445%      D9   +0.403%
D5   -0.425%      D10  -0.138%   <-- the decile H2 traded
```

**The finding, and it explains trial #2 exactly.** The effect is not absent —
the mean IC is positive, its magnitude is ordinary for a real monthly factor,
and monotonicity clears its threshold. What fails is the **top decile**, which
is the only part a ten-name portfolio can hold.

D10 was positive in **32 of 70 months (46%)** — worse than a coin flip — where
D9 managed 57% and D8 59%. H2 bought D10 every month for 5.89 years and lost
3.32% a year gross. H1 says why: it bought the one decile in the upper half
that did not work.

**Sub-period instability, which is the other failure:**

```
2016-02 .. 2017-03    -0.427% / month
2017-04 .. 2018-05    +1.992%
2018-06 .. 2019-07    +3.645%
2019-08 .. 2020-09    -2.559%
2020-10 .. 2021-11    -0.346%
```

A spread that ranges from +3.6% to −2.6% per month across five equal blocks is
not a stable effect. The D10−D1 spread was positive in 43 of 70 individual
months (61%), so the sign is more often right than wrong; the losing months are
simply much larger.

**A post-hoc check, recorded as a diagnostic and explicitly not as a result.**
Excluding the four COVID-window rebalances (March–June 2020) raises monotonicity
to +0.867 and the D10−D1 spread to +0.99% per month. It does **not** change the
verdict, and it must not: choosing which months to exclude after seeing the
answer is the exact selection this register exists to prevent. It is recorded
for one reason only — even with COVID removed, **D10 (+0.03%) still trails D8
(+0.42%) and D9 (+0.48%)**. The top-decile weakness is not a COVID artefact.

**What this establishes.** Within the Nifty 100, 12-1 momentum carries weak
positive cross-sectional information that is not statistically distinguishable
from noise at the registered bar, is unstable across sub-periods, and is
**absent in the extreme top decile** where a small concentrated portfolio must
operate.

**What it does not establish.** That momentum is absent from Indian equities.
The Nifty 100 is the largest, most-researched hundred names in the market. This
says nothing about mid-caps, and NSE's own momentum index draws from the Nifty
200 rather than the 100.

**A trap worth naming.** "Trade D8 and D9 instead of D10" is the obvious
reading and it is exactly the move the trial register exists to make expensive.
The rank at which an effect lives was not registered in advance; picking it now,
from this output, is selection. Testing it is legitimate and requires a new
dated amendment before the run — and it would be trial #4, raising the Deflated
Sharpe bar for whatever eventually passes.

**Consequence under Amendment A1.** A1 named H3, H4 and H6 as the only plausible
sources of edge over a 0.22% momentum ETF, on the assumption that momentum
itself worked. H4 is rejected, H2 is rejected, and H1 now says the underlying
effect is weak and unstable in this universe. **All three of A1's candidate
sources rested on a foundation that has not held.**

---

## The cost floor, measured

Established 2026-08-18 from the validated cost model, reading **no returns**
(`docs/breadth_frontier.md`). Cost of one full turnover at ₹3,00,000:

| Holdings | Position | DP | Brokerage | Statutory | **Total** |
|---:|---:|---:|---:|---:|---:|
| 10 | ₹30,000 | 0.079% | 0.157% | 0.222% | **0.458%** |
| 15 | ₹20,000 | 0.118% | 0.236% | 0.222% | **0.576%** |
| 30 | ₹10,000 | 0.236% | 0.236% | 0.222% | **0.694%** |
| 50 | ₹6,000 | 0.393% | 0.236% | 0.222% | **0.852%** |
| 100 | ₹3,000 | 0.787% | 0.393% | 0.222% | **1.402%** |

Three facts follow, none of which depend on any strategy working:

1. **0.222% is the floor nobody escapes.** STT, stamp duty and exchange fees
   are proportional, so they are the same at every breadth. Any edge must clear
   this before anything else.
2. **Brokerage is a second fixed cost, not a rate.** It hits its ₹5 floor below
   a ₹5,000 order — at 100 names it is 0.393%, *larger than the DP charge at 15
   names*. The floor was invisible until real contract notes were read.
3. **Going from 100 names to 10 saves 0.944% per turnover** at ₹3L. That is
   larger than most claimed edges, and it is certain rather than hoped for.

**The capital equivalence.** 100 names at ₹20,00,000 costs 0.576% — identical
to 15 names at ₹3,00,000. Breadth is not free; it is bought with capital.

**What the budget actually permits.** The 1.00% cap admits up to 50 holdings if
every exit fills in a single order, but only **20** if exits take three orders:

| Holdings | 1 order | 1.5 orders | 3 orders |
|---:|---:|---:|---:|
| 10 | 0.458% | 0.498% | 0.616% |
| 15 | 0.576% | 0.635% | 0.812% |
| 20 | 0.616% | 0.694% | 0.930% |
| 30 | 0.694% | 0.812% | **1.166%** |
| 50 | 0.852% | **1.048%** | **1.638%** |
| 100 | **1.402%** | **1.796%** | **2.976%** |

The permitted breadth is set by *execution*, not by strategy. That is why A7
requires the orders-per-exit assumption to be reported with every result:
30 holdings passes at 0.694% and fails at 1.166%, and only the assumption
separates them.

---

## Amendment log

| Date | Hypothesis | Change | Reason | Made before testing? |
|---|---|---|---|---|
| 2026-08-04 | — | Initial registration of H1–H6 | Phase 1 foundation | Yes — no data existed |
| 2026-08-04 | H2 (and H3/H4/H6 by reference) | **Amendment A1** — added Baseline B3 (Nifty200 Momentum 30, net of 0.22% and LTCG) as a mandatory blocking baseline | The primary signal is already an investable product; the original benchmark was insufficient | Yes — no data ingested, nothing tested |
| 2026-08-04 | H4 | **Amendment A2** — declared the regime definition, data sources, evaluation windows, cost model and pass/fail criteria | H4 was registered with its definition DEFERRED; it must be fixed before testing | Yes — no price series downloaded, nothing plotted |
| 2026-08-07 | all (data treatment) | **Amendment A4** — declared the three-way delisting classification, its thresholds, and the two-band reporting rule | 1,092 delistings observed in the Phase 2 dataset showed no bimodal split; only the tails are separable | Yes — no strategy backtested on stock-level data (`0174cfd`) |
| 2026-08-10 | all (deployment) | **Amendment A6** — fixed a ₹3,00,000 capital cap, a two-year abandonment test against Baseline B3, and six binding pre-conditions on any future derivatives work including a permanent ban on naked short options | Nothing in this file yet governed what happens *after* a result arrives, which is where retail capital is actually lost. The owner intends to explore F&O eventually; the conditions are cheapest to set honestly while still theoretical | Yes — no strategy result exists, no capital deployed, no derivatives work begun |
| 2026-08-10 | all (universe) | **Amendment A5** — declared a liquidity-ranked proxy universe as engine scaffolding, with a binding guard that no result from it may enter the trial register or bear on any hypothesis | Phase 3 needs a universe; real Nifty 100 membership requires ~30–40 uncollected NSE circulars. Declaring the proxy's zero evidentiary status *before* it produces any number removes the incentive to let a convenient result stand | Yes — proxy not yet implemented, no engine exists, no stock-level backtest run |
| 2026-08-23 | H2 (portfolio specification) | **Amendment A9** — declared H2's unstated parameters: **10 holdings** (the top decile), equal weight, monthly on the first session, decided on the previous close and filled at the next open, 252-session minimum history, development window 2015–2021 with the 2022–2025 holdout untouched. Logged as **one** trial; no breadth sweep | H2 said "the highest-ranked momentum names" without saying how many, which changes the answer. Ten because H1's criteria are written about decile 10 — holding twenty would test a different portfolio and could not say whether H1's effect is tradeable — and because it is the cheapest breadth A7 permits (0.458%–0.616% per full turnover across every execution assumption). Both reasons read no returns | Yes — momentum signal not yet implemented, no stock-level backtest run |
| 2026-08-23 | H2 (cost model) | **Amendment A8** — corrected the DP charging unit from "per sell scrip" to **per sell order**, verified against two Groww contract notes and reconciled to the paisa against the funds ledger. Set a standing rule that any cost parameter not checked against a real settled transaction is marked documented-only | The registered text stated Zerodha's rule, not the one this account is charged under. A security sold in two orders on one day is charged twice. The correction is weakly **stricter** for every possible execution and strictly stricter whenever an exit splits, so it can only make H2 harder to pass — which is the only direction a pre-registered document may be corrected in without the edit being indistinguishable from fitting the rules to a result | Yes — no hypothesis tested on stock-level data; the correction raises modelled costs |
| 2026-08-18 | all (portfolio construction) | **Amendment A7** — set a **portfolio breadth budget**: no configuration may be tested whose modelled cost of one full turnover exceeds **1.00% of capital**, which at ₹3,00,000 rules out 100 equal-weight holdings (1.402%) and 50 (0.852% at one order per exit, 1.638% at three). Every result must report the holdings count and the assumed sell orders per exit | Two independent methods agree the ₹3L/100-name configuration is uneconomic before any signal is considered: this project's own engine measured DP at 48.5% of all charges over 11 years, and a broker-tariff analysis reached the same conclusion from first principles. The cost model has since been validated to the paisa against real contract notes. Setting the budget from cost arithmetic — which reads no returns — costs no trial budget and removes the temptation to keep a wide book because one backtest liked it | Yes — no hypothesis tested on the real universe; breadth chosen on cost, not performance |

---

*Every hypothesis in this file was registered before the data to test it
existed. **Three** trials have since been run and are recorded in the trial
register — **#1 H4**, **#2 H2** and **#3 H1**, all rejected — and the price
archive runs 2015-2026. No result has been observed for **H3, H5 or H6**. The
declared holdout, 2022-01-01 to 2025-12-31, remains **untouched**.*

*Three rejections is not a failure of the project. It is the project working:
each was rejected against criteria fixed before the data existed, and none
required an argument about what the criteria should have said.*

*This closing note previously read "No backtest has been run. No market data
has been ingested." Both statements were true when written and had quietly
stopped being true. A pre-registration whose own status line is stale is
worthless as a record, so the status is now stated specifically enough to go
out of date visibly rather than silently.*
