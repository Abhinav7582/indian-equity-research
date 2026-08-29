# Nifty 200 — the thirteen changes to adjudicate by hand

**Route 3 of Amendment A11.** This reads no returns and is not a trial. It is a
data-quality repair, and it is the same method that recovered the September 2021
Nifty 100 reconstitution now sitting in `data/reference/index_changes_manual.md`.

If this closes the reconstruction, Route 1's sensitivity band becomes
unnecessary and the Nifty 200 study runs with no caveat at all.

---

## The one rule that matters

**An entry may record only what a document says.**

"This name must have left around here, because otherwise the count is wrong" is
an inference from the reconstruction failing. Writing that down would make the
reconstruction close *by construction* — fitting the data to the method, which
is the exact failure this whole register exists to prevent.

If you cannot find a document, **leave it**. An unresolved change is not a
defeat; it feeds Route 1's excluded list, which is already designed for it.

---

## How to read the two failure types

The reconstruction rolls today's roster **backwards**. Undoing a change means:
remove whatever the release *included*, add back whatever it *excluded*.

| Report | What it means | What to look for |
|---|---|---|
| **included but absent** | The release says X joined on this date, so X should still be in a later roster. It is not. | The event that **removed** X afterwards |
| **excluded but present** | The release says Y left on this date, so Y should not be in a later roster. It is. | The event that **re-admitted** Y afterwards |

In both cases the missing document is *later* than the date shown.

---

## The thirteen

Ordered oldest first. Dates are **effective** dates, not announcement dates —
NSE announces roughly five weeks ahead, and the filename carries the
announcement date.

| # | Effective | Release | Look for the event that… |
|---|---|---|---|
| 1 | 2014-09-19 | `ind_prs20082014.pdf` | **removed** WABAG; **re-admitted** BAJAJFINSV, CRISIL, TRENT, VAKRANGEE |
| 2 | 2015-03-27 | `ind_prs20022015.pdf` | **re-admitted** NIITTECH |
| 3 | 2016-09-30 | `ind_prs12082016.pdf` | **re-admitted** HINDCOPPER |
| 4 | 2017-09-29 | `ind_prs29082017.pdf` | **removed** MFSL; **re-admitted** RELCAPITAL |
| 5 | 2018-02-05 | `ind_prs08012018.pdf` | **removed** VGUARD |
| 6 | 2018-04-02 | `ind_prs21022018.pdf` | **removed** GODREJAGRO |
| 7 | 2018-06-29 | `ind_prs24052018.pdf` | **re-admitted** TATACOMM |
| 8 | 2018-12-28 | `ind_prs14122018.pdf` | **removed** BBTC |
| 9 | 2019-09-27 | `ind_prs28082019.pdf` | **removed** CESC |
| 10 | 2020-06-26 | `ind_prs10062020.pdf` | **removed** ABBOTINDIA; **re-admitted** INDIANB |
| 11 | 2021-03-31 | `ind_prs23022021.pdf` | **re-admitted** NATIONALUM |
| 12 | 2024-03-28 | `ind_prs28022024.pdf` | **removed** IREDA |
| 13 | 2024-09-30 | `ind_prs23082024.pdf` | **removed** CENTRALBK; **re-admitted** IDEA |

**Twenty securities, 5.3% of the 380 that were ever members.**

### The four that are almost certainly quickest

Rows 1 and 13 involve names whose stories are already known elsewhere in this
project, and rows 12 and 9 are recent enough that NSE's site still lists the
release prominently.

Start there. If the method works on four, it will work on thirteen; if it
doesn't, stop and fall back to Route 1 rather than grinding through the rest.

---

## Where to look

1. **NSE press releases** — https://www.niftyindices.com/media
   Pattern: `https://www.niftyindices.com/Press_Release/ind_prsDDMMYYYY.pdf`
   Reconstitutions are announced in late **February** and late **August**,
   effective **31 March** and **30 September**. Off-cycle changes appear
   whenever a constituent merges, delists or is suspended.

2. **The company itself.** A name that vanishes from an index between reviews
   usually merged, delisted, or was moved to surveillance. NIITTECH became
   Coforge; that kind of event is often a **rename**, in which case the index
   never lost it and the entry should say so.

3. **Do not** use a screener or a third-party constituent history as evidence.
   They are reconstructions too, with unknown methods, and citing one would make
   this register a copy of somebody else's guess.

---

## The format to write it in

Append to `data/reference/index_changes_manual.md`, matching the rows already
there:

```
| source | index | effective_from | excluded | included | evidence |
|---|---|---|---|---|---|
| ind_prsDDMMYYYY.pdf | Nifty 200 | 2019-11-15 | CESC |  | p3, section "N) NIFTY 200"; read visually |
```

* **source** — the release the change comes from, or a short description if it
  is not a press release
* **effective_from** — as printed in the release, never the filename date
* **excluded** / **included** — comma-separated symbols, blank if none
* **evidence** — enough that someone else can find the same page

That file is git-ignored: NSE prohibits redistributing its data, so the method
is committed and the transcription stays local.

---

## When you are done

```bash
uv run python scripts/build_membership.py --index "Nifty 200"
```

**0 unapplied and every snapshot at 200** means the repair worked and the study
runs clean. Anything less is fine too — whatever remains is what Route 1's band
is for, and the excluded list in Amendment A11 shrinks to match.
