# Beliefs log

Every claim about market state that has been checked against the archive,
**including the ones that came back unhelpful**.

Amendment A13 rule 4 requires this file. It exists because a belief that fails a
check is otherwise free to resurface six months later as a fresh idea, and
neither party would notice. This log is the memory that prevents that.

**What a row is.** A claim, in the words it was said in, and what the archive
said back. Not a decision, not a recommendation, and never a weight or an
amount — A13 rule 1 puts those outside this system entirely.

**Reproduce any row with:**

```
uv run python scripts/check_belief.py --subject <folder> --comparator <folder>
```

---

## Register

| # | Date | Claim (abbreviated) | Subject | Comparator | Outcome |
|---|---|---|---|---|---|
| **B1** | 2026-08-30 | Mid- and small-caps have beaten my portfolio over the past year, more so since I started investing | Midcap 150 TRI, Smallcap 250 TRI | Nifty 100 TRI, 2005–2026 | **NOT CONFIRMED — the effect is confined to one half of the archive** |
| **B2** | 2026-09-06 | Use an equity MF instead of the RD for one year — the returns are better than an RD | Nifty 100 TRI, 12 monthly buys redeemed at month 12 | RD 6.3% after 30% slab tax | **TRUE ON AVERAGE, UNSAFE FOR THIS PURPOSE** — median +₹10,027 better, but worse than the RD in 31% of programmes and the money has a fixed due date |

---

## B2 — "Shift the RD into an equity MF and redeem after a year"

**Claim, as given:**

> The amount of returns the RD is giving — if we shift that to MF then we can
> redeem those a year later where the said returns from MF is better than RD.
> So the only idea is that instead of RD we use MF as an RD for those 1 year
> period. Nothing is being removed or reduced. It is just a shift.

**Simulated exactly:** ₹20,000 on a session near each month end for 12 months
into the Nifty 100 TRI, redeemed in full at month 12. **272 overlapping
programmes, 2003–2026.** Every lot is short-term at redemption — 12 months is
365 days and s.112A needs *more* than 365 — so 20% STCG applies to all of it.

### The premise is correct

An RD is a poor vehicle for a 30%-slab taxpayer:

```
12 x Rs 20,000 at 6.3%  ->  matures 248,305, interest 8,305
after 30% slab tax      ->  net gain 5,814 = 2.42% on money invested
```

### And the median outcome supports the claim

| | Net gain after tax | vs RD |
|---|---:|---:|
| worst (programme starting Oct 2007) | **−₹1,09,252** | −₹1,15,066 |
| p5 | −₹32,115 | −₹37,929 |
| p10 | −₹7,829 | −₹13,643 |
| median | **+₹15,841** | **+₹10,027** |
| p90 | +₹51,991 | +₹46,177 |
| best | +₹1,21,570 | +₹1,15,756 |

### But the distribution is the finding, because this money has a due date

```
worse than the RD    in 31% of programmes
lost money           in 20%
lost more than 10%   in  7%
```

The ₹2,40,000 exists to pay **PPF ₹1,50,000 + LIC ₹1,04,515 = ₹2,54,515** on a
date nobody chooses. Against that obligation:

| Outcome | Value at month 12 | |
|---|---:|---|
| median equity | ₹2,55,841 | covers it |
| RD | ₹2,45,814 | short ₹8,701 |
| equity, 10th percentile | ₹2,32,171 | short ₹22,344 |
| equity, worst | ₹1,30,748 | **short ₹1,23,767** |

**Note the RD does not fully cover it either** — ₹2,40,000 invested against
₹2,54,515 owed. A small gap is already being met from elsewhere.

### The vehicle built for exactly this

| | pre-tax | tax | net gain | vs RD |
|---|---:|---:|---:|---:|
| RD 6.3% | 6.3% | 30% slab | ₹5,814 | — |
| Short-duration debt ~7.0% | 7.0% | 30% slab | ₹6,304 | +₹490 |
| **Arbitrage fund ~6.5%** | 6.5% | **20% equity STCG** | ₹6,695 | **+₹881** |
| **Arbitrage fund ~7.0%** | 7.0% | **20% equity STCG** | ₹7,205 | **+₹1,391** |

Arbitrage funds carry **equity taxation on a near-debt risk profile** — which is
precisely the mismatch the RD suffers from, solved without taking equity's
distribution. Smaller upside than equity's median, and no realistic path to
being ₹1.2 lakh short.

**Verdict: the insight is right and the vehicle is wrong.** Equity over a fixed
twelve-month window ending on a payment date is not an RD substitute; it is a
20% chance of arriving short. This is Phase 6 instrument #2, and it has now
earned its priority.

---

## B1 — "Midcap 150 and Smallcap 250 have beaten my portfolio"

**Claim, verbatim:**

