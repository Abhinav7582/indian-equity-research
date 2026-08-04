# Data Principles

**These rules are mandatory. A violation invalidates every downstream result,
usually silently and usually in a flattering direction.**

That last point is what makes these rules worth enforcing before any data
exists. Most data defects make a backtest look *better*, so nothing prompts
you to go looking for them.

---

## 1. Point-in-time correctness

A feature computed for date *T* may use only information that was **publicly
available on or before date *T***.

Every record carries three timestamps:

| Field | Meaning |
|---|---|
| `event_date` | When the thing happened (quarter end, ex-date, trade date) |
| `published_at` | **When it became publicly available.** The only field features may filter on. |
| `ingested_at` | When this system stored it. For audit and replay. |

**The canonical failure.** A June-quarter result is published on 14 August. A
feature dated 31 July that uses June-quarter data has a six-week look-ahead.
The backtest will look excellent. It will be fiction.

Enforcement: features query a view filtered on `published_at <= as_of_date`.
They never query the raw table directly.

## 2. No look-ahead data

Beyond fundamentals, the recurring sources of look-ahead:

- **Revised macro series.** GDP, IIP and CPI are revised. Using the current
  vintage as if it had been known then is look-ahead. Store the release
  vintage.
- **Index membership.** Applying today's Nifty 100 to 2015 assumes knowledge
  of which companies would succeed.
- **Restated financials.** Using a restated figure as if it were the original
  is look-ahead. Keep every vintage; never overwrite.
- **Announcement timing.** An announcement *date* is not an announcement
  *time*. A signal from a post-close disclosure may not trade that day's close.
- **Adjusted prices.** A price series adjusted with today's full corporate
  action history embeds future knowledge if used naively for point-in-time
  ratios. Adjust for returns; keep unadjusted prices for anything that depends
  on the actual traded price.

## 3. No survivorship bias

Delisted, suspended, merged and renamed securities remain in the historical
universe with an explicit terminal return.

Silently dropping failures is the single most common and most flattering
research defect in retail backtesting. A universe built from currently listed
companies is a universe selected on having survived.

Where a delisting was compulsory or followed a fraud finding and no realisable
value is recoverable, the terminal return is recorded as **−100%** unless
documented evidence supports otherwise.

## 4. Historical universe reconstruction

Universes are reconstructed point-in-time from index rebalance announcements
and are stored with `effective_from` / `effective_to` ranges.

**Validation gate:** an equal-weighted portfolio reconstructed from the stored
membership must track the published index within a documented tolerance. If it
does not, the membership data is wrong and no research may proceed on it.

## 5. ISIN is the stable identifier

**Join on ISIN. Never on ticker symbol.**

Symbols are reused after delisting, change on corporate restructuring, and
differ between NSE and BSE. A pipeline keyed on symbol will eventually
attribute one company's history to a different company, and will do so
silently.

A `symbol_history` table maps ISIN to symbol over time so that historical
files keyed on symbol can still be resolved correctly.

## 6. Immutable raw data

`data/raw/` is **append-only**. Files are stored exactly as received, with the
retrieval timestamp and source URL recorded.

Raw data is never edited, cleaned or corrected in place. Corrections are new
records or downstream transformations. If a source republishes a corrected
file, both versions are kept.

Rationale: without immutable raw data you cannot reproduce a past result, and
you cannot distinguish "the model changed" from "the data changed."

## 7. Versioned transformations

Every derived dataset records the code version that produced it. Feature sets
carry an explicit version identifier. A model artefact records the feature-set
version and a hash of its training data.

If you cannot say which code and which data produced a number, that number is
not evidence.

## 8. Reproducibility

Given the raw archive and a commit hash, any historical result must be
reproducible exactly. This implies deterministic transformations, pinned
dependencies (`uv.lock` is committed) and seeded randomness wherever
randomness is used.

## 9. Corporate-action validation

Corporate actions are the most common source of silent corruption. The
validator is written **before** the adjustment engine, not after.

Mandatory checks:

- Every absolute daily return greater than 25% is explained by a documented
  corporate action or a documented market event. Unexplained outliers block
  the pipeline.
- Adjustment factors are cumulative, monotonic and reconcile across the full
  history.
- A reconstructed index tracks its published counterpart within tolerance.
- Split and bonus ratios reconcile against the change in shares outstanding.

## 10. Complete data lineage

Every stored record can be traced to the raw file it came from, the retrieval
time, and the transformation version applied. Lineage is a stored column, not
tribal knowledge.

## 11. Explicit source and publication timestamps

Never infer a publication time. If a source does not provide one, record that
it is unknown and treat the record as available only from the **end of the
following trading day**. Guessing a timestamp optimistically is look-ahead
wearing a disguise.

## 12. No silently revised fundamental data

Financial statements are restated. Storage is append-only with a
`revision_seq`; the original vintage is never overwritten.

Convenience data providers frequently serve only the latest restated figures.
Such sources are acceptable for exploration and **unacceptable as a backtest
input**, because they cannot answer "what did this look like on that date."

---

## Secrets and licensing

- **Secrets never appear in YAML.** `configs/*.yaml` holds non-sensitive
  settings only. Credentials come from `.env` (git-ignored) or the process
  environment.
- **Exchange data is licensed.** NSE's data usage policy restricts automated
  collection and redistribution. Access must be rate-limited, personal,
  non-commercial and never redistributed. Any intention to share results,
  publish signals or charge anyone requires a written licence and legal advice
  first.
- **Raw market data is not committed to git.** `data/` is ignored apart from
  its `.gitkeep` placeholders.

## Archive prospectively

Some data cannot be backfilled at any price, because the source overwrites it:

- Exchange surveillance lists (ASM / GSM)
- Shareholding-pattern pages
- Corporate announcement pages
- Instrument master snapshots
- Market-depth snapshots

**Archiving these begins on day one, before it is known whether they will be
used.** A day not archived is a day permanently lost. This is the cheapest
high-value action available to the project and the only one with a deadline.
