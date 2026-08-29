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

**Status:** `NOT_TESTED` — and see the Phase 4 closeout, 2026-08-29. H3 was
registered as a **refinement to a working strategy**. With the base case
negative before costs (trials #2, #3, #6, #7), a quality filter would have to
**create** the edge rather than improve it, which is a far stronger claim than
this hypothesis was written to make. Not withdrawn; not worth a trial at current
odds.
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

**Status:** `NOT_TESTED` — close to moot after the Phase 4 closeout, 2026-08-29.
Weekly rebalancing means more turnover, more charges and more short-term capital
gains tax on an effect that did not survive monthly. Not withdrawn; not worth a
trial at current odds.
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

**Status:** `NOT_TESTED` — and see the Phase 4 closeout, 2026-08-29. Like H3,
H6 was registered as a **refinement to a working strategy**. With the base case
negative before costs, governance exclusions would have to **create** the edge
rather than improve it. Not withdrawn; not worth a trial at current odds.
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

# AMENDMENT A10 — the Nifty 200 extension, declared before the data exists

**Date: 2026-08-23** · **Written before the Nifty 200 roster and TRI have been
downloaded, and therefore before any Nifty 200 result could have been seen.**

## Why this exists

H1 and H2 were both rejected on the **Nifty 100** — the largest, most-covered,
most-arbitraged hundred names on the exchange. Neither result says anything
about the rest of the market, and there is a specific published reason to look
wider: Indian momentum research concentrates in mid-caps, and NSE's own momentum
index draws its constituents from the **Nifty 200**, not the Nifty 100.

This amendment fixes the extension **before** it is run, because the tempting
version of it — take the Nifty 100 output, notice which deciles worked, and
build the Nifty 200 test around them — is selection, and would make whatever
came out worth very little.

## One variable moves

| | Nifty 100 (trials #2, #3) | Nifty 200 (trials #4, #5) |
|---|---|---|
| Universe | Nifty 100, point-in-time | **Nifty 200, point-in-time** |
| Signal | 12-1 momentum | unchanged |
| Deciles | 10 | unchanged |
| Cadence | monthly, first session | unchanged |
| Decision / execution | previous close / next open | unchanged |
| Minimum history | 252 sessions | unchanged |
| Development window | 2015–2021 | unchanged |
| Holdout | 2022–2025, untouched | unchanged |
| Costs | H1 gross, H2 full | unchanged |
| Capital | ₹3,00,000 | unchanged |

**Breadth changes as a consequence, and this is declared rather than hidden.**
The top decile of two hundred names is **twenty** names, not ten. A9's principle
was "H2 trades what H1 tests", and holding that principle constant is what
forces the count to move. The alternative — holding ten names, the top 5% —
would keep breadth constant while changing the rank cut, and would break the
link to H1 that A9 exists to preserve.

Twenty holdings at ₹3,00,000 is ₹15,000 a position and costs **0.616% per full
turnover at one sell order per exit, 0.694% at the measured 1.5, and 0.930% at
three**. All three clear Amendment A7's 1.00% budget, so the change is
permitted. It also reduces the concentration A9 flagged as the cost of ten
names.

## The prediction, registered now so that confirming it means something

The Nifty 100 run produced this decile profile:

```
D8  +0.376%     D9  +0.403%     D10  -0.138%    per month, gross
```

That pattern was **not predicted**. It emerged from the data, which is exactly
why it cannot be acted on from the same data.

**So it is predicted here, in advance, for a universe not yet examined:**

> If the Nifty 100 pattern reflects something real about the top of the momentum
> distribution rather than sampling noise, the Nifty 200 will also show **D8 and
> D9 exceeding D10**.

This costs nothing — it falls out of the same run. But stating it beforehand
turns a coincidence into evidence if it holds, and into a useful negative if it
does not. A pattern that appears in one universe and not another was noise.

**H2 on the Nifty 200 still trades the top decile**, as A9 fixed, and **not** D9.
Moving the universe and the rank cut together would leave any result
unattributable to either.

If the prediction holds, a *later* amendment may propose trading D9, and it will
then rest on two independent observations rather than one. That amendment does
not exist yet and must not be written until the result is in.

## Trial accounting — binding

Two trials, logged as **#4 (H1, Nifty 200)** and **#5 (H2, Nifty 200)**, whatever
they show and including any that is abandoned mid-run.

That brings the register to **five**. This file already records what that costs:
*with 5 trials the chance-expected best Sharpe is 1.19.* Any result from here
must clear a visibly higher bar than trial #2 or #3 faced, and the Deflated
Sharpe denominator is the honest count, not the count of results reported.

## Data required, and not yet held

Neither of these is in the repository, and the run is blocked until both are:

1. **A Nifty 200 constituent roster.** The reconstruction rolls today's roster
   backwards; without a starting point there is nothing to roll.
   `https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv`
   → `data/raw/archive/nse_nifty200_constituents/nse_nifty200_constituents_YYYY-MM-DD.csv`
2. **The Nifty 200 Total Return Index**, 2015–2026, from
   `niftyindices.com/reports/historical-data`, Total Returns Index Values,
   Broad Market Indices → NIFTY 200
   → `data/raw/indices/nifty200_tri/nifty200_tri_YYYY.csv`

The archive holds `nifty200_momentum30` and a 75:25 blend, but **not** a plain
Nifty 200 TRI. Benchmarking against the momentum index instead would be
comparing a momentum strategy to a momentum strategy, and would answer a
different question.

## What is already known about the reconstruction

The press releases parse. Forty-eight substantive Nifty 200 changes were
extracted from the existing archive, running 2013 to 2026, and **forty-four have
a net size change of exactly zero** as a fixed-size index requires.

Four do not, and must be resolved before any result is recorded:

```
2016-04-01  ind_prs22022016_2.pdf   net +2
2020-06-26  ind_prs10062020.pdf     net -5
2023-09-29  ind_prs17082023.pdf     net +1
2024-08-30  ind_prs23082024_1.pdf   net -1
```

The last two are the **TATAMTRDVR** pair already understood from the Nifty 100
reconstruction — Tata Motors' differential-voting share entering and leaving as
a constituent in its own right. The first two are not yet explained.

**The run is conditional on `roll_back` reporting zero unapplied changes**, the
same standard the Nifty 100 had to meet. A reconstruction that does not close is
not a universe, and no result from it enters this register.

## What would make this amendment dishonest

Changing the decile traded, the breadth, the window or the signal **after**
seeing a Nifty 200 result and reporting the second number as though it were the
first. If any of those changes, the original stays in the register with its
outcome and the new one is logged beneath it.

---

## A10 OUTCOME — BLOCKED ON DATA QUALITY, 2026-08-29

**Trials #4 and #5 were not run.** The Nifty 200 universe could not be
reconstructed to the standard the Nifty 100 met, and A10 made the run
conditional on exactly that. No trial budget was spent; the register stays at
three.

### What was attempted

Both datasets arrived and both are sound. The Nifty 200 TRI covers 2004-2026,
5,626 levels, no gaps over the test window, and every session the Nifty 100 TRI
has. The roster is 200 constituents as at 2026-08-29.

**Attempt 1 — parse the "Nifty 200" sections directly.** 51 changes parsed,
**13 could not be applied**, nine of them inside the 2016-2021 test window, and
the constituent count drifted from 200 to 208.

**Attempt 2 — build it as NSE does, `Nifty 100 ∪ Nifty Midcap 100`.** The
definitional identity was verified exact on the real rosters: no Nifty 100 name
sits outside the Nifty 200, and the remainder is exactly 100 names. The union
also self-checks, since it must total 200 on every date.

It failed too: **14 unapplied changes and 31 of 38 snapshots off 200**, ranging
from 187 to 205. The Nifty 100 half reconstructs perfectly; every failure is in
the mid-cap half.

### The actual cause

Not the parser, and not the union. **The press-release archive is incomplete in
its early years.**

```
releases held, per year
  2015   18        2019   84        2023   41
  2016   15        2020   61        2024   93
  2017   30        2021   47        2025  165
  2018   68        2022   42        2026   82 (to August)
```

NSE did not publish ten times more index releases in 2025 than in 2015. Eight
months between 2015 and 2017 have **zero** releases on disk. The failures
cluster there — 2015-03-27, 2015-09-28 twice, 2015-10-19, 2016-09-30,
2017-09-29 — with the remainder scattered later.

**Why the Nifty 100 survived the same gaps.** It turns over roughly two names
per semi-annual review, and the reviews that matter were captured. A 200-name
universe carries several times that churn plus intra-review maintenance
changes, and those are precisely what the thin years are missing. The Nifty 100
reconstruction was not more robust; it was less demanding of the archive.

### What this does and does not mean

It does **not** mean momentum is absent in mid-caps. That question is untested
and remains open.

It does mean **this archive cannot answer it honestly**, and that the Nifty 100
is currently the only universe this project can reconstruct to its own standard.

### What would unblock it

1. **Backfill the 2015-2017 press releases** from `niftyindices.com/media`.
   Likely fixes roughly half the failures; the 2018+ ones have another cause
   not yet diagnosed.
2. **A licensed historical constituent series**, which removes the
   reconstruction problem entirely rather than patching it.
3. Nothing else. Lowering the standard is forbidden by this amendment and by
   the reasoning in Amendment A5: a universe that does not close is not a
   universe, and a result from one is not evidence.

**The code is kept.** `reconstruct_union` and the `Nifty Midcap 100` spec are
correct and tested; they are blocked on inputs, not on logic. The union's
self-check worked exactly as designed — it detected the drift immediately
instead of serving a plausible-looking universe that was quietly wrong.

---

# AMENDMENT A11 — three routes past the Nifty 200 blocker, declared in advance

**Date: 2026-08-29** · **Written before any of the three has been run, and
before the Nifty 50 roster has been downloaded.**

## Why this exists

A10 ended blocked: the Nifty 200 will not reconstruct, and the cause is an
incomplete press-release archive rather than a bug. Three routes past it are
declared here. **None may be run before this amendment is committed**, and the
rules below are fixed now precisely because the tempting version of each is to
decide what counts as success after seeing the answer.

Cheap tests already ruled two ideas out, and they are recorded so nobody
re-tries them:

* **Starting the study later does not help.** Rolling back only to 2021 still
  leaves 3 unapplied changes; to 2018, nine. The gaps are spread across the
  period, not confined to the thin 2015-2017 years.
* **Backfilling 2015-2017 releases is therefore necessary but not sufficient**,
  and is not pursued on its own.

---

## Route 1 — a sensitivity band on the Nifty 200

**The measured doubt.** Thirteen changes cannot be applied. They implicate
exactly **twenty securities**, 5.3% of the 380 that were ever members, and the
constituent count overshoots by at most 8 on 200 — 4%.

```
ABBOTINDIA  BAJAJFINSV  BBTC      CENTRALBK  CESC
CRISIL      GODREJAGRO  HINDCOPPER IDEA      INDIANB
IREDA       MFSL        NATIONALUM NIITTECH  RELCAPITAL
TATACOMM    TRENT       VAKRANGEE  VGUARD    WABAG
```

That list is determined by the reconstruction alone. **No return was read to
produce it**, so fixing it here costs nothing and prejudges nothing.

**The design.** H1 and H2 are each run twice on the Nifty 200:

* **Band A** — the full reconstruction, as it stands.
* **Band B** — the same, with those twenty securities excluded for the entire
  period.

**The binding rule, fixed now.** If both bands reach the same verdict on every
rejection criterion, that verdict stands and the reconstruction error is
declared **not load-bearing**. If they differ on **any** criterion, the result
is **INCONCLUSIVE** and neither band is reported as the answer.

Choosing the more favourable band afterwards is forbidden. So is widening the
excluded set until the bands agree.

**Why this is not moving the goalposts.** A10's gate was about **data quality**,
and **no Nifty 200 return has been observed**. Amending a method before any
result exists cannot be fitting the rules to a result — which is the specific
thing the gate protects against. Had a return been seen, this amendment would
not be permissible.

**Trial accounting.** Following Amendment A4's precedent for the delisting
bands: **one trial per hypothesis**, reported as a band rather than as two
selectable numbers. Trials **#4 (H1, Nifty 200)** and **#5 (H2, Nifty 200)**.

---

## Route 2 — size tiers, using the best-documented universes in the archive

**The question the Nifty 200 was for** is whether momentum lives further down
the size curve. That can be asked without the Nifty 200 at all.

The Nifty 100 splits exactly into the **Nifty 50** and the **Nifty Next 50**,
and those two are the cleanest-parsing indices in the entire archive:

```
Nifty 50        25 changes,  2 with non-zero net size
Nifty Next 50   35 changes,  1
Nifty 100       37 changes,  4      (reconstructs clean)
Nifty 200       51 changes,  4      (does not)
```

**The design.** 12-1 momentum, monthly, gross, 2016-2021, identical to trial #3
in every respect except the universe. Measured **within each tier separately**.

**Rank IC is the primary metric, not deciles.** Fifty names give buckets of
five, which is too thin for a decile mean to mean anything. The rank IC uses
all fifty every month and is the same statistic H1 was registered on. Quintiles
are reported alongside for shape, and are secondary.

**The prediction, registered now:**

> If momentum lives further down the size curve, the mean rank IC in the
> **Nifty Next 50** will exceed that in the **Nifty 50**.

**The criteria.** The comparison is informative only if the smaller tier's IC is
both higher *and* itself distinguishable from zero: Next 50 IC > Nifty 50 IC,
**and** Newey-West |t| ≥ 3.0 on the Next 50 IC. Failing the second while passing
the first is a **suggestive negative**, recorded as such and not as support.

**Trial accounting — one trial, #6**, with a binding rule: **neither tier's IC
may be reported as a standalone finding.** The registered claim is the
difference between them. Reporting the better tier alone would be selecting one
of two measurements after seeing both, which is exactly what a single-trial
count must not be allowed to conceal.

**Data required and not yet held:** the Nifty 50 and Nifty Next 50 constituent
rosters. Both are checkable against what we already have — their union must
equal the Nifty 100 roster exactly, and each must hold 50 names.

---

## Route 3 — adjudicate the thirteen changes by hand

The honest fix rather than a bound on the damage, and the method this project
has already used successfully: the September 2021 Nifty 100 reconstitution was
recovered exactly this way and is recorded in
`data/reference/index_changes_manual.md`.

Each of the thirteen is researched against NSE's record, and what actually
happened to that security on that date — merger, delisting, suspension,
migration between indices — is written down with its evidence.

**This reads no returns and is not a trial.** It is a data-quality repair.

**If it closes the reconstruction, Route 1 becomes unnecessary** and the Nifty
200 study runs with no caveat at all. Route 1 exists because partial success is
the likely outcome, not because the repair is optional.

**A rule for the register, binding.** An entry may record only what a document
says. "This name must have left around here because the count is wrong" is an
inference from the reconstruction failing, and writing it down would make the
reconstruction close by construction — it would be fitting the data to the
method. Any change that cannot be evidenced stays unapplied and feeds Route 1's
excluded list instead.

---

## What would make this amendment dishonest

Running any route before this is committed. Reporting Band A or Band B
selectively. Reporting one size tier alone. Adding names to the excluded list
until the bands agree. Writing an unevidenced entry into the manual register.

---

# AMENDMENT A12 — test the signal NSE actually uses

**Date: 2026-08-29** · **Written before the signal was implemented and before
any risk-adjusted result was computed.**

## Why this exists

Every trial so far has varied the universe, the breadth, the costs, the tiers
and the window, and has held **one thing constant: raw 12-1 momentum**. Four
trials, one signal.

Scoring Baseline B3 revealed that the investable momentum product returned
**25.10% a year** over exactly the window in which our momentum strategy
returned 10.85%. Whatever went wrong, "momentum did not work in India in
2016–2021" is not it.

The most likely remaining explanation is that **we tested a different signal
from the one that worked.**

## What NSE actually does

Verified against NSE's published methodology rather than recalled:

* The score comes from **6-month and 12-month price returns, each divided by
  volatility** — a momentum *ratio*, return over standard deviation.
* The two ratios are normalised and combined into one score.
* The top **30** of the **Nifty 200** are selected.
* Weights are free-float market cap **multiplied by** the momentum score,
  capped at the lower of 5% or 5× the free-float weight.
* Rebalanced **semi-annually**, June and December.

Our signal is none of that. It is a raw twelve-month return with one month
skipped, no volatility adjustment, equal weights, ten names, monthly.

## What is tested, and what is not

**Tested:** NSE's *signal*, as published — 6-month and 12-month returns each
divided by trailing volatility, cross-sectionally normalised and averaged.

**Deviations, forced by data or by power, and declared here:**

| | NSE | This test | Why |
|---|---|---|---|
| Universe | Nifty 200 | **Nifty 100** | The Nifty 200 does not reconstruct (A10 outcome) |
| Cadence | semi-annual | **monthly** | 70 observations against ~12; and it matches trial #3 |
| Weighting | free-float × score, capped | **not modelled** | This is an IC study, not a portfolio |
| Skip month | none | **none** | Follows NSE, and differs from our 12-1 |

**Not tested:** whether NSE's *portfolio* is reproducible. Weighting needs
free-float market cap, which this project does not hold.

**One consequence stated plainly.** Because the skip month goes as well as the
volatility adjustment, a positive result attributes to **NSE's signal as a
whole**, not to risk-adjustment specifically. Isolating the two components would
be a further trial and is not claimed here.

## A simplification, and why it is exact

NSE converts the averaged z-score into a positive weighting score. **That
transform is monotonic, and rank correlation is invariant to any monotonic
transform**, so it cannot change the IC by even a rounding error. It is
therefore omitted, and the omission costs nothing — it would matter only for
weighting, which is not modelled.

## The specification — binding

| Parameter | Declared value |
|---|---|
| Universe | Point-in-time Nifty 100 |
| Signal | mean of the cross-sectional z-scores of (6m return ÷ σ) and (12m return ÷ σ) |
| σ | Annualised standard deviation of daily returns over the trailing 252 sessions |
| Windows | 126 sessions (6m) and 252 sessions (12m), ending on the decision date |
| Skip | **None**, following NSE |
| Minimum history | 252 sessions |
| Cadence | Monthly, first session |
| Metric | Mean Spearman rank IC vs forward one-month excess return, Newey-West t |
| Window | 2015–2021 development; **holdout untouched** |
| Costs | **Gross** — this is H1's question, not H2's |

Everything else is identical to trial #3.

## The registered prediction

> If the signal is the explanation for trials #2 and #3, the risk-adjusted score
> will produce a mean rank IC **materially above the raw 12-1 figure of
> +0.0378**.

**Criteria, fixed now:**

| | Required for support |
|---|---|
| Risk-adjusted IC > raw 12-1 IC (+0.0378) | necessary |
| Newey-West \|t\| ≥ 3.0 on the risk-adjusted IC | necessary |

Both, or it is not support. Higher-but-not-significant is a **suggestive
positive** — the same standing A11 gave the mirror-image result in trial #6, and
recorded as such rather than as encouragement.

**And an honest limit.** Even full support would not explain the whole B3 gap.
NSE's 25.10% comes from signal, universe, concentration and weighting together,
and this test moves one of the four.

## Trial accounting

**One trial, #7.** Taking the register to five spent trials. This file already
records the cost: at five trials the chance-expected best Sharpe is 1.19.

If this fails, then across **two signals**, three universes and every cost
treatment, the archive says there is nothing here that this account can reach —
and Phase 5 is the answer rather than a consolation.

## What would make this amendment dishonest

Tuning the lookback windows, the volatility definition, or the combination
weights after seeing an IC. Reporting a component (6m alone, 12m alone) that was
not registered. Running it on the holdout.

---

## Trial register

Every backtest configuration executed against project data is recorded here,
including abandoned ones. This register is the denominator in the Deflated
Sharpe Ratio.

| # | Date | Hypothesis | Configuration | Data snapshot | Commit | Outcome |
|---|---|---|---|---|---|---|
| **1** | 2026-08-06 | **H4** | A2 regime rule as declared: Nifty 100 < 200d SMA AND India VIX > trailing 756d 80th pct; monthly evaluation; 1-period lag; 0.55% round trip; 20% STCG; cash at 0% | NSE Indices + NSE: Nifty 100 PR 2003-2026, Momentum 30 TRI 2005-2026, India VIX 2010-2026, Momentum30+G-Sec 75:25 2011-2026 | `5fed927` | **REJECTED** (see below) |
| **2** | 2026-08-23 | **H2** | A9 as declared: 10 holdings, top decile of 12-1 momentum in the point-in-time Nifty 100, equal weight, monthly, decided on previous close and filled at next open, ₹3,00,000, 1 sell order per exit | Bhavcopy 2015-2026 back-adjusted; NSE corporate actions; reconstructed point-in-time Nifty 100; Nifty 100 TRI | `d36ea3e` | **REJECTED** (see below) |
| **3** | 2026-08-23 | **H1** | As registered: 12-1 momentum deciles within the point-in-time Nifty 100, forward one-month excess return over the Nifty 100 TRI, monthly, **gross** | Same as trial #2 | `5aff43b` | **REJECTED** (see below) |
| **7** | 2026-08-29 | **A12** | NSE's own momentum signal: 6m and 12m returns each ÷ trailing volatility, cross-sectionally standardised and averaged, no skip. Nifty 100, monthly, gross. Identical to #3 except the signal | Same as trial #2 | *pending* | **NOT SUPPORTED** (see below) |
| **6** | 2026-08-29 | **A11 Route 2** | Size tiers: mean rank IC of 12-1 momentum **within** the Nifty 50 against **within** the Nifty Next 50, monthly, gross, 2016-2021, identical to #3 except the universe | Bhavcopy 2015-2026 back-adjusted; Nifty 50 and Nifty 100 rosters; Nifty 100 TRI | *pending* | **SUGGESTIVE NEGATIVE** (see below) |

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

### Trial #2, ADDENDUM — Baseline B3 scored at last, 2026-08-29

**Amendment A1 made the NIFTY 200 Momentum 30 index a blocking baseline on
2026-08-04.** Trial #2 was scored against the Nifty 100 TRI only. **The check
was never run**, although the data had been in
`data/raw/indices/nifty200_momentum30/` since before the trial. This addendum
runs it.

Over exactly the trial #2 window, 2016-02-09 to 2021-12-31, on ₹3,00,000:

| | Final | CAGR | After terminal LTCG | CAGR |
|---|---:|---:|---:|---:|
| H2 strategy, gross | ₹6,50,655 | 14.04% | ₹6,22,448 | 13.19% |
| **H2 strategy, net of everything** | **₹5,50,426** | **10.85%** | ₹5,34,748 | 10.31% |
| Nifty 100 TRI less 0.20% — **B1** | ₹7,61,583 | 17.13% | ₹7,19,510 | 16.01% |
| **NIFTY200 Momentum 30 less 0.22% — B3** | **₹11,22,652** | **25.10%** | ₹10,35,445 | 23.40% |

```
H2 net vs B1    -6.28%/yr   (-5.16% like-for-like post-tax)
H2 net vs B3   -14.25%/yr  (-12.55% like-for-like post-tax)
```

**The investable momentum product more than doubled the strategy's final
value.** ₹11.2 lakh against ₹5.5 lakh.

**What this does to trial #2.** The verdict is unchanged — H2 was rejected
against criteria naming the Nifty 100 TRI, and it fails B3 far more heavily. But
the **explanation** recorded in `docs/h2_result.md` is now doubtful. That
document says the signal did not work in this window. Something recognisably
momentum returned **25.1% a year** in this window. The failure is far more
likely to be in our specification than in the market.

**A note on the post-tax column, and why it does not become the criterion.**
`h2_experiment.py`'s docstring claimed the benchmark was net of terminal LTCG;
the code applied only the expense ratio. The docstring has been corrected to
match the code. The post-tax figures are reported as a **sensitivity, not a
benchmark change** — lowering a benchmark after failing it is precisely the move
this register exists to prevent, and it is not being made. Every verdict holds
under both readings.

**Process failure, recorded plainly.** An amendment declared a mandatory
comparison, the data was present, and nothing in the pipeline checked it had
been made. That is the largest process failure in this project to date. A guard
now refuses to print a verdict when a registered baseline is missing from the
result table.

---

### The statistical power available, measured 2026-08-29

Given the observed effect sizes and IC volatility, how long a sample is needed
to clear the registered bar of **t ≥ 3.0**?

| Study | IC | t | n | Months for t=3 | **Years** |
|---|---:|---:|---:|---:|---:|
| H1, Nifty 100 (#3) | 0.0378 | 1.47 | 70 | 292 | **24.3** |
| Nifty 50 (#6) | 0.0360 | 1.14 | 70 | 485 | **40.4** |
| Nifty Next 50 (#6) | 0.0414 | 1.57 | 70 | 256 | **21.3** |

*Back-solves the standard error from the reported HAC t; assumes the effect size
and IC volatility persist.*

**The development window is 5.9 years.** Detecting an effect of this magnitude
at this bar needs **twenty to forty years** of monthly observations.

This does not make the criteria wrong. The t ≥ 3.0 threshold follows Harvey,
Liu & Zhu (2016) and exists because a t of 2 across a multiple-tested literature
means little. But it must be read alongside every rejection in this register:

> **These hypotheses were registered with a bar the available data cannot clear
> for an effect of this size — whether or not the effect is real.**

A rejection here is therefore substantially a statement about sample size, and
not only about the market. Extending the price archive backwards to ~2005 would
roughly double the sample and move t from 1.47 toward 2.1 — closer, still short.

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

### Trial #6 detail — A11 Route 2, size tiers

**Run:** 2026-08-29 · 70 monthly rebalances, 2016-2021, gross. Holdout
untouched.

**Both universes reconstructed cleanly**, to the standard the Nifty 200 could
not meet:

```
Nifty 50        0 unapplied, sizes [50, 51]
Nifty 100       0 unapplied, sizes [100, 101]
Nifty Next 50   0 unapplied, sizes [50, 51]      (derived, see below)
```

Every size deviation is `TATAMTRDVR`, the security already understood from the
Nifty 100 reconstruction — and the pattern corroborates independent reporting:
the DVR left the **Nifty 50** in September 2017 but stayed in the Nifty 100
until 2020, so the derived Next 50 correctly holds 51 in exactly those windows.

**Method note, recorded because it was a decision.** The Nifty Next 50
reconstructed *directly* from its own press-release sections leaves **six**
unapplied changes and drifts to 59 members. It was therefore built as **Nifty
100 minus Nifty 50**, both of which reconstruct with zero unapplied. The
containment was verified at all 33 snapshots, so the subtraction can never
produce names the larger index did not hold. **This decision reads no returns**
and was taken before any tier IC was computed, which is why it is a method note
rather than a new amendment.

**The result:**

| | Nifty 50 | Nifty Next 50 |
|---|---:|---:|
| Mean rank IC | **+0.0360** | **+0.0414** |
| Newey-West \|t\| | 1.14 | **1.57** |
| Rebalances | 70 | 70 |

| Quintile, monthly excess, gross | Nifty 50 | Nifty Next 50 |
|---|---:|---:|
| Q1 | −0.575% | −0.336% |
| Q2 | −0.326% | −0.507% |
| Q3 | −0.209% | −0.516% |
| Q4 | +0.063% | +0.119% |
| Q5 | +0.089% | +0.231% |

**Scored against the prediction registered in A11:**

| | Observed | Required | |
|---|---|---|---|
| Smaller tier scores higher | +0.0054 | > 0 | PASS |
| Next 50 \|t\| distinguishable from zero | 1.57 | ≥ 3.0 | **FAIL** |

**Verdict: SUGGESTIVE NEGATIVE.** The prediction's direction held and its
substance did not. A11 fixed in advance that this combination is not support,
and it is not being read as support.

**Why the direction is not encouraging either.** The gap is **+0.0054** on ICs
of about 0.04 — a 15% relative difference, nowhere near enough to explain why
H2 lost 3.32% a year gross. And the three measurements now available sit in one
narrow band:

```
Nifty 50    +0.0360      (trial #6)
Nifty 100   +0.0378      (trial #3)
Next 50     +0.0414      (trial #6)
```

The Nifty 100 falls between its two halves, as it arithmetically should — an
internal consistency check that passes. Across the whole size range this
archive can measure, 12-1 momentum is **weak, similar, and never
distinguishable from noise**.

**What this closes.** The most plausible explanation for trials #2 and #3 was
that the Nifty 100 is too large-cap. Moving down one tier moves the IC by
0.005 and leaves the t-statistic at 1.57. That does not rule out a real effect
in genuine mid- or small-caps, which are outside this archive's reconstructable
range — but it removes the nearest and most tempting escape hatch, and it does
so on universes that reconstruct perfectly rather than ones that do not.

**What it does not close.** Neither tier was *tested* for tradeability. This is
H1's question, not H2's, and it is gross.

---

### Trial #7 detail — A12, NSE's own momentum signal

**Run:** 2026-08-29 · Nifty 100, 70 monthly rebalances, 2016-2021, gross.
Holdout untouched. Identical to trial #3 in every respect **except the signal**
— same universe, same dates, same forward returns, same statistic, the same
lines of code from the ranking onward.

| | raw 12-1 | risk-adjusted |
|---|---:|---:|
| Mean rank IC | **+0.0378** | **+0.0239** |
| Newey-West \|t\| | 1.47 | **1.04** |
| D10 − D1 per month | +0.461% | **+0.042%** |
| Monotonicity | +0.758 | **+0.394** |

**Scored against the prediction registered in A12:**

| | Observed | Required | |
|---|---|---|---|
| Beats the raw 12-1 IC | +0.0239 vs +0.0378 | higher | **FAIL** |
| \|t\| ≥ 3.0 | 1.04 | ≥ 3.0 | **FAIL** |

**Verdict: NOT SUPPORTED. The signal is not the explanation.**

NSE's definition scored **worse** than ours on this universe — lower IC, lower
t, a decile spread of four basis points a month against forty-six, and
monotonicity roughly halved. The prediction was not merely unmet; it was
inverted.

**A verification that passed quietly and is worth stating.** The raw 12-1 signal
was **re-measured** in this run rather than quoted, with a check that would
print a warning if it disagreed with trial #3 by more than 0.0005. It came back
at exactly **+0.0378**. The harness reproduces the earlier trial, so the
comparison is like-for-like and the difference is genuinely the signal.

### What now explains the B3 gap — and what does not

Four candidate explanations for the momentum index returning 25.10% while our
strategy returned 10.85%:

| Candidate | Status |
|---|---|
| **Signal** — raw vs risk-adjusted | **Ruled out** by this trial. Theirs is worse here |
| **Universe** — Nifty 100 vs Nifty 200 | Largely ruled out by trial #6: one tier down moved the IC by 0.005 |
| **Concentration and weighting** — 30 names, free-float × score, capped | **Untested.** No free-float data |
| **Cadence** — semi-annual vs monthly | Untested; lower turnover, lower cost, different holding period |

Worth recording alongside: the NIFTY 200 Momentum 30 index beat **its own parent
universe** — the Nifty 200 TRI returned 17.50% over the same window against the
momentum index's 25.38%, a genuine **+7.88% a year from momentum selection**.
Momentum selection worked in India in this window. It did not work in our hands,
and after trial #7 the reason is not the signal definition.

### The position after seven trials

```
raw 12-1, Nifty 100      IC +0.0378   t 1.47
raw 12-1, Nifty 50       IC +0.0360   t 1.14
raw 12-1, Next 50        IC +0.0414   t 1.57
risk-adjusted, Nifty 100 IC +0.0239   t 1.04
```

**Two signals, three universes, every cost treatment.** Every measurement lands
between 0.024 and 0.041 with a t-statistic between 1.04 and 1.57, and the
power calculation says this data would need twenty to forty years to resolve an
effect that size.

That is not a near miss. It is a consistent reading that **this archive cannot
find a tradeable momentum edge for this account**, and the two most plausible
escapes — a bigger universe and a better signal — have now both been tested and
neither helped.

What remains untested is weighting and concentration, which needs free-float
market cap this project does not hold, and which A7's ₹3,00,000 breadth budget
would constrain heavily even if it did.

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
| 2026-08-29 | H1/H2 (signal) | **Amendment A12** — test **NSE's own momentum signal**: 6-month and 12-month returns each divided by trailing volatility, cross-sectionally normalised and averaged, no skip month. Nifty 100, monthly, gross, everything else identical to trial #3. Registered prediction: the risk-adjusted IC exceeds the raw 12-1 figure of +0.0378, **and** its own \|t\| ≥ 3.0. Both, or it is a suggestive positive rather than support. Trial #7 | Four trials varied universe, breadth, costs, tiers and window while holding **one signal constant**. Baseline B3, scored at last, returned 25.10%/yr over exactly the window our strategy returned 10.85% — so "momentum did not work" is not the explanation, and the likeliest remaining one is that we tested a different signal from the one that worked. Methodology verified against NSE's published document rather than recalled | Yes — signal not implemented, no risk-adjusted result computed |
| 2026-08-29 | H1 and H2 (universe, method) | **Amendment A11** — declared three routes past A10's blocker. **Route 1:** run the Nifty 200 study as a two-band sensitivity, full reconstruction against one excluding the twenty implicated securities, with disagreement on any criterion forcing **INCONCLUSIVE** rather than a choice. **Route 2:** ask the size question directly on the Nifty 50 versus Nifty Next 50, the two cleanest-parsing indices in the archive, with rank IC primary and the prediction that the smaller tier scores higher registered in advance. **Route 3:** hand-adjudicate the thirteen unapplied changes, evidence-only. Trials #4, #5 (bands) and #6 (tiers) | A10 ended blocked on data quality with no Nifty 200 return observed, so amending the method now cannot be fitting rules to a result — the distinction the gate exists to protect. Two cheaper ideas were tested and ruled out first and are recorded so they are not retried: starting the study later leaves 3 unapplied changes even from 2021, and backfilling 2015-2017 releases is therefore necessary but not sufficient | Yes — no route run, Nifty 50 roster not yet downloaded, no Nifty 200 return ever observed |
| 2026-08-23 | H1 and H2 (universe) | **Amendment A10** — declared the **Nifty 200** extension: one variable moves, the universe; signal, deciles, cadence, window, holdout and costs all unchanged. Breadth follows the decile (20 names, not 10) to keep A9's "H2 trades what H1 tests" principle intact, and clears A7 at 0.616–0.930%. Registered **in advance** the prediction that D8 and D9 will again exceed D10, so a replication counts as evidence and a non-replication says the Nifty 100 pattern was noise. H2 still trades D10, **not** D9. Two trials, #4 and #5 | H1 and H2 were rejected on the largest, most-arbitraged hundred names, which says nothing about the rest of the market; Indian momentum research concentrates in mid-caps and NSE's own momentum index draws from the Nifty 200. The tempting version — build the Nifty 200 test around whichever deciles worked on the Nifty 100 — is selection, so the design is fixed before the roster and TRI have even been downloaded | Yes — the two required datasets are not in the repository, so no Nifty 200 result could have been seen |
| 2026-08-23 | H2 (portfolio specification) | **Amendment A9** — declared H2's unstated parameters: **10 holdings** (the top decile), equal weight, monthly on the first session, decided on the previous close and filled at the next open, 252-session minimum history, development window 2015–2021 with the 2022–2025 holdout untouched. Logged as **one** trial; no breadth sweep | H2 said "the highest-ranked momentum names" without saying how many, which changes the answer. Ten because H1's criteria are written about decile 10 — holding twenty would test a different portfolio and could not say whether H1's effect is tradeable — and because it is the cheapest breadth A7 permits (0.458%–0.616% per full turnover across every execution assumption). Both reasons read no returns | Yes — momentum signal not yet implemented, no stock-level backtest run |
| 2026-08-23 | H2 (cost model) | **Amendment A8** — corrected the DP charging unit from "per sell scrip" to **per sell order**, verified against two Groww contract notes and reconciled to the paisa against the funds ledger. Set a standing rule that any cost parameter not checked against a real settled transaction is marked documented-only | The registered text stated Zerodha's rule, not the one this account is charged under. A security sold in two orders on one day is charged twice. The correction is weakly **stricter** for every possible execution and strictly stricter whenever an exit splits, so it can only make H2 harder to pass — which is the only direction a pre-registered document may be corrected in without the edit being indistinguishable from fitting the rules to a result | Yes — no hypothesis tested on stock-level data; the correction raises modelled costs |
| 2026-08-18 | all (portfolio construction) | **Amendment A7** — set a **portfolio breadth budget**: no configuration may be tested whose modelled cost of one full turnover exceeds **1.00% of capital**, which at ₹3,00,000 rules out 100 equal-weight holdings (1.402%) and 50 (0.852% at one order per exit, 1.638% at three). Every result must report the holdings count and the assumed sell orders per exit | Two independent methods agree the ₹3L/100-name configuration is uneconomic before any signal is considered: this project's own engine measured DP at 48.5% of all charges over 11 years, and a broker-tariff analysis reached the same conclusion from first principles. The cost model has since been validated to the paisa against real contract notes. Setting the budget from cost arithmetic — which reads no returns — costs no trial budget and removes the temptation to keep a wide book because one backtest liked it | Yes — no hypothesis tested on the real universe; breadth chosen on cost, not performance |

---

*Every hypothesis in this file was registered before the data to test it
existed. **Five** trials have since been run and are recorded in the trial
register — **#1 H4**, **#2 H2**, **#3 H1** all rejected, **#6** a suggestive
negative on the size question, and **#7** not supported on the signal question —
and the price archive runs 2015-2026. Trials **#4 and #5 were never spent**: the
Nifty 200 universe would not reconstruct. No result has been observed for **H3,
H5 or H6**. The declared holdout, 2022-01-01 to 2025-12-31, remains
**untouched**.*

*Three rejections is not a failure of the project. It is the project working:
each was rejected against criteria fixed before the data existed, and none
required an argument about what the criteria should have said.*

*This closing note previously read "No backtest has been run. No market data
has been ingested." Both statements were true when written and had quietly
stopped being true. A pre-registration whose own status line is stale is
worthless as a record, so the status is now stated specifically enough to go
out of date visibly rather than silently.*
