# Press-release worklist — 11 scanned PDFs, 2 of them critical

**Generated and revised 2026-08-12** from 1,037 downloaded releases.

> **Revision note.** The first version of this file listed 15 files and asked
> for manual work on 6 of them. That was premature — every one of those 6 was a
> parser bug, not a document needing human eyes:
>
> | Cause | Effect |
> |---|---|
> | NSE writes **"scrips"**, not "companies", in 2016 | closed the entire 2016 gap |
> | A release can carry **two sections for the same index** — an eligibility-criteria table and, further down, the replacement list | closed the 2020-H2 gap |
>
> What remains is only what genuinely cannot be read by machine: scanned images
> with no text layer.

---

## Where this stands

| | |
|---|---:|
| Total downloaded | 1,037 |
| Announced before July 2015 — **out of scope** | 301 |
| No Nifty 100 section — correctly ignored | ~690 |
| **Parsed cleanly** | **32** |
| **Need a human** | **11** |
| **Net size change** | **+1** |

**Why pre-July-2015 is out of scope.** Bhavcopy begins 2015-01-01 and the
universe needs 126 sessions of history, so the earliest possible backtest start
is around October 2015. A membership change effective before then cannot affect
any result.

---

## Coverage — one gap left

Each year needs a review around March/April and one around September/October.

| Year | Effective dates found | |
|---|---|---|
| 2015 | 09-28, 10-19 | ok |
| 2016 | 04-01, 09-30, 11-15 | ok |
| 2017 | 03-31, 05-26, 09-29 | ok |
| 2018 | 04-02, 09-28 | ok |
| 2019 | 03-29, 09-27 | ok |
| 2020 | 03-19, 03-27, 06-26, 07-31, 09-25 | ok |
| **2021** | 03-31, 06-30 | **H2 missing** |
| 2022 | 03-31, 08-08, 09-30 | ok |
| 2023 | 03-31, 07-13, 09-29 | ok |
| 2024 | 03-28, 09-30 | ok |
| 2025 | 03-28, 09-30 | ok |
| 2026 | 03-30, 09-30 | ok |

---

## Priority 1 — the missing September 2021 review (2 files)

**These two are the only thing blocking full coverage.**

| Announced | File | |
|---|---|---|
| 2021-08-23 | `ind_prs23082021.pdf` | scanned, 0 characters extractable |
| 2021-08-23 | `ind_prs23082021_1.pdf` | scanned, 35 characters extractable |

**How to hand these over:** open each PDF, find the section headed
`Nifty 100`, screenshot it, and paste the image into the conversation. Images
are readable directly — no transcription needed.

Capture the **effective date stated in the text** too. It is roughly five weeks
after the date in the filename, and must never be inferred.

## Priority 2 — scanned interim releases (9 files)

Both 2018 and 2023 already have their semi-annual reviews covered, so these are
interim changes or releases about other indices. Lower priority, but they must
be **checked rather than assumed** — an unread interim change is exactly what
makes a reconstruction drift out of alignment.

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

If a release does not change the Nifty 100, record `no change` — that is a
useful answer and stops it being revisited.

---

## Two judgement calls code cannot make

### 1. The 2020 supersession

```
2020-03-27  out: ASHOKLEY, IBULHSGFIN, L&TFH, IDEA, YESBANK
            in:  ADANITRANS, IDBI, NAUKRI, LTI, TORNTPHARM

2020-06-26  out: ASHOKLEY, IBULHSGFIN, L&TFH, NIACL, IDEA, TATAMTRDVR
            in:  ABBOTINDIA, IGL, NAUKRI, MUTHOOTFIN, TORNTPHARM
```

The same names appear in both. NSE **deferred** the March 2020 reconstitution
because of the COVID crash, so one release supersedes the other — they are not
two events to apply in sequence. Applying both would remove companies twice and
corrupt every date afterwards.

Read both and record which took effect, and why.

### 2. The +1 net size change

Three releases have a non-zero net:

| | | |
|---|---:|---|
| 2016-04-01 | +1 | `ind_prs22022016_2.pdf` |
| 2020-06-26 | −1 | `ind_prs10062020.pdf` |
| 2023-09-29 | +1 | `ind_prs17082023.pdf` |

The 2023 one is **as printed**: six inclusions against five exclusions, with
`Tata Motors Ltd. DVR / TATAMTRDVR` as the sixth. That is what the PDF says.
Either the index briefly held 101 members, or the DVR share was handled as a
special case alongside the ordinary share. Worth a note in the record rather
than a code change.

The other two want a glance to confirm no row has been miscounted.

---

## Recording answers

Create `data/reference/index_changes_manual.md` (git-ignored) with:

```
| file | effective_from | excluded | included | note |
|---|---|---|---|---|
| ind_prs23082021.pdf | 2021-09-30 | ABC, DEF | GHI, JKL | read by hand |
```

---

## When it is done

```bash
uv run python -m indian_equity_research circulars --parse
```

Two conditions before the reconstruction can be trusted:

1. **Net size change is zero**, or every non-zero entry is explained.
2. **Every year has both reviews.** Only 2021-H2 is outstanding.

Then `reconstruct_membership` walks backwards from today's constituent list. It
refuses to return a membership that is not exactly 100, so any remaining gap
announces itself rather than passing silently.

**If a release genuinely cannot be found or read, record that too.** Under
Amendment A5 clause 4 a documented gap is a finding to report — not a licence to
fall back on the proxy universe.
