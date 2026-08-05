# Benchmarks: The Real Bar

**Added: 2026-08-04.** Findings from a review of India's investable factor
indices. This document changes what this project must beat, and it is the
single most decision-relevant page in `docs/`.

---

## 1. The problem in one paragraph

The primary signal registered in H1 is **12-1 momentum on a Nifty 200
universe**. NSE already publishes an index that does exactly this — the
**Nifty200 Momentum 30** — and at least five asset managers sell it as an ETF
or index fund for **0.22%–0.30% a year**.

So the honest benchmark is not "the Nifty 100 index fund." It is *"the
momentum factor, implemented professionally, at 0.22%, held long enough to
qualify for LTCG."* Every hour spent building must be justified against a
product you can buy this afternoon.

## 2. Investable factor vehicles in India (as of 2026-08-04)

| Index | Vehicle | Expense ratio |
|---|---|---|
| Nifty200 Momentum 30 | Aditya Birla Sun Life ETF (`MOMENTUM`) | **0.22%** |
| Nifty200 Momentum 30 | Motilal Oswal ETF (`MOMOMENTUM`) | 0.30% |
| Nifty200 Momentum 30 | HDFC ETF (`HDFCMOMENT`) | 0.30% |
| Nifty200 Momentum 30 | ICICI Prudential ETF (`MOM30IETF`) | 0.30% |
| Nifty200 Momentum 30 | UTI Index Fund (allows SIP, no demat needed) | see AMC factsheet |

Source: fund and exchange listings, retrieved 2026-08-04 `[S]`. **Verify the
current expense ratio and AUM on the AMC factsheet before acting** — ratios
change and small ETFs carry liquidity risk.

NSE also publishes investable-index versions of quality (`Nifty100 Quality
30`, `Nifty200 Quality 30`), low volatility (`Nifty100 Low Volatility 30`),
alpha (`Nifty Alpha 50`), and several **multifactor** combinations
(`Nifty500 Multifactor MQVLv 50`, `Nifty500 Multicap Momentum Quality 50`,
`Nifty Total Market Momentum Quality 50`). In other words: every factor
combination this project might plausibly discover already exists as a
product.

## 3. Index performance, and the caveat that matters

**Nifty200 Momentum 30**, from the NSE Indices factsheet dated 31 July 2026
`[P]`:

| Horizon | Total return |
|---|---|
| Since inception (base date 1 Apr 2005) | **18.65% CAGR** |
| 5 years | 11.28% CAGR |
| 1 year | **+1.85%** |
| Year to date | **−1.29%** |
| 5-year annualised std. deviation | ~19.6% |

**Two caveats, both essential.**

1. **The index launched on 25 August 2020.** Everything before that is
   **back-tested**, constructed with hindsight about which rules worked.
   Roughly three-quarters of the headline "since inception" record is
   simulation. Treat the ~5 years of live history as the evidence, and the
   rest as an illustration.
2. **Momentum is currently in a flat-to-negative stretch** (+1.85% over one
   year, −1.29% YTD). This is normal and expected — see
   [`factor_evidence.md`](factor_evidence.md) on momentum crashes — but it
   means anyone starting now should expect the possibility of years of
   underperformance before any premium appears, if it appears.

## 4. The hurdle, computed

Assume the DIY system and the ETF capture the **same gross momentum return
`G`**. They differ only in costs and tax treatment.

| | Momentum ETF | DIY system (manual execution) | DIY system (Groww API) |
|---|---|---|---|
| Management / subscription | 0.22% | 0.00% | **2.36%** (₹7,066 on ₹3L) |
| Trading costs | inside the fund | **1.32%** (monthly rebalance, ~240% turnover) | 1.32% |
| **Annual cost drag** | **0.22%** | **1.32%** | **3.68%** |
| Tax on gains | **12.5% LTCG, deferred** while held | **20% STCG, realised annually** | 20% STCG, annually |

Worked at a 15% gross return:

| | ETF | DIY manual | DIY with API |
|---|---|---|---|
| Net pre-tax | 14.78% | 13.68% | 11.32% |
| Net post-tax (annual realisation at 20%; ETF tax deferred) | **14.78%** | 10.94% | 9.06% |
| **Shortfall vs ETF** | — | **−3.84 pp/yr** | **−5.72 pp/yr** |

> ### The bar
>
> **The DIY system must beat the Nifty200 Momentum 30 index by roughly
> 3.8 percentage points a year (manual execution), or 5.7 points (with the
> Groww API), simply to draw level.**
>
> Not to add value. To *draw level*.

Add realistic ETF tracking error (0.2–0.5% in Indian factor ETFs, and worth
checking per fund) and the gap narrows slightly — but not by enough to change
the conclusion.

## 5. What this does and does not mean

**It does not kill the project.** It relocates where any edge must come from.
The index is a fixed, public, semi-annually rebalanced rule. It cannot:

- exclude a stock the day it goes onto ASM/GSM (**H6**)
- apply a governance or auditor-resignation filter (**H6**)
- de-risk into cash during an adverse regime (**H4**)
- apply a quality screen to remove the distress tail (**H3**)
- concentrate into 12–15 names rather than 30

**Those four capabilities are the entire investment case for building this.**
They are exactly H3, H4 and H6 — which is fortunate, because they were
registered before this research was done.

**It does mean H2 must be restated.** Beating the Nifty 100 TRI was never a
sufficient test: an ETF beats it with no work. The real question is whether
the strategy beats *the momentum index*, after costs and after tax.

## 6. Consequences for the project

1. **Baseline B3 becomes mandatory and blocking.** See the amendment dated
   2026-08-04 in [`../HYPOTHESES.md`](../HYPOTHESES.md).
2. **Holding period matters more than signal quality.** The single largest
   controllable term in the table above is the tax line, and it is decided by
   holding period, not by prediction. A signal held 13 months beats a
   marginally better signal held 3 months, at these numbers.
3. **The benchmark position should arguably be the momentum ETF, not a plain
   index fund.** Holding the thing you are trying to beat, in size, is the
   most effective defence against self-deception this project has.
4. **If H3/H4/H6 all fail, the correct action is explicit:** buy the ETF, stop
   building, and keep the research code as the thing that told you the truth.

## 7. Open questions for Phase 2

- Realised tracking error of each momentum ETF versus the index, over the live
  period only (2020-08 onward).
- Liquidity and bid-ask spread of each ETF at ₹25,000 order size — small
  Indian ETFs can trade well away from iNAV.
- Whether the UTI index fund's NAV-based dealing removes the ETF spread
  problem at the cost of a day's execution lag.
- Whether a 75:25 momentum/G-sec hybrid (NSE publishes this index) achieves
  the drawdown reduction H4 targets, with no work at all.
