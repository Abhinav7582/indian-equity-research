# Indian Equity Research System

A point-in-time research platform for Indian cash equities.

> ### ⚠️ Research only — this software cannot trade
>
> This project has **no broker integration, no market-data connectivity and no
> ability to place, modify or cancel an order**. It does not connect to the
> Groww Trading API, to NSE, to BSE or to any external service. It produces
> **no investment recommendations**.
>
> Nothing in this repository is investment advice. Any strategy developed here
> is a research artefact until it has been validated out of sample and
> reviewed by a human.

---

## Purpose

To find out — honestly, and with the evidence bar set before the experiment —
whether a disciplined, cost-aware, systematic process can beat a Nifty 100
index fund **after every cost and every tax**.

The likeliest outcome is that it cannot. Establishing that with evidence is a
successful result and is the reason the project is structured as research
rather than as a trading system.

## Current phase

**Phase 3 — complete.** The full pipeline runs end to end: bhavcopy → universe →
engine → metrics → statistical gates. See [`ROADMAP.md`](ROADMAP.md) for what
comes next and what is blocking it.

**One hypothesis tested and rejected.** H4's regime overlay increased drawdown
rather than reducing it and lost to a static 75:25 blend
([`HYPOTHESES.md`](HYPOTHESES.md), trial #1). Cost: no capital at risk.

### What exists

**Foundation** — layered validated configuration, structured logging with
credential redaction, SQLAlchemy 2.x base with Alembic-ready naming, local
PostgreSQL via Docker Compose.

**Data layer** — daily archiver with a hash-chained manifest, trading calendar
from observed sessions, instrument master with explicit resolution basis,
bhavcopy ingest across both the legacy and UDiFF formats, corporate-action
validator, delisting register with three-way classification, back-adjustment
engine with provenance.

**Backtest layer** — a date-versioned Indian cost model accurate to the paisa,
an event-driven engine that makes look-ahead structurally impossible, the A5
proxy universe, and Deflated Sharpe Ratio / Probability of Backtest Overfitting
gates.

**Discipline** — six pre-registered hypotheses, six dated amendments, a trial
register, and a self-deception suite that is itself mutation-tested: twelve
deliberate bugs injected, twelve caught.

CLI: `version`, `config-check`, `db-health`, `h4-regime`, `archive`,
`reference`, `bhavcopy`.

### What still does not exist

| Not implemented | Belongs to |
|---|---|
| Purged / embargoed walk-forward cross-validation | Phase 3g |
| Momentum, quality or any other signal | Phase 4 |
| Allocation and rebalancing system | Phase 5 |
| Research into instruments beyond cash equity | Phase 6 |
| Shadow portfolio, paper trading | Phase 7 |
| **Groww API authentication, market data or orders** | **Only if Amendment A6 is passed** |
| Live order placement | **Not in scope for this project** |
| Machine learning, news processing, LLM features | Only if a baseline works first |

**No database tables are defined yet.** Modelling instruments, prices and
corporate actions is deferred until the point-in-time requirements are fixed,
because retrofitting point-in-time correctness into an existing schema is far
more expensive than designing for it. The research path currently runs on files,
not on the database.

### Blocked on one remaining download

Nothing in Phase 4 can produce a trustworthy result until these land. Steps are
in [`ROADMAP.md`](ROADMAP.md).

1. **NSE index-change press releases** — the real index membership. Under
   Amendment A5 no hypothesis can be tested on the proxy universe. The parser
   is built and tested; only the PDFs are missing. See
   [`docs/universe_reconstruction.md`](docs/universe_reconstruction.md).

**Done:** bhavcopy 2015-01-01 to 2026-08-05 (2,861 sessions, 5.33M rows, no
gaps) and NIFTY 100 TRI 2015–2026 (12 files).

## Technology stack

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Layout | `src/` |
| Packaging / environments | `uv` |
| Configuration | `pydantic-settings` (env vars) + YAML (non-secrets) |
| Database | PostgreSQL 16 via SQLAlchemy 2.x, Alembic-ready |
| Driver | `psycopg` 3 |
| Local services | Docker Compose |
| Tests | `pytest` |
| Lint / format | `ruff` |
| Types | `mypy` (strict) |
| Logging | Standard library, structured format, secret redaction |

Rationale in [`docs/adr/0001-initial-technology-stack.md`](docs/adr/0001-initial-technology-stack.md).

## Local setup

Prerequisites: [`uv`](https://docs.astral.sh/uv/), `git`, and optionally
Docker (needed only for the integration tests).

```bash
# 0. Check prerequisites. Changes nothing.
python3 scripts/bootstrap.py

# 1. Create the virtual environment and install everything.
#    uv provisions Python 3.12 itself; no system Python 3.12 required.
uv sync --extra dev

# 2. Local configuration. .env is git-ignored.
cp .env.example .env

# 3. Optional: start PostgreSQL.
make db-up

# 4. Verify the environment end to end.
uv run python scripts/verify_environment.py
```

## CLI

```bash
uv run python -m indian_equity_research version        # prints the version
uv run python -m indian_equity_research config-check   # validates config, masks secrets
uv run python -m indian_equity_research db-health      # exits non-zero if unreachable
uv run python -m indian_equity_research h4-regime      # score H4 against Amendment A2
```

`h4-regime` reads index CSVs from `data/raw/indices/` (git-ignored, downloaded
by hand — see [`docs/data_sources.md`](docs/data_sources.md) for why there is
no scraper) and prints a scorecard against criteria fixed before the data
existed. It opens no socket and places no order.

Exit codes: `0` success, `1` check failed, `2` usage error.

## Tests

```bash
make test-unit          # no database required
make db-up
make test-integration   # requires PostgreSQL
make test               # everything; integration tests skip if PostgreSQL is absent
make check              # format-check + lint + typecheck + unit tests (what CI runs)
```

Tests never access the network and never read a developer's `.env`.

## Developer commands

`make help` lists everything. The most used:

| Command | Purpose |
|---|---|
| `make install` | Create the venv and install dependencies |
| `make format` | Format and auto-fix with ruff |
| `make lint` | Lint with ruff |
| `make typecheck` | Strict type check with mypy |
| `make test` / `test-unit` / `test-integration` | Test suites |
| `make db-up` / `db-down` / `db-logs` | Local PostgreSQL |
| `make config-check` / `db-health` / `version` | CLI shortcuts |
| `make verify` | Full environment verification |
| `make clean` | Remove caches (never touches `data/` or `.env`) |

## Repository layout

```
configs/     Non-sensitive YAML configuration, layered by environment
data/        Local data lake (git-ignored except .gitkeep). Empty by design.
docs/        Architecture, data principles, architecture decision records
migrations/  Reserved for Alembic. No migrations yet; no tables exist.
notebooks/   Exploration only. Never imported by src/.
scripts/     Bootstrap and environment verification (no side effects)
src/         The package
tests/       Unit and integration suites
```

## Documentation

- [`HYPOTHESES.md`](HYPOTHESES.md) — pre-registered hypotheses H1–H6 and
  Amendments A1–A6, including the universe rule (A5) and the capital cap,
  abandonment test and derivatives gate (A6). **Read this before writing any
  research code.**
- [`ROADMAP.md`](ROADMAP.md) — the single forward plan: what is done, what is
  blocked, the three outstanding downloads, and Phases 4–7. Supersedes any
  older plan elsewhere in the repository.
- [`docs/benchmarks.md`](docs/benchmarks.md) — **the real bar.** The primary
  signal is already sold as an ETF at 0.22%; this computes what the system
  must beat and why.
- [`docs/architecture.md`](docs/architecture.md) — target architecture, with
  every future component marked unimplemented
- [`docs/data_principles.md`](docs/data_principles.md) — the non-negotiable
  data rules
- [`docs/factor_evidence.md`](docs/factor_evidence.md) — what the evidence
  supports for Indian equities, and which sources to distrust
- [`docs/data_sources.md`](docs/data_sources.md) — Phase 2 data acquisition:
  sources, costs, the 2024 bhavcopy format change, licensing boundaries
- [`docs/portfolio_template.md`](docs/portfolio_template.md) — template for a
  personal holdings snapshot. Fill into `data/reference/portfolio.md`
  (git-ignored). **Never read by the backtester** — see the boundary note in
  the template.
- [`docs/universe_reconstruction.md`](docs/universe_reconstruction.md) — how to
  obtain and parse NSE index-change press releases, and how to walk membership
  backwards from today's constituent list
- [`docs/verification.md`](docs/verification.md) — **reproduce every claim in
  this repo from a clean clone**, with the expected output at each step
- [`docs/adr/`](docs/adr/) — architecture decision records

## Security

- Secrets live only in `.env` (git-ignored) and process environment variables.
- YAML configuration files must never contain a credential.
- Logs pass through a redaction filter; database URLs are rendered with the
  password masked.
- No broker, exchange or market-data credentials exist in this project, and
  none are required.

## Safety statement

This software performs **no trading of any kind**. It cannot place, modify or
cancel an order. It has no connection to any broker. It generates no buy or
sell recommendations.

Investing in equities carries the risk of permanent capital loss. Past
performance of any index, factor or strategy is not indicative of future
results. Nothing produced by this project is investment, legal or tax advice.
