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
| **B1** | 2026-08-30 | Mid- and small-caps have beaten my portfolio over the past year, more so since I started investing | Midcap 150 TRI, Smallcap 250 TRI | **Nifty 200 TRI** (deficient — see below) | **PARTLY CONFIRMED, AND ONE PREMISE WRONG** |

---

## B1 — "Midcap 150 and Smallcap 250 have beaten my portfolio"

**Claim, verbatim:**

> In the past 1 yr Nifty Midcap 150 and Nifty smallcap 250 has beaten my
> portfolio by a little over 1-2% and slightly more in Nifty smallcap 250 if you
> take from the time that I started investing.

**Window:** 2005-04-01 to 2026-08-28 · **Horizons:** 3, 6, 12, 36, 60 months

### The premise that was wrong

The comparison was **an index against a blended portfolio**. The portfolio is
26.0% equity, 48.8% debt and cash, 25.2% gold. A 100% equity index outrunning a
26%-equity portfolio in a rising market is a statement about asset allocation,
not about mid-caps.

Measured properly — index against index — the gap is not 1–2%. It is **+8.9%**
for Midcap 150 and **+7.9%** for Smallcap 250 over the trailing year.

Which raises the more interesting question the original framing hid: the
portfolio nearly kept pace with a pure equity index while holding 26% equity.
Something carried the other 74%.

### What the archive said

Relative to the Nifty 200 TRI, 2005–2026:

| Horizon | Midcap 150 | | Smallcap 250 | |
|---|---|---|---|---|
| | latest | percentile | latest | percentile |
| 3m | +0.8% | 48th | +5.5% | 77th |
| 6m | +7.5% | 83rd | **+16.4%** | **91st** |
| 12m | +8.9% | 69th | +7.9% | 66th |
| 36m | +23.7% | 54th | +20.7% | 60th |
| 60m | +63.7% | 72nd | +52.2% | 76th |

**The 6-month row is the finding.** Smallcap's 6-month relative return sits at
the **91st percentile of 21 years** while its 12-month figure sits at the 66th.
The 12-month number is not the whole story — it is an extreme recent run
averaged together with a poor preceding half-year, and the averaging is what
makes it look ordinary.

The stated worry going in was that this was another 97th-percentile situation.
On the horizon actually asked about — one year — **it is not**. On the horizon
that was not asked about, it very nearly is.

### The two are not one story

| | Beats N200 | Avg win | Avg loss | Worst | Max drawdown |
|---|---|---|---|---|---|
| **Midcap 150**, 12m | 61% | +12.0% | −6.3% | −17.7% | −72.9% |
| **Smallcap 250**, 12m | 53% | +17.5% | −10.1% | −29.6% | −75.6% |

Over 60-month windows the divergence is sharper still: Midcap beats the Nifty
200 in **83%** of windows with a median of +23.7% and an average loss of −5.4%;
Smallcap beats it in **52%** with a median of **+2.3%** and a worst window of
**−59.9%**.

Treating "midcap and smallcap" as one category, which the original claim did, is
not supported by anything in this table.

### On the sample size

The 12-month row rests on 5,060 rolling windows and roughly **21 independent
observations**. Adjacent daily windows share 364 of their 365 days. Every
percentile above should be read against 21, not 5,060.

### The deficiency in this check

**The comparator is wrong, and known to be wrong.** The Nifty 200 contains the
Nifty Midcap 100, so measuring mid-caps against it compares a set against a set
that includes it. The true large-cap-versus-mid-cap gap is therefore **larger**
than every figure above.

The correct comparator is the Nifty 100, whose archive currently spans only
2015-01-01 to 2026-08-11 — 11.6 years against the 21.4 required. Per A13 rule 5
the checker **refuses** that pairing rather than answering the short question
while reporting the long one:

```
REFUSED at 3 months
  NIFTY 100 begins 2015-01-01, 9.8 years after NIFTY MIDCAP 150 begins
  2005-04-01. Measuring the claim anyway would answer it from the shorter
  history while reporting the longer one.
```

**This row is provisional until the Nifty 100 TRI archive is extended to 2005.**

### Confirmation status

**Not confirmed.** A13 rule 3 requires an encouraging result to survive a
non-overlapping second window before it may inform a decision. The 6-month
smallcap reading is the one that would need it, and it has not been run — a run
concentrated in recent months dominates every rolling window that contains it,
which is precisely what a second window is for.

---

*No row in this file recommends anything. A13 rule 1: the checker describes,
and any decision that follows is made outside this system by its owner.*
