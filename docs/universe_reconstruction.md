# Reconstructing the historical Nifty 100

**Written 2026-08-10.** Supports Amendment A5, which forbids testing any
hypothesis on the proxy universe.

---

## They are not called circulars

An earlier note in this repository called these "NSE rebalance circulars". That
was wrong and would have sent you looking in the wrong place. NSE Indices
publishes membership changes as **press releases**.

| | |
|---|---|
| Publisher | NSE Indices Limited (formerly IISL) |
| Document | *"Replacements in indices"* press release |
| Decided by | Index Maintenance Sub-Committee (Equity) |
| URL pattern | `https://www.niftyindices.com/Press_Release/ind_prsDDMMYYYY.pdf` |
| Listing page | https://www.niftyindices.com/media |
| Announced | late **February** and late **August** |
| Effective | **31 March** and **30 September** (from close of the previous day) |

### The title changed over the years

The document is the same; only its heading on the media page moved around.

| Era | Title on the media listing |
|---|---|
| ~2015 | **"Change in Indices w.e.f \<date\>"**, or "Change in \<specific indices\> w.e.f \<date\>" |
| Current | **"Replacements in indices"** |

Search the listing for **"Change in"** as well as "Replacements". Both are the
same kind of document and both are needed.

Confirmed working examples:

- `ind_prs22082025.pdf` — 22 Aug 2025, effective 30 Sep 2025
- `ind_prs23082024.pdf` — 23 Aug 2024
- `ind_prs28022024.pdf` — 28 Feb 2024, effective 28 Mar 2024
- `ind_prs24022022_1.pdf` — 24 Feb 2022 (note the `_1` suffix)

The date in the filename is the **announcement** date, not the effective date.
Some have a `_1` or `_2` suffix when more than one was issued that day.

---

## What the document actually contains

Each release covers every Nifty index. The section you need is headed
**"3) Nifty 100"** under *"A. Replacements on account of semi-annual review of
broad market indices"*. From the August 2025 release, verbatim:

```
3) Nifty 100
The following companies are being excluded:
Sr. No. Company Name Symbol
1 Dabur India Ltd. DABUR
2 Hero MotoCorp Ltd. HEROMOTOCO
3 ICICI Prudential Life Insurance Company Ltd. ICICIPRULI
4 IndusInd Bank Ltd. INDUSINDBK
5 Swiggy Ltd. SWIGGY
The following companies are being included:
Sr. No. Company Name Symbol
1 Hindustan Zinc Ltd. HINDZINC
2 Max Healthcare Institute Ltd. MAXHEALTH
3 Mazagoan Dock Shipbuilders Ltd. MAZDOCK
4 Siemens Energy India Ltd. ENRIN
5 Solar Industries India Ltd. SOLARINDS
```

**The volume is small.** Five in, five out at that review. Across roughly 22
semi-annual reviews since 2015 the Nifty 100 has perhaps 100–150 total changes.
This is a very tractable dataset, not a research project of its own.

---

## The index was not always called the Nifty 100

**IISL renamed every index on 22 September 2015.** Before that date the same
index is called **"CNX 100 Index"**. From `ind_prs24082015.pdf`, verbatim:

```
2) CNX 100 Index
The following company is being excluded:
Sr. No. Company Name Symbol
1 Crompton Greaves Ltd. CROMPGREAV
```

| Current name | Pre-rebrand name |
|---|---|
| Nifty 100 | CNX 100 |
| Nifty 50 | CNX Nifty / S&P CNX Nifty |
| Nifty Next 50 | CNX Nifty Junior |
| Nifty 200 | CNX 200 |
| Nifty 500 | CNX 500 |
| Nifty Midcap 100 | CNX Midcap |

Older headings also carry a trailing **"Index"** that current ones drop.

The parser handles all of this through `INDEX_ALIASES`. It matters because
searching a 2015 release for "Nifty 100" finds nothing — and "this release did
not touch the index" and "the index was called something else here" are
completely different facts that would otherwise look identical.

---

