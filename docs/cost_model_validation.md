# Cost model validated against real contract notes

**Validated 2026-08-18** against two Groww contract notes (4 and 11 August
2026). Until now every rate in `backtest/costs.py` came from *documentation*.
None had been checked against a rupee actually paid.

Source PDFs are personal records and are **not** in the repository.

---

## Result: one exact match, one real defect

| Component | Modelled | Actual | |
|---|---|---|---|
| DP charge | ₹20 + 18% GST = **₹23.60** | **₹23.60** | ✅ exact |
| — CDSL portion | — | ₹3.50 | |
| — Groww portion | — | ₹16.50 | |
| **DP charging unit** | **per scrip per sell** | **per sell ORDER** | ❌ **understates** |
| GST | 18% | CGST 9% + SGST 9% | ✅ |
| GST base | brokerage + exchange + SEBI + IPFT, and DP separately | same | ✅ |
| SEBI turnover fee | 0.000001 | ₹0.04 on ₹40,417 → 0.000001 | ✅ |
| Stamp duty | 0.015%, buy only | ₹3.00 on ₹20,871 buys = 0.0144% | ✅ |
| IPFT | 0.000001 | ₹0.00 on both notes | ⚠️ ~₹0.04, immaterial |
| Brokerage | ₹20 cap / 0.1% / ₹5 floor, per order | consistent | ✅ |

---

## The defect: DP is charged per sell ORDER

The two notes separate the hypotheses cleanly.

**4 August — both hypotheses fit.**

```
6 scrips sold, 6 sell orders, 7 trades (one order filled in two trades)
DP charged: Rs 141.60  =  6 x Rs 23.60
```

Note that the order with **two fills was charged once** — so it is not per
trade.

**11 August — only one hypothesis fits.**

```
Ltm Limited          1 sell order   (-2)
Jio Fin Services     2 sell orders  (-8, then -20)
                     --------------------------------
2 distinct scrips,   3 sell orders
DP charged: Rs 70.80  =  3 x Rs 23.60
```

**Jio Financial was sold in two orders on one day and was charged twice.**

Per-scrip-per-day predicts ₹47.20. Per-order predicts ₹70.80. The note says
₹70.80.

### The exact rule

> DP is charged **once per sell order**. Not per scrip per day (Zerodha's
> rule), and not per fill.

`costs.py` names the field `dp_charge_per_scrip` and the engine applies it once
per position exited. That is correct **only if every exit is a single order**.

### Why this matters more than it looks

Order splitting is driven by liquidity, not by choice. A ₹3,000 position in a
liquid Nifty 100 name is one order — but any position large enough to need
working, or any execution logic that slices to limit impact, multiplies the DP
charge by the number of slices.

So the fixed-cost problem has a second dimension the dossier did not have:

* **breadth** — how many positions (known)
* **order count per exit** — how finely each is worked (new)

The breadth study must count **sell orders**, not positions. Modelling one
order per exit is the optimistic case and should be labelled as such.

---

## What this does to the earlier numbers

The DP rate itself was right, so the headline arithmetic stands:

| Names at ₹3L | DP per full turnover, 1 order per exit |
|---:|---:|
| 15 | 0.118% |
| 100 | 0.787% |

But those are now a **floor**. At an average of 1.5 sell orders per exit — which
11 August actually exhibited (3 orders for 2 scrips) — they become 0.177% and
1.18%.

---

## Two things the notes revealed that were not being modelled at all

**1. ETFs are not equity delivery.** Both notes contain `INF179KC1981` (HDFC
Gold ETF) and `INF204KB17I5`. STT on 4 August was ₹39.00 where whole-portfolio
equity delivery at 0.1% both legs would give ₹40.42. The gap is the ETFs, which
carry a different STT treatment. Immaterial for a Nifty 100 cash strategy, but
the cost engine silently treats every instrument as equity delivery and should
say so.

**2. Brokerage floors bind constantly.** On 11 August, 10 orders produced
₹51.61 of brokerage — an average of ₹5.16, meaning almost every order hit the
**₹5 minimum** rather than the 0.1% rate. At the position sizes this project
contemplates, brokerage is effectively another *fixed* cost, not a
proportional one. That compounds the same small-account problem as DP.

---

## Changes required

1. Rename `dp_charge_per_scrip` → `dp_charge_per_sell_order` and update the
   docstring to state the rule and the broker it was verified against.
2. Give the engine an explicit orders-per-exit assumption, defaulting to 1 and
   **reported in every result**, so the optimistic case is never mistaken for
   the expected one.
3. Record in `costs.py` that the schedule is Groww-specific, and that Zerodha's
   DP rule (per scrip per day, ₹13 + GST) is materially different — both in
   rate and in charging unit.
4. Add a test pinning the 11 August case: 2 scrips, 3 orders, ₹70.80.

---

## Note on the source files

The contract notes contain a mobile number and other identifying fields. They
are personal records: keep them out of the repository, and out of any inbox
folder that might later be committed.

---

## Ledger reconciliation — both days match to the paisa

The Groww Balance Statement (1 Jan – 17 Aug 2026, 560 rows) settles the
component check completely. DP charges do not appear as their own segment; they
are netted inside `STOCKS_SETTLEMENT`.

```
04-Aug   ledger net -1618.26   =  contract note -1476.66 - DP 141.60   MATCH
11-Aug   ledger net +1502.11   =  contract note +1572.91 - DP  70.80   MATCH
```

Every modelled component — brokerage, STT, stamp duty, exchange, SEBI, GST, DP
— reconciles end to end against money that actually moved. **The cost model's
components are validated.** Only the DP charging *unit* was wrong.

## Charges the model does not have at all

The ledger contains cost categories that never reach a contract note:

| Segment | Rows | Total |
|---|---:|---:|
| `TURNOVER_COLLECTED` | 1 | **₹2,264.80** |
| `INTEREST_ACCRUED` | 223 | ₹154.11 |
| `DDPI_CHARGES` | 1 | ₹118.00 |
| `STOCKS_PLEDGE_UNPLEDGE_CHARGES` | 1 | ₹23.60 |

`INTEREST_ACCRUED` is **₹0.69 every single day**, unbroken. Alongside 68
`M2M_BLOCKED` / 65 `M2M_RELEASED` rows and the pledge and DDPI charges, that is
the signature of a **margin facility**, not plain delivery. The narration column
is `N/A` throughout, so this is inference from structure, not a reading.

`TURNOVER_COLLECTED` is a single ₹2,264.80 debit on 11 August — **3.85% of all
settlement debits in the period**, and larger than every other non-trade charge
combined. Its meaning cannot be determined from the file.

### What this changes

The engine models a **cash delivery** account: brokerage, statutory charges, DP.
It has no concept of financing cost, margin interest, pledge fees, or
periodic account charges. For a pure-delivery strategy that is correct. But a
backtest that quietly assumes delivery while the real account accrues daily
interest is comparing two different things.

**Open questions for Groww support** — neither answerable from the data:

1. What is `TURNOVER_COLLECTED`, and is it periodic or one-off?
2. Is `INTEREST_ACCRUED` margin financing? At what rate, on what balance?

Until answered, `docs/benchmarks.md` should note that measured account costs
exceed modelled trading costs by a margin that has not been quantified.
