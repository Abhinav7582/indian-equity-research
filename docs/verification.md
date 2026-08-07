# Verifying This Project From Scratch

**Purpose:** reproduce every claim this repository makes, from a clean clone,
without trusting anything already on your machine.

Do this whenever you have been away from the project, before acting on any
result, and after any large change. It takes about fifteen minutes.

---

## Why bother

Two failure modes this catches, both of which are common and neither of which
announces itself:

1. **The repo is not actually self-contained.** Something works only because
   of a file, environment variable or installed package that exists on your
   machine and is not in git. You discover this on a new laptop, usually at
   the worst time.
2. **You are trusting numbers you have not reproduced.** The whole discipline
   of this project — pre-registration, purged validation, honest cost models —
   is worthless if the person running it cannot rebuild the result themselves.

---

## Step 0 — Clone somewhere else

Do **not** verify in your working copy. Use a throwaway directory, so anything
that only works because of local state fails loudly.

```bash
cd /tmp
rm -rf verify-ier
git clone https://github.com/<you>/indian-equity-research.git verify-ier
cd verify-ier
```

**Expect:** a clone with **78 tracked files** and no `data/`, `.venv/` or
`.env`.

```bash
git ls-files | wc -l          # 78
ls data/raw                   # only .gitkeep
```

> **This is the point, not a problem.** No market data is in git. Exchange
> data must never be redistributed, so the repo carries code and decisions,
> never the data itself.

## Step 1 — Prerequisites

```bash
python3 scripts/bootstrap.py
```

**Expect:** `OK` for uv and git; `WARN` for docker if it is not running and
for the absent `.env`. Exit code 0 if the required tools are present. This
script changes nothing.

## Step 2 — Environment

```bash
uv sync --extra dev
cp .env.example .env
```

**Expect:** uv downloads CPython 3.12 if needed, creates `.venv`, and writes
`uv.lock` — which should already match the committed one. If `uv.lock`
changes, the lockfile was stale in git and should be committed.

## Step 3 — The full check

```bash
make check
```

**Expect exactly:**

| Stage | Expected output |
|---|---|
| `ruff format --check` | `46 files already formatted` |
| `ruff check` | `All checks passed!` |
| `mypy` | `Success: no issues found in 46 source files` |
| `pytest -m "not integration"` | `276 passed` |

Any deviation is a real finding. Investigate before continuing.

## Step 4 — The database path

```bash
make db-up && make db-wait
make test-integration
make db-down
```

**Expect:** `8 passed`. If Docker is not running you will get an actionable
message rather than a cryptic flag error — that message is itself a feature
worth confirming.

Without Docker these tests **skip**, and `make test` still succeeds. CI runs
them against a real PostgreSQL service container and **fails if they skip**,
so the database path is verified on every push regardless.

## Step 5 — The CLI

```bash
uv run python -m indian_equity_research version        # 0.1.0
uv run python -m indian_equity_research config-check   # exit 0
uv run python -m indian_equity_research db-health      # exit 1 with no database
```

**Expect:**

- `config-check` prints 16 settings with `database_password` shown as
  `<set>` or `<not set>` — **never the value** — and a URL with the password
  masked.
- `db-health` exits **non-zero** when no database is reachable. That is the
  specification, not a failure.

Confirm the secret handling yourself rather than taking it on trust:

```bash
DATABASE_PASSWORD=hunter2xyz uv run python -m indian_equity_research config-check | grep -c hunter2xyz
# expect: 0
```

## Step 6 — The archiver

```bash
uv run python -m indian_equity_research archive --check
```

**Expect:** `OK` for `nse_equity_master` (~169 KB) and
`nse_nifty100_constituents` (~7 KB); `MANUAL` for `nse_asm` and `nse_gsm`,
which cannot be automated (see `docs/data_sources.md`).

```bash
uv run python -m indian_equity_research archive --dry-run
```

**Expect:** `2 secured, 0 disabled, 2 manual, 0 problem(s)` — and nothing
written.

## Step 7 — The H4 experiment

```bash
uv run python -m indian_equity_research h4-regime
```

**Expect it to FAIL**, with a message naming the files it wants:

```
Could not load input data: ... no files matching 'nifty200_momentum30_tri*.csv'
```

> **This is correct behaviour.** The index CSVs are git-ignored. A fresh clone
> has code and criteria but no data, and the command refuses rather than
> inventing a result.

To reproduce trial #1, copy `data/raw/indices/` from your working copy (94
CSVs) and run again. **Expect the same verdict: H4 REJECTED, 3 of 5 criteria
failed, in both windows.** If you get a different answer from the same data
and the same commit, something is wrong and it matters.

---

## What each step actually proves

| Step | Proves |
|---|---|
| 0 | The repo is self-contained and carries no market data |
| 1 | Prerequisites are declared, not assumed |
| 2 | The environment is reproducible from a lockfile |
| 3 | Formatting, typing and logic are all verified, not asserted |
| 4 | The database layer works against a real server |
| 5 | Exit codes are specified, and secrets do not leak |
| 6 | The archiver fails closed and is honest about what it cannot do |
| 7 | Results are reproducible, and absent data produces an error rather than a number |

## Clean up

```bash
cd /tmp
rm -rf verify-ier
docker volume ls | grep postgres    # remove any strays from the verification
```

## Findings this walkthrough has already caught

| Date | Finding | Fix |
|---|---|---|
| 2026-08-07 | The Compose volume had a fixed `name:`, so a clean clone mounted the working copy's database instead of its own. Tests still passed, but the isolation the walkthrough assumes was not real. | Removed the explicit name; Compose now namespaces the volume per project. |

Record anything else here. A verification that never finds anything is usually
a verification that is not looking.

---

## If something fails

Write down what you expected, what you got, and the commit hash — **before**
changing anything. A failure you fix without recording is a failure you will
have again and will not recognise.
