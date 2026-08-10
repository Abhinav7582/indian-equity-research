# Portfolio Snapshot — Template

Copy this to **`data/reference/portfolio.md`** and fill it in. That location is
git-ignored: it stays on your machine and never reaches GitHub.

> **Never record** client IDs, account numbers, folio numbers, PAN, login
> details or anything from a statement header. None of it is needed here.

## Boundary — read this before filling it in

This file exists for **four decisions, all outside the research**:

1. **Benchmark holding** — what to hold as the thing the system must beat
2. **Tax timing** — which lots are past 12 months, so selling costs 12.5%
   rather than 20%
3. **Overlap** — if the system later picks stocks already held, sizing needs
   care or the position doubles unnoticed
4. **Your own track record** — your realised XIRR against the index over the
   same period is genuine out-of-sample evidence about whether active
   selection works for you

**The backtester must never read this file.** If a strategy is designed, even
unconsciously, around what is already owned, the result stops being evidence
and becomes a justification. This is the same discipline as pre-registering
hypotheses, applied to the person rather than the code.

---

## Equities

| Symbol | Qty | Avg buy price | First bought | Notes |
|---|---|---|---|---|
| | | | | |

## Mutual funds

| Scheme | Units | Avg NAV | First bought | SIP? |
|---|---|---|---|---|
| | | | | |

## ETFs / index funds

| Name | Units | Avg price | First bought |
|---|---|---|---|
| | | | |

## Other

| Asset | Value | Notes |
|---|---|---|
| Cash / liquid | | |
| Crypto (WazirX RTs etc.) | | |
| | | |

---

## Performance, if you have it

| | Since | Return |
|---|---|---|
| Overall XIRR | | |
| Equities only | | |
| Mutual funds only | | |
| Nifty 100 TRI, same period | | for comparison |
| Nifty Midcap 150, same period | | for comparison |

## Context worth writing down

- Roughly how much of this is money you would not want to lose?
- Any holdings you would not sell regardless (long-term convictions, ESOPs,
  anything with a lock-in)?
- Monthly amount you can add, if any?
- Anything with a pending tax consequence you already know about?