## Two important corrections this uncovered

**1. The effective date is not what Amendment A5 assumed.**
A5 declared the proxy rebalances on *"the first session of April and October"*.
NSE actually reconstitutes effective **30 September / 31 March**, from the close
of the previous day — roughly one session earlier. A5 is scaffolding and does
not need amending for this. **The real universe must use the effective dates
printed in each release**, not a rule of thumb.

**2. Semi-annual reviews are not the only changes.**
Mergers, acquisitions, demergers and suspensions trigger **ad-hoc replacements
between reviews**, each with its own press release. A reconstruction built only
from the February and August releases will drift out of alignment over time.
Those interim releases must be collected too, or the gap has to be reported as a
known limitation under A5 clause 4.

---

## How to collect them

### Step 1 — the baseline

Get today's constituent list first. Everything is reconstructed backwards from it.

- `https://nsearchives.nseindia.com/content/indices/ind_nifty100list.csv`
- Save to `data/raw/circulars/baseline_nifty100_YYYY-MM-DD.csv`

### Step 2 — the releases

**The listing cannot be scraped directly.** The year filter on
`https://www.niftyindices.com/media` runs in the browser, not in the URL:
fetching `/media?year=2015` returns byte-for-byte the same page as `/media`,
covering only the most recent ten months or so. Confirmed by trying it.

So there are two routes, and doing both is the honest approach.

#### Route 1 — save the listing, let the tool read it *(preferred)*

For each year 2015–2026:

1. Open https://www.niftyindices.com/media
2. Select the year in the filter
3. **File → Save Page As → Webpage, HTML Only**
4. Save into `data/raw/circulars/listings/media_YYYY.html`

Twelve saves, no judgement calls. `extract_release_links` then pulls every
URL, date and title out of them, `is_possibly_relevant` filters, and the
fetcher downloads. Nothing is guessed because the listing is authoritative.

#### Route 2 — sweep the predictable dates

Release URLs are deterministic (`ind_prsDDMMYYYY.pdf`), and the semi-annual
reviews are announced inside narrow windows: **15 Feb – 5 Mar** and
**5 Aug – 5 Sep**. `plan_sweep` generates **439 candidate URLs** for 2015–2026
— about fifteen minutes at the two-second default.

Same-day variants (`_1`, `_2`, …) are *not* planned. They are followed only on
dates that actually produced a release, which keeps the request count down and
still finds the `_3` and `_4` that busy days occasionally carry.

**Route 2 alone is not sufficient.** It catches the semi-annual reviews and
misses interim changes, which fall on unpredictable dates. That is survivable
rather than fatal: `reconstruct_membership` refuses to return a membership that
is not exactly 100, so a missing release surfaces as an error naming the
period. Sweep, reconstruct, read the failure, sweep that window narrowly.

Save everything as `data/raw/circulars/ind_prsDDMMYYYY.pdf` — keep NSE's own
filename so the announcement date is never lost.

Expect roughly **24 semi-annual releases plus 10–20 interim ones**.

### Step 3 — parse

`indian_equity_research.market.index_changes` extracts the exclusion and
inclusion tables from the release text. It is tested against a fixture taken
verbatim from the August 2025 release.

### Step 4 — walk backwards

Membership at any past date is the current list with every subsequent change
undone: for each release later than that date, **add back what was excluded and
remove what was included**.

The reconstruction is self-checking. If applying the changes in reverse ever
produces a membership count other than 100, a release has been missed, and that
must be reported rather than patched.

---

## Licensing

Press releases are public. Redistributing them, or a database derived from them,
is a different question. See the licensing section of
[`data_principles.md`](data_principles.md). For personal research this is fine;
publishing a reconstructed constituent history is not obviously fine.

---

## What to do if some cannot be found

Report it. **Amendment A5, clause 4:** *"If the circulars cannot be obtained,
that is a finding to be reported — not a licence to substitute the proxy."*

A partial reconstruction with documented gaps is a legitimate research artefact.
A complete-looking one with silently interpolated membership is not.
