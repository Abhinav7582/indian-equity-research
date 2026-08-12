# Press-release worklist — closed

**Closed 2026-08-12.** Nifty 100 membership is reconstructed continuously from
July 2015 to August 2026 with **net size change zero** and **no unread release**.

> This file was a worklist three times over. It asked for 15 files by hand, then
> 11, then 2. Every reduction came from a parser defect, not from the documents
> being difficult. The final count of releases a human had to read is **one**.

---

## Where this ended

| | |
|---|---:|
| Releases downloaded | 1,037 |
| Announced before July 2015 — out of scope | 301 |
| No Nifty 100 change — correctly ignored | ~700 |
| **Parsed automatically** | **33** |
| **Read by eye** (scans) | **1** |
| Deferred, correctly dropped | 1 |
| **Changes applied** | **33** |
| **Net size change** | **0** |
| Unresolved | **0** |

**Why pre-July-2015 is out of scope.** Bhavcopy begins 2015-01-01 and the
universe needs 126 sessions of history, so the earliest possible backtest start
is around October 2015. A change effective before then cannot affect a result.

---

## Coverage

Each year needs a review around March/April and one around September/October.

| Year | H1 | H2 | Interim |
|---|---|---|---|
| 2015 | n/a | 09-28 | 10-19 |
| 2016 | 04-01 | 09-30 | 11-15 |
| 2017 | 03-31 | 09-29 | 05-26 |
| 2018 | 04-02 | 09-28 | |
| 2019 | 03-29 | 09-27 | |
| 2020 | 03-19 | 07-31 | 06-26, 09-25 |
| 2021 | 03-31 | 09-30 | 06-30 |
| 2022 | 03-31 | 08-08 | 09-30 |
| 2023 | 03-31 | 07-13 | 09-29 |
| 2024 | 03-28 | 08-30 | 09-30 |
| 2025 | 03-28 | 09-30 | |
| 2026 | 03-30 | 09-30 | |

---

## The four things that were actually wrong

### 1. September 2021 was in a release nobody expected

The worklist assumed the September 2021 review was announced in September. It
was not: neither `ind_prs15092021.pdf` nor `ind_prs20092021.pdf` mentions the
Nifty 100 at all, despite the latter being titled *"Replacements in indices"*
and dated ten days before the effective date.

It was in `ind_prs23082021.pdf` — a 29-page scan — on **page 5**, under
`3) NIFTY 100`. Found by rendering every page and OCR-ing it, then read by eye.

**−5 +5, effective 30 September 2021.** Recorded in the register; two
independent consistency checks passed (see that file).

### 2. Nine "scanned" releases were not index changes at all

All nine were rendered and OCR'd. None touches the Nifty 100. One is not even a
press release — `ind_prs16062018.pdf` is an **arbitration award** with IISL as
claimant, caught only because its filename matches the pattern.

### 3. A whole release format was invisible

`ind_prs23082024_1.pdf` (Tata Motors DVR cancellation) contains no
`N) Nifty 100` heading. It uses a different shape entirely: one paragraph naming
the security, then a table of *index names* it drops out of.

`parse_index_section` reported "this release does not change the index" —
confidently, and wrongly. `parse_index_list_exclusion` now handles it.

**How it was caught:** the reconstructed index had gained a net member over
twelve years. A fixed-size index cannot do that. Everything else about the
history looked fine.

The `+1` was one thread throughout — **TATAMTRDVR**, in 2016, out 2020, in 2023,
and out for good in 2024 when the DVR shares were cancelled.

### 4. A reconstitution that was announced and never happened

`ind_prs18022020.pdf` announced a −5 +5 review effective **27 March 2020**. NSE
then deferred it *"until further notice"* on 23 March, citing circuit breakers,
margin requirements and travel restrictions, and replaced it with the June
review effective 26 June.

Nothing in the February release says it was withdrawn. Applying both would have
removed five companies twice and left membership wrong for three months.

`DEFERRED_RELEASES` in `market/index_changes.py` records the mapping.

**Not deferred:** `ind_prs16032020.pdf`, the accelerated YES BANK removal
effective 19 March, which took effect before the deferral. Dropping that as part
of "March 2020" would be the opposite error and just as invisible.

---

## Two prefix traps, same shape, different places

NSE runs at least seven indices named `NIFTY100 <something>` — Equal Weight,
Liquid 15, Low Volatility 30, Quality 30, Alpha 30, ESG, Enhanced ESG.

- As a **section heading**: `4) NIFTY100 Low Volatility 30: No Change` in
  `ind_prs10092018.pdf`.
- As an **index-list row**: rows 1 and 11 of the DVR table are `Nifty 100` and
  `Nifty100 Equal Weight`.

A prefix match in either place attaches the wrong constituents and produces a
complete, plausible membership history that is not the Nifty 100. Both are
matched exactly and both are pinned by tests.

---

## Reproducing this

```bash
uv run python -m indian_equity_research circulars --parse
```

Two conditions, both now met:

1. Net size change is zero, or every non-zero entry is explained.
2. Every year has both reviews.

`reconstruct_membership` refuses to return a membership that is not exactly 100,
so a regression announces itself rather than passing silently.

**The one thing a fresh clone still needs.** `data/reference/index_changes_manual.md`
is git-ignored, because NSE prohibits redistribution and a transcribed
membership list is still NSE's data. `load_manual_register` fails loudly if it
is absent. That file documents how to regenerate itself.
