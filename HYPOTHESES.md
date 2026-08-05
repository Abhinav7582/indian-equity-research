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

**Status:** `NOT_TESTED`
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
trade, and DP charges are a **flat rupee amount per sell scrip**, which
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

**Status:** `NOT_TESTED`
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

**Status:** `NOT_TESTED`
**Registered:** 2026-08-04

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

## Trial register

Every backtest configuration executed against project data is recorded here,
including abandoned ones. This register is the denominator in the Deflated
Sharpe Ratio.

| # | Date | Hypothesis | Configuration | Data snapshot | Commit | Outcome |
|---|---|---|---|---|---|---|
| — | — | — | *No trials run. No market data has been ingested.* | — | — | — |

---

## Amendment log

| Date | Hypothesis | Change | Reason | Made before testing? |
|---|---|---|---|---|
| 2026-08-04 | — | Initial registration of H1–H6 | Phase 1 foundation | Yes — no data existed |
| 2026-08-04 | H2 (and H3/H4/H6 by reference) | **Amendment A1** — added Baseline B3 (Nifty200 Momentum 30, net of 0.22% and LTCG) as a mandatory blocking baseline | The primary signal is already an investable product; the original benchmark was insufficient | Yes — no data ingested, nothing tested |
| 2026-08-04 | H4 | **Amendment A2** — declared the regime definition, data sources, evaluation windows, cost model and pass/fail criteria | H4 was registered with its definition DEFERRED; it must be fixed before testing | Yes — no price series downloaded, nothing plotted |

---

*No backtest has been run. No market data has been ingested. No result in this
file is an observation; every entry is a prediction made in advance.*
