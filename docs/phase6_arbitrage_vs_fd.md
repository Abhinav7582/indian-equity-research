# Phase 6, instrument 1 — arbitrage funds against fixed deposits

**2026-09-06.** Written research. Nothing here is a recommendation to buy or sell
anything, and no allocation is proposed. It prices a comparison the owner asked
for, using rates verified against published sources rather than recalled.

Promoted to first in the Phase 6 queue by belief check **B2**, which found that
an equity fund is the wrong vehicle for money with a due date, and that the
category built for exactly that problem had never been examined here.

---

## First, a correction

This project has said several times that **"₹31,91,275 — 48.8% of the balance
sheet — sits in debt and cash at ~6.6%."** That framing is wrong and it
overstated the opportunity. Broken out:

| | Value | Rate | Status |
|---|---:|---|---|
| PPF | ₹12,88,000 | **7.1% tax-free** | Locked to ~Apr 2036 |
| FDs + RDs | ₹14,54,000 | ~6.6% taxable | The emergency fund |
| NPS | ₹1,94,202 | market-linked | Locked to 60 |
| EPF + VPF | ₹1,49,000 | **8%+ tax-free** | Employment-locked |
| Savings | ₹99,531 | ~2.7–3.5% taxable | Genuinely idle |

**PPF at 7.1% tax-free and EPF at 8%+ tax-free are the best risk-free rates in
the entire portfolio.** Nothing in this document beats them. They are also
locked, so the question does not arise.

The addressable money is the **₹14,54,000 of FDs** and the **₹99,531 of
savings** — and the FDs are the emergency fund, which the owner has said is not
to be touched. So this is an analysis of an option, not of a plan.

---

## What an arbitrage fund is

It buys a stock in the cash market and simultaneously sells the same stock's
futures contract. The futures price normally trades above spot; that gap closes
by expiry, and the fund keeps the difference. The two legs offset, so the fund
carries **almost no directional equity risk** — but because it holds ≥65% in
equity and equity-related instruments, it is **taxed as an equity fund**.

That is the entire point: **equity taxation on a near-debt risk profile.**

| | Fixed deposit | Arbitrage fund |
|---|---|---|
| Return | contractual, guaranteed | depends on the futures-spot spread |
| Taxed as | interest, at slab | equity — 20% STCG / 12.5% LTCG |
| At 30% slab, keeps | 70% of the return | 87.5% after 12 months |
| Annual exemption | none | ₹1,25,000 of LTCG, **shared** across all equity |
| Early exit | premature-withdrawal penalty rate | exit load, typically 0.25–0.5% for 15–30 days |
| Redemption | branch/netbanking, penalty applies | T+1/T+2, no penalty after the load period |

Verified 2026-09-06: STCG **20%** below 12 months since 23 July 2024; LTCG
**12.5%** under s.112A above 12 months with a **₹1,25,000** annual exemption.
This matches the constants already in `backtest/tax.py`.

---

## The comparison, on ₹14,54,000 at a 30% slab

| Vehicle | Gross | Tax | Net | Net ₹ |
|---|---:|---|---:|---:|
| FD 6.60% — his current average | 6.60% | 30% slab | **4.62%** | ₹67,175 |
| FD 7.25% — best current market rate | 7.25% | 30% slab | 5.08% | ₹73,790 |
| Arbitrage 6.22% — category average, >12mo | 6.22% | 12.5%, under the exemption | **6.22%** | ₹90,439 |
| Arbitrage 7.00% — a good fund, >12mo | 7.00% | 12.5%, under the exemption | 7.00% | ₹1,01,780 |
| Arbitrage 6.22% — sold **inside** 12 months | 6.22% | 20% STCG | 4.98% | ₹72,351 |

**A category-average arbitrage fund held past twelve months beats his current FD
by ₹23,264 a year.** Even sold early at 20% STCG it still wins, by ₹5,176.

### The break-even is the cleanest way to see it

What an FD must pay **pre-tax** to match an arbitrage fund, at a 30% slab, held
past twelve months:

```
arbitrage 5.50%  ->  FD must pay 6.88%
arbitrage 6.22%  ->  FD must pay 7.78%
arbitrage 7.00%  ->  FD must pay 8.75%
```

