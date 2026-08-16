# External claims register

**Opened 2026-08-16.**

Claims encountered outside this project — forum posts, blogs, vendor material.
Nothing here is evidence, and **nothing here enters `HYPOTHESES.md` or the trial
register** unless it is formally registered as a trial first.

## Why this file exists separately

The trial count is the denominator of the Deflated Sharpe. With 5 trials the
chance-expected best Sharpe is already 1.19; at 25 it is 2.00.

Reading twenty strategy ideas and testing the two that looked promising is
**twenty trials, not two**. The selection happened, it just happened in
someone's head rather than in code. Keeping external claims in a separate file
that explicitly is not the trial register makes that boundary visible — and
makes it deliberate when it is crossed.

---

## C1. "Multi-factor quant engine, +₹21k live" — r/IndiaAlgoTrading, Aug 2026

**Status: not testable as presented.** Recorded as a worked example of how to
read this kind of post, not as a lead.

### What was claimed

- Live realised P&L **+₹21,474**, 16 Feb 2026 → 15 Aug 2026, Zerodha ledger shown
- Paper simulation over Jul–Aug described as "about +₹8k in profit"
- Three strategy legs: Pure Momentum, Quality Value, Unified
- Sold at ₹199/month

### What the numbers actually say

**1. The two figures are from different systems.** The live P&L covers Feb–Aug
on an engine that has since been changed. The paper simulation runs the
*current* engine. The paper result is the out-of-sample test; the live figure
is from a superseded version.

**2. The paper result contradicts itself.** The text says "+₹8k in profit". The
chart in the same post shows base ₹1,00,000 → **₹95,952.39**, a loss of
**₹4,048 (−4.05%)**. The curve peaks around ₹105k, so ₹8k is not the
high-water mark either. The most likely reconciliation is gross profit on
winning trades with losers excluded.

**3. The denominator is missing.** Nowhere is the capital stated. Measured
against the Nifty 100 TRI over his exact window, from this project's own
archive:

```
NIFTY 100 TRI   2026-02-16 → 2026-08-11
36,216.78 → 35,540.21   =  −1.87%
```

| Capital | His return | Index over same window |
|---|---:|---:|
| ₹1,00,000 | 21.5% | −1.9% |
| ₹5,00,000 | 4.3% | −1.9% |
| ₹20,00,000 | 1.1% | −1.9% |

At the top of that range it is extraordinary. At the bottom it is what being
60% in cash produces in a falling market. **The market fell over his window**,
so any strategy with reduced net exposure beats it without skill.

**4. "Net realised P&L" excludes open positions.** Sell winners, hold losers,
and a verified ledger shows a profit while the book bleeds. This is the
disposition effect, and it is the standard way an honest-looking ledger
misleads.

**5. The return distribution has the wrong shape.**

| Bucket | Count | Share |
|---|---:|---:|
| Large loss (< −5%) | 11 | 8% |
| Small loss (−5–0%) | 49 | 36% |
| Small gain (0–5%) | 67 | 49% |
| Large gain (> 5%) | 10 | 7% |

The left tail is fatter than the right: many small gains, occasional large
loss. That is the sell-insurance profile that
`backtest/gates.py::deflated_sharpe_ratio` penalises through skewness — see
`test_negative_skew_is_penalised`, which describes it as "excellent right up
until it is not". His reported metrics — win rate and "reward factor" — cannot
see this.

**6. Overfitting, stated in the post.** *"Looking at the bad data from the July
simulation, I realized my risk-reward logic wasn't strict enough."* Three
filters were then added: forced 1:2 ATR risk-reward, 20-day anchored VWAP,
sector breadth. Rules chosen after seeing the period that lost money, to avoid
the period that lost money. That is fitting to the test set.

Trial count is now at least six (3 legs + 3 filters), and none of it is
reported.

**7. Sample size.** `Quality Value` — the leg being sold — is **33
simulations** with a reward factor of 7.5. Thirty-three trades in a month is
noise.

### Regulatory note

Paid stock recommendations in India require SEBI Research Analyst registration
under the SEBI (Research Analysts) Regulations, 2014. There is no small-scale
or side-income exemption. No claim is made here about this individual's
registration status; the SEBI RA register is the place to check before paying
anyone for recommendations.

