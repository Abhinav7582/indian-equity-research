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
| 4 | Hypothesis testing on the real universe | **H2 and H1 both REJECTED on the Nifty 100** (trials #2 and #3, 2026-08-23). H2: net CAGR **10.85%** vs **17.13%** for the Nifty 100 TRI; the signal lost **3.32% before any cost**, so costs were not the cause. H1 then explained why — mean rank IC **+0.0378** with **t = 1.47** (needs 3.0), spread positive in **2 of 5** sub-periods, and **decile 10 returned −0.138%/month** against D9's +0.403%. The effect is weak, unstable, and absent from the top decile a small book must hold. Holdout untouched. **Nifty 200 extension declared by Amendment A10**, blocked on two datasets (see below); the code now takes the index as an argument and the Nifty 100 result reproduces identically through it. H3, H5, H6 untested |
| 5 | Allocation system | Not started |
| 6 | Unexplored instruments research | Not started |
| 7 | Paper trading, then the A6 decision | Not started |

**883 tests · ruff clean · mypy strict clean · 12/12 mutation bugs caught.**

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
4. **Belief checker.** Any claim about market state tested against the archive
   before it is acted on. Built because a confident belief that the market was
   "at one of its lowest points" turned out to be the **97th percentile** of 23
   years — off by roughly 90 percentiles, and about to inform real decisions.

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

## Blocked: the Nifty 200 extension (Amendment A10)

The design is fixed and the code takes the index as an argument
(`--index "Nifty 200"`). Two datasets are missing and nothing can run until
both are on disk. **Download them before the next session.**

### 1. Nifty 200 constituent roster

The reconstruction rolls today's roster backwards through the published
changes, so it needs a starting point.

- `https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv`
- Save as
  `data/raw/archive/nse_nifty200_constituents/nse_nifty200_constituents_YYYY-MM-DD.csv`
- **The date in the filename is load-bearing.** It decides which
  reconstitutions are already reflected in the roster. The 2026-09-30
  reconstitution is already published; dating the file wrongly would undo a
  change that has not happened yet, and `load_roster` refuses a filename it
  cannot read a date from.

### 2. Nifty 200 Total Return Index, 2015–2026

- **https://www.niftyindices.com/reports/historical-data**
- Index Type **Equity** → **Total returns Index Values**
- Sub-Index **Broad Market Indices** → Index **NIFTY 200**
- One year per download if the site caps the range
- Save to `data/raw/indices/nifty200_tri/nifty200_tri_YYYY.csv`

Header should read `"IndexName","Date","Total Returns Index"`.

**Not a substitute:** the archive already holds `nifty200_momentum30` and a
75:25 blend. Benchmarking a momentum strategy against a momentum index answers
a different question and would flatter or damn it for the wrong reason.

### Already verified without the data

The press releases parse. **Forty-eight** substantive Nifty 200 changes come out
of the existing circular archive, 2013–2026, and forty-four have a net size
change of exactly zero as a fixed-size index requires. Four do not:

```
2016-04-01  ind_prs22022016_2.pdf   net +2   unexplained
2020-06-26  ind_prs10062020.pdf     net -5   unexplained
2023-09-29  ind_prs17082023.pdf     net +1   TATAMTRDVR in
2024-08-30  ind_prs23082024_1.pdf   net -1   TATAMTRDVR out
```

The last two are the Tata Motors DVR pair already understood from the Nifty 100
reconstruction. The first two are not yet explained, and A10 makes the run
conditional on `roll_back` reporting zero unapplied changes — the same standard
the Nifty 100 had to meet.

### Then

```bash
uv run python scripts/build_membership.py --index "Nifty 200"   # must come out clean
uv run python scripts/run_h1.py --index "Nifty 200"             # trial #4
uv run python scripts/run_h2.py --index "Nifty 200" --holdings 20   # trial #5
```