His FDs pay 6.5–7.0%. The best rate in the market is around 7.25%. **A 6.22%
arbitrage fund needs an FD paying 7.78% to match it, and that FD does not
exist.**

---

## Three things that spoil the clean version

**1. The ₹1,25,000 exemption only helps if gains are realised inside it each
year.** Hold and redeem in one go and the whole accumulated gain lands in a
single year:

| Held | Gain | Taxable | Net CAGR |
|---:|---:|---:|---:|
| 1 year | ₹90,439 | ₹0 | **6.22%** |
| 3 years | ₹2,88,542 | ₹1,63,542 | 5.80% |
| 10 years | ₹12,04,443 | ₹10,79,443 | 5.67% |

Redeeming and re-buying annually to use the exemption keeps the net CAGR at
**6.18%** over ten years, against **4.62%** for the FD — a gap of **₹3,65,166**
on ₹14.54 lakh. But that requires actually doing it every year.

**And the exemption is shared.** It is one ₹1,25,000 across all equity — the
mutual funds, the direct stocks, and any arbitrage fund together. Using it here
means it is not available for the equity book.

**2. The return is not contractual.** Arbitrage yields track the futures-spot
spread, which compresses in calm or falling markets. The break-even against a
6.6% FD is roughly **5.28% gross**:

```
arbitrage 4.50% -> 3.94% net   vs FD 4.62% net   WORSE
arbitrage 5.50% -> 4.81% net   vs FD 4.62% net   better
arbitrage 6.22% -> 5.44% net   vs FD 4.62% net   better
```

Arbitrage funds have delivered in the 4–5% range in weak periods. An FD's 6.6%
is written into a contract; 6.22% is a category average over one year and is
**not a promise**.

**3. It is not capital-protected.** The hedge is close to complete, not
complete. Drawdowns are small and rare, but "small and rare" is a different
statement from "impossible", which is what an FD offers.

---

## The one place this bears on an open item

`portfolio.md` open item 5: **₹3 lakh needed in 48 hours would require breaking
an FD or using a card, and the owner wants neither.**

An arbitrage fund redeems **T+1/T+2 with no penalty** once past the exit-load
window, against an FD's premature-withdrawal penalty rate. On the specific
problem of *reachable* emergency money, it is structurally better than the
instrument currently doing that job — while paying more after tax.

That is an observation about the instrument, not a proposal to move the
emergency fund. The FD's guarantee is worth something precisely in the scenario
an emergency fund exists for.

---

## What this does and does not establish

**Establishes:** for a 30%-slab taxpayer holding past twelve months, the
after-tax gap between a category-average arbitrage fund and the best available
FD is large — around 1.6 percentage points a year — and it comes from the tax
treatment rather than from taking more risk.

**Does not establish:** that the owner should move anything. The FD money is the
emergency fund by deliberate choice, the guarantee has value in exactly the
circumstances it is held for, and arbitrage returns are neither contractual nor
stable. Choosing between them is the owner's call.

**Not examined here:** specific funds, expense ratios beyond what NAV returns
already net out, AMC concentration, or the effect of a large redemption on a
small fund. Those matter before any money moves and none of them is in this
document.

---

## Sources

Rates and tax treatment verified 2026-09-06 rather than recalled:

- [Arbitrage Fund Taxation in India 2026 — Bajaj AMC](https://www.bajajamc.com/knowledge-centre/arbitrage-fund-taxation)
- [Best Arbitrage Funds in India 2026 — ClearTax](https://cleartax.in/s/best-arbitrage-funds)
- [Arbitrage Mutual Funds category returns — Groww](https://groww.in/mutual-funds/category/best-arbitrage-mutual-funds)
- [Arbitrage Funds India 2026, compare returns and AAUM — RightAdvise](https://rightadvise.com/arbitrage-funds)
- [FD Interest Rates September 2026 — HDFC Bank](https://www.hdfc.bank.in/fixed-deposit/fd-interest-rate)
- [SBI FD Interest Rates September 2026 — GoldenPi](https://goldenpi.com/blog/fixed-deposit/sbi-fd-interest-rates-september-2026/)
- [Best FD Interest Rates September 2026 — Stable Money](https://stablemoney.in/fixed-deposit-interest-rates/best-fixed-deposit-interest-rate)