### What is worth taking

Three things, genuinely:

1. **Paper trading alongside live.** This project's Phase 7.
2. **Per-leg attribution.** It is how he found the momentum leg bleeding.
3. **He published the leg that failed.** Most do not.

---

## C2. Momentum in Indian equities

**Status: already covered by H1. No new trial cost.**

H1 (momentum monotonicity) was pre-registered before this material was read, so
testing it does not add to the trial count. That is what pre-registration is
for, and it is working.

The literature broadly supports momentum in Indian equities — a long-only
momentum strategy has delivered superior risk-adjusted performance, with
6-month lookback and quarterly rebalancing among the better-performing
configurations, and returns concentrated in the **most liquid** names.

**The number that matters more than the average.** A published 18-year backtest
of the Nifty 200 Momentum 30 index reports a **roughly −70% drawdown with a
65-month recovery**. Five and a half years underwater.

That is the figure to hold onto. It is absent from fund factsheets, and it is
the difference between a strategy that is theoretically sound and one a person
can actually hold. Amendment A6's two-year abandonment test would fire long
before month 65.

**Bearing on this project:** the primary momentum signal is already sold as an
ETF at 0.22% (`docs/benchmarks.md`). The bar is not "does momentum work in
India" — the evidence says broadly yes — it is "does *our* implementation beat
a cheap fund that already captures it, after every cost and tax". H2 is the
question, not H1.

---

## C3. Technique claims not currently registered

Recorded so that if any is ever tested, the reading is on the record and the
trial count is honest.

| Claim | Source | Status |
|---|---|---|
| 1.5× ATR stop / 3× ATR target, reject below 1:2 | C1 | Untested. A stop rule is a **cost multiplier** — at ₹3,000 positions the flat ₹20 DP charge per sell is 0.67%, so a rule that increases exits is expensive here in a way it is not at scale |
| 20-day anchored VWAP filter | C1 | Untested. Closely correlated with a short-window momentum filter; unlikely to be independent of H1 |
| Sector breadth (advances vs declines) gate | C1 | Untested. This is a regime overlay, and **H4 — a regime overlay — was tested and rejected**: it increased drawdown rather than reducing it and lost to a static 75:25 blend |

The third is worth dwelling on. The single hypothesis this project has actually
tested was a regime filter, and it failed. A breadth gate is the same idea in a
different costume. Testing it would mean re-running a rejected class of
hypothesis on new packaging — permissible, but it should be a deliberate
decision with a fresh amendment, not a drift.

---

## How to read the next one of these

A checklist, derived from C1:

1. **What is the denominator?** Return without capital is not a return.
2. **Realised or total?** Realised P&L can hide an unrealised hole.
3. **What did the market do over the same window?** We have the archive; check.
4. **How many configurations were tried?** Every one raises the bar.
5. **Were the rules chosen before or after seeing the data?** "I looked at the
   bad month and added a filter" is fitting to the test set.
6. **What is the sample size?** 33 trades is not a result.
7. **Is the loss tail fatter than the gain tail?** Win rate hides this.
8. **Are costs and taxes in the simulation?** Usually not.
9. **Is something being sold?** Not disqualifying. But it is the frame.

---

## What forums are good for

Not strategy claims. These, which cost nothing in trial count because they are
not statistical claims at all:

- Data sources, URL patterns, and **format changes** — NSE changed the bhavcopy
  format in 2024 and will again
- Broker and API mechanics: rate limits, token expiry, order rejection quirks
- Cost and tax gotchas — the DP-charge finding in this project came from
  modelling real charges, and there are likely more like it
- What people tried and **abandoned**

## A note on Indian dividend taxation

Relevant to any dividend-focused material, most of which is US-centric:

| | Rate |
|---|---|
| Dividends (resident individual) | **Slab rate**, up to 30% + cess |
| Equity LTCG (s.112A) | **12.5%** above ₹1.25L |

Dividends are taxed roughly **2.4× worse than capital gains** at the margin in
India, the opposite of the US treatment that most dividend-growth content
assumes. From 1 April 2026 the deduction previously available against dividend
income was removed. TDS applies at 10% above ₹10,000 under s.194 and is a
credit, not a final tax.

The strategy logic in US dividend material does not transfer.