> In the past 1 yr Nifty Midcap 150 and Nifty smallcap 250 has beaten my
> portfolio by a little over 1-2% and slightly more in Nifty smallcap 250 if you
> take from the time that I started investing.

**Window:** 2005-04-01 to 2026-08-28 · **Horizons:** 3, 6, 12, 36, 60 months
**Comparator:** Nifty 100 TRI — large-cap, and containing none of what is being
measured.

### The premise that was wrong

The comparison was **an index against a blended portfolio**. The portfolio is
26.0% equity, 48.8% debt and cash, 25.2% gold. A 100% equity index outrunning a
26%-equity portfolio in a rising market is a statement about asset allocation,
not about mid-caps.

Measured index against index, the trailing-year gap is **+11.3%** for Midcap 150
and **+10.2%** for Smallcap 250 — not 1–2%.

Which leaves the more interesting question the original framing hid: the
portfolio nearly kept pace with a pure equity index while holding 26% equity.
Something carried the other 74%.

### What the full archive said

| Horizon | Midcap 150 | | Smallcap 250 | |
|---|---|---|---|---|
| | latest | percentile | latest | percentile |
| 3m | +0.9% | 49th | +5.6% | 75th |
| 6m | +9.4% | 86th | **+18.3%** | **91st** |
| 12m | +11.3% | 72nd | +10.2% | 69th |
| 36m | +28.9% | 59th | +25.9% | 64th |
| 60m | +74.3% | 76th | +62.8% | 77th |

**The 6-month row is the extreme, not the 12-month one the claim was about.**
Smallcap's six-month relative return sits at the **91st percentile of 21 years**
while its twelve-month figure sits at the 69th — an exceptional recent half-year
averaged with a poor preceding one, and the averaging is what makes the annual
number look ordinary.

### The confirmation, and what it destroyed

A13 rule 3 requires an encouraging result to survive a **non-overlapping** second
window. The archive was split at its own midpoint, 2016-01-01, chosen for being
the midpoint and nothing else.

The two halves disagree completely.

| | 2005–2015 | 2016–2026 |
|---|---|---|
| **Midcap 150**, 12m | 46% hit, median **−2.0%** | 73% hit, median +6.1% |
| **Smallcap 250**, 12m | 46% hit, median **−2.3%** | 59% hit, median +3.3% |
| **Midcap 150**, 60m | 41% hit, median **−4.4%** | 95% hit, median +60.4% |
| **Smallcap 250**, 60m | **20%** hit, median **−14.5%** | 62% hit, median +31.1% |

**For the first eleven years of this archive, mid- and small-caps lost to
large-caps more often than they won.** Over five-year holds, Smallcap 250 beat
the Nifty 100 in **one window in five**, with a median of −14.5%.

Every favourable statistic in the full-sample table above is an average of two
regimes pointing in opposite directions. A 60% twelve-month hit rate is not a
stable property of Indian mid-caps; it is 46% followed by 73%.

**Status: NOT CONFIRMED.** The second window did not corroborate the first — it
showed the effect is confined to the half of the archive we have lived through.

### What this does and does not establish

**It does not establish** that mid-caps will revert. A structural change in
Indian markets after 2016 — domestic institutional flows, SIP growth, wider
participation — is a real hypothesis and this data cannot rule it out.

**It does establish** that the belief rests on one regime rather than on
twenty-one years, and that the twenty-one-year figures are the wrong ones to
quote in its support. Anyone relying on "mid-caps beat large-caps 60% of the
time" should know that number is a blend of 46% and 73%, and that which one
applies next is exactly what is unknown.

### The whole-period statistics, for completeness

| | Beats N100, 12m | Avg win | Avg loss | Worst | Max drawdown |
|---|---|---|---|---|---|
| **Midcap 150** | 60% | +13.4% | −7.8% | −23.5% | −72.9% |
| **Smallcap 250** | 52% | +18.9% | −11.2% | −31.9% | −75.6% |
| *Nifty 100* | — | — | — | — | *−61.1%* |

Over 60-month windows against the correct comparator, **Smallcap 250 beats the
Nifty 100 in only 47% of windows with a median of −3.0%**. Against the Nifty 200
the same figures were 52% and +2.3% — the contaminated comparator was flattering
it, exactly as A13 rule 5 anticipated.

### On the sample size

The 12-month row rests on 5,060 rolling windows and roughly **21 independent
observations**. Adjacent daily windows share 364 of their 365 days. Every
percentile above should be read against 21, not 5,060 — and the split-half table
rests on about ten each side.

### Data

Nifty 100 TRI extended to 2003-01-01 on 2026-08-30: **5,880 rows, zero
defects**, and all 5,311 mid-cap sessions present. Three values spanning the
pre-existing 2015–2026 files were re-checked against what they read before the
re-download and matched to the paisa, so the extension introduced no drift.

---

*No row in this file recommends anything. A13 rule 1: the checker describes,
and any decision that follows is made outside this system by its owner.*
