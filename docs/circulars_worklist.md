# Press-release worklist — 15 files needing human eyes

**Generated 2026-08-12** from 1,037 downloaded releases.

---

## Where this came from

The parser reads 1,037 PDFs and extracts Nifty 100 membership changes. Most
need no attention. The list below is what remains after four rounds of
narrowing:

| | |
|---|---:|
| Total downloaded | 1,037 |
| Announced before July 2015 — **out of scope** | 301 |
| No Nifty 100 section at all — correctly ignored | 693 |
| Parsed cleanly | 28 |
| **Need a human** | **15** |

**Why pre-July-2015 is out of scope.** The bhavcopy archive begins 2015-01-01,
and the universe needs 126 sessions of history before it can rank anything, so
the earliest possible backtest start is around October 2015. A membership
change effective before then cannot affect any result. That single observation
removed 301 files from the list.

**The net size change across all 28 parsed changes is exactly zero**, which is
what a fixed-size index requires. That is the strongest available signal that
nothing is currently mis-parsed.

---

## Coverage, and the three real gaps

Each year needs one review around March/April and one around September/October.

| Year | Effective dates found | |
|---|---|---|
| 2015 | 09-28, 10-19 | ok |
| **2016** | **none** | **both missing** |
| 2017 | 03-31, 05-26, 09-29 | ok |
| 2018 | 04-02, 09-28 | ok |
| 2019 | 03-29, 09-27 | ok |
| **2020** | 03-19, 03-27, 06-26, 07-31 | **H2 missing** |
| **2021** | 03-31, 06-30 | **H2 missing** |
| 2022 | 03-31, 08-08, 09-30 | ok |
| 2023 | 03-31, 07-13, 09-29 | ok |
| 2024 | 03-28, 09-30 | ok |
| 2025 | 03-28, 09-30 | ok |
| 2026 | 03-30, 09-30 | ok |

**2016 is the priority.** A whole year of membership is unknown, and every
backtest spanning it is affected.

---

## What to do with each file

Open the PDF, find the section headed `Nifty 100` or `CNX 100 Index`, and
record what it says. Add the result to
`data/reference/index_changes_manual.md` (create it; `data/` is git-ignored)
using this format:

```
| file | effective_from | excluded | included |
|---|---|---|---|
| ind_prs22022016_2.pdf | 2016-03-31 | ABC, DEF | GHI, JKL |
```

Two things to capture exactly:

1. **The effective date stated in the text** — not the date in the filename.
   They differ by about five weeks.
2. **Which symbols are excluded and which are included.** Getting these the
   wrong way round is undetectable downstream.

If a release turns out not to change the Nifty 100, write `no change` — that is
a useful answer and stops it being revisited.

---

## The 15 files

### Priority 1 — the 2016 gap (3 files)

Nothing is known about 2016 membership. Start here.

| Announced | File | Problem |
|---|---|---|
| 2016-02-22 | `ind_prs22022016_2.pdf` | section found, tables not detected |
| 2016-08-12 | `ind_prs12082016.pdf` | section found, tables not detected |
| 2016-10-17 | `ind_prs17102016.pdf` | section found, tables not detected |

*"Section found, tables not detected"* means the heading is there but the
exclusion/inclusion tables did not parse — usually a layout the extractor
mangled. The content is almost certainly readable by eye.

### Priority 2 — the two missing H2 reviews (3 files)

| Announced | File | Problem | Note |
|---|---|---|---|
| 2021-08-23 | `ind_prs23082021.pdf` | scanned, 0 characters | **the missing Sept 2021 review** |
| 2021-08-23 | `ind_prs23082021_1.pdf` | scanned, 35 characters | same date, second release |
| 2020-08-20 | `ind_prs20082020.pdf` | section found, tables not detected | **the missing Sept 2020 review** |

### Priority 3 — scanned PDFs (9 files)

No extractable text at all. These are images. Read them on screen.

| Announced | File |
|---|---|
| 2018-06-16 | `ind_prs16062018.pdf` |
| 2018-09-10 | `ind_prs10092018.pdf` |
| 2018-09-18 | `ind_prs18092018.pdf` |
| 2018-09-24 | `ind_prs24092018.pdf` |
| 2018-09-24 | `ind_prs24092018_1.pdf` |
| 2018-09-25 | `ind_prs25092018.pdf` |
| 2018-12-03 | `ind_prs03122018.pdf` |
| 2023-06-19 | `ind_prs19062023.pdf` |
| 2023-06-26 | `ind_prs26062023.pdf` |

2018 and 2023 already have both reviews covered, so these are likely interim
changes or releases about other indices. Lowest priority, but they must be
checked rather than assumed, because an unread interim change is exactly the
kind of gap that makes a reconstruction drift.

---

## One judgement call the parser cannot make

**2020 has two reconstitutions that overlap.**

```
2020-03-27  out: ASHOKLEY, IBULHSGFIN, L&TFH, IDEA, YESBANK
            in:  ADANITRANS, IDBI, NAUKRI, LTI, TORNTPHARM

2020-06-26  out: ASHOKLEY, IBULHSGFIN, L&TFH, NIACL, IDEA, TATAMTRDVR
            in:  ABBOTINDIA, IGL, NAUKRI, MUTHOOTFIN, TORNTPHARM
```

The same names appear in both. NSE deferred the March 2020 reconstitution
because of the COVID crash, so **one release supersedes the other** — they are
not two separate events to be applied in sequence. Applying both would remove
companies twice and corrupt every subsequent date.

Read both releases and decide which actually took effect. Record the answer,
and the reason, in the manual file. Nothing in the text lets code work this
out.

---

## When the list is done

```bash
uv run python -m indian_equity_research circulars --parse
```

Two conditions must hold before the reconstruction can be trusted:

1. **Net size change is zero.** It already is, and it must stay that way.
2. **Every year has both reviews.** 2016, 2020-H2 and 2021-H2 currently do not.

Then `reconstruct_membership` can walk backwards from today's constituent list.
It refuses to return a membership that is not exactly 100 members, so a
remaining gap will announce itself rather than pass silently.

**If a release genuinely cannot be found or read, record that too.** Under
Amendment A5 clause 4 a documented gap is a finding to report — it is not a
licence to fall back on the proxy universe.
