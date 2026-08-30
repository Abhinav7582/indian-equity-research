# Roadmap

**Last revised: 2026-08-12**

This is the single forward-looking plan. Where it disagrees with an older note
elsewhere in the repository, this file wins. `HYPOTHESES.md` remains the
governing document for anything evidential — this file may not weaken it.

---

## Where things stand

| Phase | Scope | State |
|---|---|---|
| 1 | Research foundation, feasibility verdict, H1–H6 registered | **Done** |
| 1.5 | H4 regime overlay experiment | **Done — H4 REJECTED** |
| 2 | Data layer: archiver, calendar, instrument master, validator, bhavcopy ingest, delisting register, adjustment engine | **Done** |
| 3a | Universe construction | **Done — real Nifty 100 reconstructed, and now actually produced.** `market/membership.py` rolls the 2026-08-21 roster backwards through 38 changes to 2014-09-19: **34 snapshots, 0 changes unapplied**. Renames are resolved by ISIN identity (`market/identity.py`), not by ticker — without that, five changes fail silently and the roster drifts. Size is 100 throughout except two windows at 101, both accounted for by exactly one security, `TATAMTRDVR`; NSE ran the Nifty 50 at 51 members for the same reason. A5 proxy retained as scaffolding only |
| 3b | Adjusted price series pipeline | **Done.** Of 487 large moves in liquid names: 270 explained by a documented action, 138 listing days, 12 market-wide, 67 hand-adjudicated (6 real actions, 61 crashes). Four lookup bugs found and fixed along the way: `Re` vs `Rs`, symbol-vs-ISIN matching, the date-ranged endpoint omitting renamed/delisted names, and `&` breaking a URL. **Wired in** via backtest/prices.py: build_bars() serves back-adjusted OHLC and refuses while the audit is incomplete. `residual_moves()` then found three further defects the audit could not have seen, all silent — see `docs/price_series_defects.md`: the `EQ`-only filter deleting surveillance-series bars, feed actions keyed by the vendor's *current* symbol (61 of 841 ratios, 7.2%, lost), and compound `Bonus/Split` subjects read as one action (11 rows, TECHM and BAJFINANCE among them) |
| 3c | Transaction cost model | **Done** |
| 3d | Event-driven engine | **Done** |
| 3e | Self-deception suite, mutation-tested | **Done** |
| 3f | Statistical gates (DSR, PBO) | **Done** |
| 3g | Purged / embargoed walk-forward CV | **Done** |
| 4 | Hypothesis testing on the real universe | **CLOSED 2026-08-29 — see `docs/phase4_closeout.md`.** The answer is no, and not marginally. **H2 and H1 both REJECTED on the Nifty 100** (trials #2 and #3, 2026-08-23). H2: net CAGR **10.85%** vs **17.13%** for the Nifty 100 TRI; the signal lost **3.32% before any cost**, so costs were not the cause. H1 then explained why — mean rank IC **+0.0378** with **t = 1.47** (needs 3.0), spread positive in **2 of 5** sub-periods, and **decile 10 returned −0.138%/month** against D9's +0.403%. The effect is weak, unstable, and absent from the top decile a small book must hold. Holdout untouched. **Nifty 200 extension attempted and BLOCKED ON DATA QUALITY** (A10 outcome, 2026-08-29) — both datasets arrived and are sound, but the universe will not reconstruct: 13 unapplied changes parsing Nifty 200 sections, 14 building it as `Nifty 100 ∪ Nifty Midcap 100`. Cause is an incomplete press-release archive (18 releases held for 2015 against 165 for 2025). Trials #4 and #5 not spent. **A11 Route 2 then asked the size question a different way (trial #6, 2026-08-29):** rank IC within the Nifty 50 vs within the Nifty Next 50, both reconstructing with 0 unapplied. Next 50 **+0.0414** against Nifty 50's **+0.0360** — direction as predicted, but **t = 1.57** against a required 3.0. **SUGGESTIVE NEGATIVE.** With the Nifty 100 at +0.0378 sitting between its two halves, momentum is weak, similar and never significant across the whole size range this archive can measure. **Retrospective 2026-08-29 found a mandatory check that was never run:** Amendment A1 made the NIFTY200 Momentum 30 index a blocking baseline, and trial #2 scored only the Nifty 100 TRI. Scored now — **B3 returned 25.10%/yr over exactly that window**, against the strategy's 10.85%. ₹3L would have become ₹11.2 lakh, not ₹5.5 lakh. The rejection stands but "the signal lost" is very likely the wrong reading; we tested **raw** 12-1 where NSE's index uses **risk-adjusted** momentum. A guard now refuses to produce a result with a registered baseline missing. **A12 then tested NSE's own signal (trial #7):** risk-adjusted momentum scored **worse** — IC **+0.0239** against raw 12-1's **+0.0378**, t 1.04 against 1.47, decile spread 4bp/month against 46bp. **NOT SUPPORTED: the signal is not the explanation.** After two signals, three universes and every cost treatment, every measurement sits between IC 0.024 and 0.041 with t between 1.04 and 1.57. H3, H5 and H6 remain registered and untested: H3 and H6 were refinements to a working strategy and would now have to **create** the edge; H5 is close to moot. None withdrawn, none worth a trial at current odds. **Nothing deployed — A6's ₹3,00,000 cap was never approached, because no strategy reached paper trading.** |
| 5 | Allocation system | **NEXT.** One percentage point across ₹65.4 lakh is ₹65,403 a year, against ₹15,000 from a successful strategy on ₹3 lakh. Currently no declared policy at all |
| 6 | Unexplored instruments research | Not started |
| 7 | Paper trading, then the A6 decision | Not started |

**895 tests · ruff clean · mypy strict clean · 12/12 mutation bugs caught.**

---

## Data acquisition — complete

All three datasets have landed. Phase 4 is no longer blocked on data; it is
blocked on 3b (adjusted prices) and 3g (validation). Instructions are retained
for the annual top-up.

### 1. ~~Bhavcopy for 2025~~ — **DONE 2026-08-10**

248 files downloaded. Archive now runs **2015-01-01 to 2026-08-05, 2,861
sessions, 5,329,912 rows, 3,963 securities, no gap longer than 10 days.** The
engine's continuity guard passes and the full 10.8-year pipeline runs.

Commands retained for the next annual top-up:

```bash
# 1. Confirm the URLs still resolve. Downloads nothing.
uv run python -m indian_equity_research bhavcopy --check

# 2. See the plan. Downloads nothing.
uv run python -m indian_equity_research bhavcopy --from 2025-01-01 --to 2025-12-31

# 3. Cautious first run — ten files, then stop.
uv run python -m indian_equity_research bhavcopy --from 2025-01-01 --to 2025-12-31 --fetch --limit 10

# 4. If those ten look right, do the rest.
uv run python -m indian_equity_research bhavcopy --from 2025-01-01 --to 2025-12-31 --fetch --delay 2

# 5. Parse everything and run the corporate-action validator.
uv run python -m indian_equity_research bhavcopy --validate
```

At a 2-second delay this takes roughly 10 minutes. Leave the delay at 2 — it is
not slow enough to matter and it is the difference between polite and abusive.

**Verify afterwards:**

```bash
ls data/raw/bhavcopy | sed -E 's/.*_([0-9]{4})-.*/\1/' | sort | uniq -c
```

#### What the first full run showed — SCAFFOLDING, not evidence

Ran on the A5 proxy universe, 2015-10-01 to 2026-08-05, equal-weight, monthly
rebalance, ₹3,00,000. Under A5 this is **not** a result and is not in the trial
register. It is reported here because it says useful things about *design*.

| | |
|---|---:|
| Final equity | ₹5,16,294 |
| CAGR | 5.13%/yr over 10.8 years |
| Max drawdown | **−55.6%** |
| Sharpe | 0.408 |
| Deflated Sharpe | **FAILS at 90.5%**, on a single trial |
| Charges paid | ₹35,067 on ₹40.3 lakh turnover |
| **DP charge alone** | **₹17,020 — 48.5% of all charges** |

Three things worth carrying forward:

1. **The flat DP charge is the dominant cost**, not brokerage and not STT.
   Equal-weighting 100 names on ₹3 lakh means ₹3,000 positions, where a flat
   ₹20 per scrip sold is 0.67% per sale. **Any strategy holding many small
   positions is structurally uneconomic at this account size.** A basis-point
   cost model would have hidden this completely.
2. **The proxy behaved exactly as Amendment A5 predicted.** 5.13%/yr against
   11.28% for the Nifty 100 price index over the same window, and a −55.6%
   drawdown against roughly −38% for the index at its COVID worst. The
   turnover-ranked universe admitted small speculative names, and it shows.
   A5 was written before this ran.
3. **The engine produces plausible numbers.** The largest single-day move it
   found was −8.63% on 2020-03-23, which is the COVID crash. Nothing absurd,
   nothing suspiciously smooth.

### 2. ~~NIFTY 100 Total Return Index~~ — **DONE 2026-08-11**

Twelve files, 2015–2026, in `data/raw/indices/nifty100_tri/`, header
`"IndexName","Date","Total Returns Index"`. The estimated dividend adjustment in
`data/reference/portfolio.md` can now be replaced with measured values.

Original instructions retained for the next annual top-up:

#### NIFTY 100 Total Return Index

Your Nifty 100 files are **price return**. Benchmarking against a price index
silently hands you ~1.3%/yr of dividends the index earned and is not being
credited for. Every TRI figure in `data/reference/portfolio.md` is currently an
estimate because of this.

- Go to **https://www.niftyindices.com/reports/historical-data**
- Index Type **Equity** → **Total returns Index Values** (not the Equity tab)
- Sub-Index **Broad Market Indices** → Index **NIFTY 100**
- One year per download if the site caps the range
- Save to **`data/raw/indices/nifty100_tri/nifty100_tri_YYYY.csv`**

Header should read `"IndexName","Date","Total Returns Index"`.

### 3. NSE index-change press releases — the real Nifty 100 universe

**They are press releases, not circulars.** An earlier version of this file had
that wrong. Full instructions and the confirmed URL pattern are in
[`docs/universe_reconstruction.md`](docs/universe_reconstruction.md).

- Listing: **https://www.niftyindices.com/media**
- Pattern: `https://www.niftyindices.com/Press_Release/ind_prsDDMMYYYY.pdf`
- Announced late **February** and late **August**; effective **31 March** and
  **30 September**
- Baseline: `https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv`
- Save to `data/raw/circulars/`, keeping NSE's own filenames

**Both the parser and the downloader already exist.** `market.index_changes`
parses the PDFs (tested against verbatim fixtures from the real 2015 *and* 2025
releases, including the pre-rebrand "CNX 100" naming).
`ingest.circulars_fetch` collects them, either from saved listing pages or by
sweeping the predictable review windows — 439 requests for 2015–2026, roughly
fifteen minutes.

**The listing cannot be scraped directly:** the year filter runs in the
browser, so `/media?year=2015` returns the same page as `/media`. Saving one
HTML page per year is the reliable route; the sweep is the supplement.

Volume is smaller than feared: five in and five out at the August 2025 review,
so roughly **100–150 total changes** for the Nifty 100 since 2015.

**Watch for interim releases.** Mergers and delistings trigger ad-hoc
replacements outside the February and August reviews. A reconstruction built
only from the semi-annual ones drifts. The size self-check in
``reconstruct_membership`` catches this by refusing to return a membership that
is not exactly 100.

**Status 2026-08-12 — CLOSED.** 1,037 releases downloaded. **33 changes applied,
coverage continuous July 2015 → August 2026, net size change zero, nothing
unread.** Exactly one release needed a human (a 29-page scan holding the
September 2021 review on page 5).

Six defects were found by running against the real archive, each of which had
silently reported "this release does not touch the index":

| Defect | Cost had it stood |
|---|---|
| Headings numbered `(3)` and `d)`, not just `3)` | 103 releases |
| Four effective-date wordings, some with spaces inserted mid-word | 148 releases |
| `"scrips"` instead of `"companies"` | the entire 2016 gap |
| Two sections for one index in a single release | the 2020-H2 gap |
| **A second release format** — one security, a table of index names, no per-index heading | the 2024 DVR cancellation; found only because the index gained a net member |
| **A reconstitution announced and then deferred** | five companies removed twice, March–June 2020 |

The last two are the interesting ones: neither is a regex problem, and neither
would ever have surfaced from a test fixture. See
[`docs/circulars_worklist.md`](docs/circulars_worklist.md).

**If some releases cannot be found, that is a finding to report — not a licence
to substitute the proxy.** A5, clause 4.

---

## Phase 3g — purged, embargoed walk-forward CV

The last missing piece of the engine, and the one that most often gets skipped.

Ordinary k-fold cross-validation leaks in time series: a training fold that
sits immediately beside a test fold shares overlapping information, because a
126-session ranking window computed near the boundary contains data from both
sides. **Purging** drops training observations whose feature windows overlap the
test period. **Embargoing** additionally drops a buffer after each test fold,
because serial correlation persists past the formal boundary.

Deliverable: `backtest/validation.py`, with tests proving that a deliberately
leaked feature is caught by the purged split and missed by a naive one. Same
pattern as the self-deception suite — the test must fail against the broken
version, or it proves nothing.

**Why this matters more here than in most projects.** The universe itself is
built from a 126-session turnover window (A5) and every candidate signal will
use a lookback of similar length. A fold boundary drawn without purging puts
training and test observations that share up to 126 sessions of input on
opposite sides of a line that is doing no work. The resulting Sharpe is not
merely optimistic — it is measuring the overlap.

---

## Phase 4 — testing the hypotheses, for real

Only after both remaining downloads land.

Order matters, and the order is fixed here so it cannot be chosen later to suit
whichever result appears first:

1. **H2 first** — net benchmark outperformance. It is the question the project
   exists to answer, and it is the one most likely to end the project early. Any
   other order risks spending months on H1 and H3 before discovering H2 fails.
2. **H1** — momentum monotonicity
3. **H3** — quality filter
4. **H5** — monthly versus weekly rebalancing
5. **H6** — governance and surveillance exclusions

Every run is entered in the trial register **before** its result is read. Each
one raises the DSR bar for all the others — with 5 trials the chance-expected
best Sharpe is already 1.19, and at 25 it is 2.00.

**Amendment A1 stands:** H3, H4 and H6 were named as the only plausible sources
of edge over a 0.22% momentum ETF. H4 is gone. Two remain.

---

## Phase 5 — the allocation system

Not a trading system. A decision-support layer over the whole balance sheet,
which is where the money actually is: one percentage point across ₹65.4 lakh is
₹65,403 a year, against ₹15,000 from a successful strategy on ₹3 lakh.

Four components:

1. **Declared target allocation with rebalancing bands.** Gold reached 25% by
   appreciation, not decision. A band rule trims it mechanically and never needs
   a view on anything.
2. **Drift monitor.** Current versus target, with the rupee trade needed to
   close it, and whether that trade is worth its own cost.
3. **Pre-trade calculator.** Cost, tax, holding-period and exit-window
   consequences of a decision **before** it is made. The cost model already does
   this to the paisa; it needs a front door.
4. **Belief checker — BUILT, 2026-08-30.** Any claim about market state tested
   against the archive before it is acted on. Built because a confident belief
   that the market was "at one of its lowest points" turned out to be the
   **97th percentile** of 23 years — off by roughly 90 percentiles, and about
   to inform real decisions.

   Governed by **Amendment A13**: it describes and never recommends, it spends
   no trial-register slots, an encouraging result needs a non-overlapping second
   window before it may inform a decision, every check is logged in
   `docs/beliefs_log.md`, and a comparator that does not span the window makes
   the check **refuse** rather than quietly answer a shorter question.

   `src/indian_equity_research/research/beliefs.py` ·
   `scripts/check_belief.py` · `docs/beliefs_log.md`

   **First check, B1** — mid- and small-caps against the archive, 2005–2026 —
   found the original comparison was an index against a *blended* portfolio, so
   the real gap was +8.9% rather than 1–2%; that Midcap 150 and Smallcap 250 are
   not one story (61% of windows against 53%, and −5.4% average loss against
   −20.5% over five years); and that the extreme reading sits at **six months**
   (91st percentile) rather than at the twelve the claim was about. It is
   recorded as **provisional**, because the correct comparator is the Nifty 100
   and its archive does not yet reach 2005.

---

## Phase 6 — instruments not yet explored

Written research, no code. Real yields, tax treatment, liquidity, minimums,
and what can go wrong.

| Instrument | Why it is on the list |
|---|---|
| **RBI Retail Direct** (G-Secs, SDLs, T-Bills) | Buy sovereign debt directly, no intermediary, no expense ratio. Currently 47% of the portfolio sits in bank deposits at 6.6% |
| **Arbitrage funds** | Equity taxation on a debt-like risk profile; often better after tax than an FD for a 1–3 year horizon |
| **REITs / InvITs** | Yield plus some inflation linkage, in a portfolio with zero property exposure |
| **International equity** | The entire ₹65 lakh is one country's economy and currency |
| **Corporate bonds / NCDs** | Higher yield, real credit risk — the risk has to be understood, not assumed away |
| **F&O, legitimate uses only** | Covered calls, protective puts, defined-risk spreads. Governed by the Amendment A6 gate |

---

## Phase 7 — paper trading, then the decision

Governed entirely by **Amendment A6**:

- **₹3,00,000 cap**, as a rupee figure, raised only by dated amendment
- **Two full years** of paper trading from the first live signal
- Abandoned if it fails to beat Baseline B3 net of costs and tax, or fails DSR
  against the trial register at that date
- Derivatives only **after** the equity system passes — never as a response to
  it disappointing

---

## Removed as redundant

- **"Reconstruct the Nifty 100 or use a liquidity proxy"** — settled by
  Amendment A5. Both, in a fixed order, with the proxy carrying no evidential
  weight.
- **"Decide whether to cap capital"** — settled by Amendment A6.
- **"Consider rewriting in C++"** — dropped. The full pipeline runs in about 30
  seconds on 1.4M rows. There is no performance problem to solve, and the
  bottleneck was never CPU.
- **"Evaluate the shared F&O data collector"** — assessed and declined. It
  collects forward-only options data, requires a year-long broker token in
  unvetted code, and is out of charter scope.
- **"Estimate Nifty 100 TRI by adding a dividend yield"** — becomes redundant
  the moment download #2 lands. Delete the synthetic-TRI helper then.

---

## Standing rules

1. `HYPOTHESES.md` governs. This file plans; it does not authorise.
2. No result on the proxy universe enters the trial register (A5).
3. Capital and derivatives are bounded by A6.
4. Every backtest configuration goes in the trial register, including abandoned
   ones. That count is the DSR denominator.
5. A number computed on data with a known defect is discarded, not reported
   with a caveat.

---

## The Nifty 200 extension — attempted, blocked on data quality

**Both datasets arrived and both are sound.** TRI: 5,626 levels 2004-2026, no
gaps over the test window, every session the Nifty 100 TRI has. Roster: 200
constituents as at 2026-08-29.

**The universe will not reconstruct.** Two independent approaches, both refused
by the gate Amendment A10 set:

| Approach | Result |
|---|---|
| Parse `Nifty 200` sections | 51 changes, **13 unapplied**, 9 inside the test window, size drifts 200 → 208 |
| `Nifty 100 ∪ Nifty Midcap 100` | **14 unapplied**, 31 of 38 snapshots off 200 (187–205) |

The definitional identity was verified exact on the real rosters — no Nifty 100
name outside the Nifty 200, remainder exactly 100 — so the union is the right
construction. It still fails, and every failure is in the mid-cap half.

**Cause: the press-release archive is thin in its early years.**

```
releases held per year
  2015   18      2018   68      2021   47      2024   93
  2016   15      2019   84      2022   42      2025  165
  2017   30      2020   61      2023   41      2026   82 (to Aug)
```

Eight months between 2015 and 2017 have zero releases on disk. The failures
cluster there. The Nifty 100 survived the same gaps because it turns over about
two names per review; a 200-name universe carries several times that churn plus
intra-review maintenance changes, which is exactly what is missing.

### Ruled out cheaply, recorded so they are not retried

* **Starting the study later does not help.** Rolling back only to 2021 still
  leaves 3 unapplied changes; to 2018, nine. The gaps are spread across the
  whole period, not confined to the thin 2015–2017 years.
* **Backfilling 2015–2017 releases is therefore necessary but not sufficient**,
  and is not worth doing on its own.

### Three routes declared by Amendment A11, none yet run

| Route | Needs | Status |
|---|---|---|
| **1. Sensitivity band** — run the Nifty 200 study twice, full reconstruction against one excluding the 20 implicated securities; disagreement on any criterion forces INCONCLUSIVE | nothing | **not run** — see below |
| **2. Size tiers** — Nifty 50 vs Nifty Next 50 | done | **RUN, trial #6: SUGGESTIVE NEGATIVE.** Both universes reconstruct with 0 unapplied. Next 50 IC +0.0414 against Nifty 50's +0.0360 — direction as predicted, but t = 1.57 against a required 3.0 |
| **3. Hand-adjudicate the 13 changes** — evidence-only, the method that fixed the Nifty 100's 2021 gap | your time | worklist written, not started |

**Route 2's result changes what Route 1 is worth.** The nearest explanation for
trials #2 and #3 — that the Nifty 100 is too large-cap — moved the IC by 0.005
and left it indistinguishable from noise. Spending trials #4 and #5 to ask a
harder version of a question that has just been largely answered raises the
Deflated Sharpe bar for everything after it. Worth a decision before running.

Route 3 first if there is time: if it closes, Route 1 is unnecessary and the
study runs with no caveat. Worklist in
[`docs/nifty200_adjudication_worklist.md`](docs/nifty200_adjudication_worklist.md).

### The two roster downloads Route 2 needs

```
https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv
  -> data/raw/archive/nse_nifty50_constituents/nse_nifty50_constituents_YYYY-MM-DD.csv

https://nsearchives.nseindia.com/content/indices/ind_niftynext50list.csv
  -> data/raw/archive/nse_niftynext50_constituents/nse_niftynext50_constituents_YYYY-MM-DD.csv
```

Both are checkable against what we already hold: each must contain exactly 50
names, and their union must equal the Nifty 100 roster exactly. Date the
filenames with the day you download them.

The union machinery (`reconstruct_union`, `NIFTY_MIDCAP_100`) is kept and
tested. It is blocked on inputs, not logic — and its self-check worked exactly
as designed, catching the drift rather than serving a universe that looked fine
and was wrong.
