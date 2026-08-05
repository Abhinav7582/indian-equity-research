# Factor Evidence for Indian Equities

**Added: 2026-08-04.** Evidence review supporting (or undermining) the
registered hypotheses. Read alongside [`benchmarks.md`](benchmarks.md).

**Source-type key:** `[P]` primary/official · `[A]` peer-reviewed academic ·
`[I]` institutional research · `[S]` secondary/practitioner.

---

## 1. The frame: assume half of any published effect

Three results govern how every number below should be read.

| Finding | Source | Implication |
|---|---|---|
| A t-statistic of **3.0**, not 2.0, is the minimum bar for a new factor once collective data-mining is accounted for | Harvey, Liu & Zhu, *RFS* 29(1), 2016 `[A]` | The rejection criteria in H1/H2 use 3.0 |
| **~65% of 452 replicated anomalies** fail |t| ≥ 1.96 under consistent methodology | Hou, Xue & Zhang, *RFS* 33(5), 2020 `[A]` | Most published factors are noise |
| Predictor returns decay **~26% out-of-sample, ~58% post-publication** | McLean & Pontiff, *JF* 71(1), 2016 `[A]` | Halve every published effect size before planning around it |

India makes this worse, not better: fewer stocks, shorter reliable history,
and a much thinner peer-reviewed replication literature than the US.

## 2. What survives, and how well it transfers to India

| Factor | Global evidence | India-specific | Confidence for India | v1? |
|---|---|---|---|---|
| **Momentum (12-1)** | Jegadeesh & Titman *JF* 1993; Asness-Moskowitz-Pedersen *JF* 2013; **survived** Hou-Xue-Zhang | NSE studies report the effect present and often stronger than developed markets, with profits concentrated in the **long leg** — convenient for a long-only investor. NSE's own live index exists. | **Medium-High** (existence) / **Low-Medium** (net of Indian costs) | **Yes** |
| **Quality / profitability** | Novy-Marx *JFE* 2013; Asness-Frazzini-Pedersen *RAST* 2019 | NSE publishes Quality 30 indices with reasonable long-run behaviour | Medium | **As a filter** |
| **Low volatility** | Frazzini & Pedersen *JFE* 2014 | NSE Low Volatility indices exist | Medium — **but the published premium needs leverage to harvest.** Unlevered it is lower return with lower risk | **Weighting only** |
| **Value** | Fama-French 1993/2012 | Works better in India than the US in several studies, but is **dominated by sector composition** (PSU banks, metals, oil & gas) | Medium | Secondary, sector-neutral |
| **Size** | Banz 1981 | Largely fails modern replication | Low | **No** — and absent in Nifty 100 anyway |
| **Short-term reversal** | Real gross | — | High confidence it is **destroyed by Indian costs** (STT both legs, flat DP charge) | **No** |

## 3. India-specific sources, and how much weight to give them

**Institutional `[I]` — usable.**
[S&P Dow Jones Indices, *An Index Approach to Factor Investing in India*](https://www.spglobal.com/spdji/en/documents/research/research-an-index-approach-to-factor-investing-in-india.pdf)
studies momentum, quality, value and low volatility on Indian data over
**31 Mar 2012 – 31 Mar 2022**. An index provider has a commercial interest in
factor indices existing, so read it as competent evidence with a known
incentive, not as neutral adjudication.

**Primary `[P]` — the strongest India evidence available.**
NSE's own live index track records. The Nifty200 Momentum 30 has **live**
history from 25 August 2020 and reports 18.65% TR CAGR since its 2005 base
date, but only ~5 years of that is not back-tested. See
[`benchmarks.md`](benchmarks.md) §3.

**Practitioner `[S]` — treat with caution.**
Practitioner backtest guides circulate claiming, for example, an 18-year
NSE study (Dec 2006 – Jun 2025, ~1,700 stocks including delisted names) with
Quality-Momentum at **17.95% CAGR "net"** versus Nifty 50 at 10.42%, and a
stated 4.02% annual tax drag on a Value-Quality variant.

**Why this is not usable as evidence, despite sounding rigorous:**

- It is a **vendor/practitioner blog**, not peer-reviewed, with an obvious
  incentive to make backtesting look attractive.
- "Net" is unverified. Net of what? Which brokerage, which STT vintage,
  whether flat DP charges were modelled at all.
- **No trial count is disclosed**, so no Deflated Sharpe Ratio can be
  computed. Five reported strategies imply an unknown number of unreported
  ones.
- No purged cross-validation, no locked holdout, no parameter-sensitivity
  surface.
- The inclusion of delisted names is genuinely commendable and rare — which is
  precisely why the rest of the methodology needs to be visible before the
  result can be believed.

**How to use it:** as a hypothesis worth testing yourself, and as evidence
that the data can be assembled. Never as a number to plan around. If your own
work reproduces something near it under the H2 rejection criteria, that is
meaningful. If it does not, the difference is probably methodology, not skill.

## 4. What this evidence does and does not support

**Supports:**
- Momentum is the right primary signal for H1. It is the best-evidenced factor
  globally, survived the harshest replication study, and has favourable
  long-leg concentration in India.
- Quality as a *filter* rather than a return source (H3's framing).
- Low volatility for *weighting* rather than selection.

**Does not support:**
- Any expectation of double-digit alpha. The credible expectation is a small
  premium, halved for post-publication decay, then reduced further by Indian
  transaction costs and STCG.
- Any claim that "India is more inefficient so factors work better." This is
  frequently asserted in practitioner writing and is not established by the
  peer-reviewed literature at the strength claimed.

**Directly undermines:**
- Short-term reversal, size, and any high-turnover signal, at this cost base.

## 5. The gap this project must actually fill

The literature answers "does momentum exist in India?" — probably yes, with
wide error bars. It does **not** answer the question that decides this
project:

> Does a 12–15 name, monthly-rebalanced, governance-filtered, regime-overlaid
> momentum portfolio beat the **Nifty200 Momentum 30 index** after Indian
> transaction costs and 20% STCG, out of sample?

No published study answers that, because nobody else has this exact cost and
tax profile. That is why H3, H4 and H6 exist, and why the answer has to be
produced rather than read.

## 6. Reading list, prioritised

**Read before Phase 4:**
- Harvey, Liu & Zhu (2016), *RFS* — the multiple-testing bar
- Hou, Xue & Zhang (2020), *RFS* — what actually replicates
- McLean & Pontiff (2016), *JF* — post-publication decay
- Daniel & Moskowitz (2016), *JFE* — momentum crashes, essential for H4
- Novy-Marx & Velikov (2016), *RFS* — anomalies after trading costs
- S&P DJI, *An Index Approach to Factor Investing in India* `[I]`

**Read before Phase 3:**
- López de Prado, *Advances in Financial Machine Learning* (2018) — purged CV,
  embargo, PBO
- Bailey & López de Prado (2014), *JPM* — Deflated Sharpe Ratio

**Do not spend more time on:** general prediction technique surveys, ML
architecture comparisons, or indicator research. The marginal value there is
approximately zero and the marginal overfitting risk is not.
