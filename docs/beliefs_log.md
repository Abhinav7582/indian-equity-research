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
