# Point-in-Time Data Acquisition (Phase 2 Groundwork)

**Added: 2026-08-04.** Concrete survey of what is obtainable, at what cost,
with what defects. Read with [`data_principles.md`](data_principles.md),
which states the rules this document has to satisfy.

**Bottom line: the data layer is free in money and expensive in effort, and it
is the only real bottleneck in this project.**

---

## 1. The finding that will cost you the most time

**NSE changed its bhavcopy format mid-history.** The legacy daily bhavcopy was
discontinued with effect from **8 July 2024**, replaced by the **CM-UDiFF
Common Bhavcopy Final** (zipped CSV), per NSE Circular No. 62424 dated
12 June 2024 `[P]`.

Consequences you must design for from the first line of ingest code:

1. **Two parsers, not one.** Pre-2024-07-08 legacy layout, post-2024-07-08
   UDiFF layout, selected by date.
2. **A column-mapping layer.** Field names and some semantics differ between
   the two. Map both onto one internal schema; never let the raw shape leak
   upward.
3. **A boundary test.** Ingest the last legacy day and the first UDiFF day and
   assert that the same securities produce the same close prices. If they
   don't, the mapping is wrong.
4. **Verify the archive depth yourself.** Some endpoints only serve
   2020-onward. **Do not assume 15–20 years is available from one URL** —
   confirm the earliest retrievable date per source before planning around it.
   If deep history is only available in the legacy format, that changes the
   Phase 2 estimate materially.

⚠ URLs are deliberately not recorded here. NSE changes them, and a stale URL
in a document is worse than no URL. Discover current endpoints from
[NSE's All Reports page](https://www.nseindia.com/all-reports) at build time.

## 2. Source catalogue

### Tier 1 — free, primary, essential (P0)

| Data | Source | Notes |
|---|---|---|
| Daily EOD OHLCV, all securities | NSE bhavcopy (UDiFF + legacy), BSE bhavcopy | **The survivorship-bias-free base.** Delisted names appear naturally in historical files, which is the whole point of using bhavcopy rather than a current-listings API |
| Corporate actions | NSE / BSE corporate-action files | Build the validator first (see `data_principles.md` §9) |
| Index membership | NSE Indices rebalance announcements | Laborious to reconstruct; no clean historical file exists |
| Index levels PR **and TRI** | NSE Indices historical data | **TRI is mandatory** for benchmarking; PR overstates your alpha by the dividend yield |
| Trading calendar | NSE holiday calendar | Special sessions (Muhurat) break naive resampling |
| ASM / GSM / T2T lists | NSE, BSE surveillance pages | **No reliable historical archive. Archive prospectively — see §4** |
| India VIX | NSE | Regime input for H4 |
| Industry classification | NSE | Needs `as_of` dating; classifications change |
| Bulk & block deals | NSE, BSE | Clean same-day timestamps |
| Shareholding & pledge | Exchange LODR filings | Quarterly, ~21-day lag, pages overwritten |
| Corporate announcements | NSE, BSE | **Best timestamps available anywhere in this project** |
| Macro | RBI DBIE, MoSPI | **Store the release date, not just the reference period** |

### Tier 2 — paid, convenient, and mostly unsuitable for backtesting

| Provider | Approx. price (2026) | Verdict |
|---|---|---|
| Trendlyne | from ~₹2,090/yr `[S]` | Exploration only |
| Tijori Finance | ~₹3,500/yr `[S]` | Interesting for operational metrics parsed from annual reports; not point-in-time |
| Screener.in Premium | ~₹4,999/yr `[S]` | ~10-year depth, good query builder. Exploration only |
| CMIE Prowess / Capitaline | ₹1 lakh+ `[I]` | **The correct answer if affordable.** Genuinely point-in-time-capable Indian fundamentals |
| Refinitiv / Bloomberg / FactSet | ₹ lakhs–crores | Out of reach; accept the gap |

> **The trap.** Every Tier 2 retail provider serves the **latest restated**
> financials. They cannot answer *"what did this look like on that date."*
> Using them in a backtest is a silent look-ahead that will make your results
> look better. They are fine for exploration and **disqualified as a backtest
> input**. Verify prices and any point-in-time claims with the vendor directly
> before paying — the figures above are secondary-source and change.

Unofficial API wrappers around these platforms exist. They violate the
platforms' terms in most cases, break without warning, and should not be a
dependency of anything you intend to trust.

### Tier 3 — blocked, and worth accepting as blocked

**Analyst consensus estimates.** Revisions and forward-looking SUE are among
the best-evidenced signals in the literature and are effectively unobtainable
at retail cost in India. Accept the gap; do not build a bad proxy and pretend
it is the same thing.

## 3. Licensing — the boundary, stated honestly

NSE's Data Usage and Sharing Policy prohibits **systematic or automated data
collection** without written consent, and prohibits redistribution outside a
licensing agreement `[P]`.

What this report can and cannot tell you:

- Downloading published EOD files for **personal, non-commercial,
  non-redistributive** research is what most Indian retail quants do, and is
  different in kind from high-frequency scraping of live pages.
- **These documents do not resolve where the line falls.** This is not legal
  advice.

**Operating rules regardless:** rate-limit aggressively; respect `robots.txt`;
prefer official bulk files over page scraping; cache locally and never
re-fetch what you already have; **never redistribute**. ⚠ If you ever intend
to publish results, share signals, or charge anyone, get a written data
licence and speak to a securities lawyer **first**.

## 4. Archive prospectively — the only task with a deadline

These sources **overwrite themselves**. Every day not captured is gone at any
price:

- ASM / GSM / surveillance lists
- Shareholding-pattern and pledge pages
- Corporate announcement listings
- Instrument master snapshots
- Market-depth snapshots (if ever wanted)

A cron job and a dated folder is enough. **Start before deciding whether the
data will be used** — H6 already records that its own evidence base may only
ever exist forward from 2026-08-04 for exactly this reason.

## 5. Phase 2 acceptance gates

Ingest is not "done" until all four pass:

1. **Corporate-action validator:** every absolute daily return > 25% is
   explained by a documented corporate action or documented market event.
2. **Index reconstruction:** an equal-weighted portfolio built from stored
   point-in-time membership tracks the published index within a documented
   tolerance.
3. **Survivorship check:** securities delisted during the sample are present
   in history with explicit terminal returns.
4. **Format-boundary check:** the legacy/UDiFF changeover produces identical
   prices for the same securities across the boundary.

Until these pass, no research may run on the data. A backtest on unvalidated
data is not a weak result — it is a meaningless one.

## 6. Realistic effort

| Task | Relative effort |
|---|---|
| Bhavcopy ingest, both formats, both exchanges | 3 RU |
| Corporate actions + validator | 3 RU |
| Point-in-time index membership reconstruction | 2 RU |
| Instrument master, ISIN/symbol history, calendar | 1 RU |
| Prospective archivers | **0.5 RU — do this first** |
| **Total** | **~10 RU**, over a quarter of the project to a live pilot |

Unglamorous, and the part that decides whether anything downstream is real.
