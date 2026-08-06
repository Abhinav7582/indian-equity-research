# Architecture

**Status: Phase 1 of 10. Almost everything below is unimplemented and is
documented as a target, not as a description of what exists.**

---

## Target data flow

```
        External source                     [ NOT IMPLEMENTED — Phase 2 ]
        NSE / BSE published files, regulator filings, macro releases
                │
                ▼
        Raw immutable storage              [ NOT IMPLEMENTED — Phase 2 ]
        Bytes stored exactly as received. Never edited in place.
        Partitioned by source and date. Append-only.
                │
                ▼
        Validation                          [ NOT IMPLEMENTED — Phase 2 ]
        Schema checks, corporate-action reconciliation,
        index-reconstruction tracking error, anomaly flags
                │
                ▼
        Point-in-time curated database      [ PARTIALLY IMPLEMENTED ]
        PostgreSQL. Connection layer exists; NO TABLES ARE DEFINED.
        Every row carries event_date, published_at and ingested_at.
                │
                ▼
        Feature generation                  [ NOT IMPLEMENTED — Phase 4 ]
        Features may read only rows with published_at <= as_of_date.
                │
                ▼
        Backtesting                         [ NOT IMPLEMENTED — Phase 3 ]
        Event-driven, pessimistic, itemised costs, purged cross-validation
                │
                ▼
        Portfolio construction              [ NOT IMPLEMENTED — Phase 6 ]
        Constraints, position sizing, sector caps, liquidity floors
                │
                ▼
        Shadow portfolio                    [ NOT IMPLEMENTED — Phase 7 ]
        Generates intended positions and reports. Executes nothing.
                │
                ▼
        Manual execution                    [ HUMAN, OUTSIDE THIS SYSTEM ]
        A person reads the report and decides whether to act.
                │
                ▼
        Groww execution                     [ FUTURE, OPTIONAL, NOT PART OF
                                              THE CURRENT SYSTEM ]
        Deliberately not a component of this architecture. It is a possible
        future addition gated on evidence, not a planned milestone.
```

## What exists today

```
                 ┌──────────────────────────────────────┐
                 │  CLI  (version, config-check,        │
                 │        db-health)                    │
                 └───────────────┬──────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐       ┌────────────────┐       ┌────────────────┐
│ config        │       │ logging_config │       │ database       │
│ - YAML layers │       │ - structured   │       │ - Base (no     │
│ - env vars    │       │   format       │       │   tables)      │
│ - validation  │       │ - secret       │       │ - engine       │
│ - secret      │       │   redaction    │       │ - sessions     │
│   masking     │       │                │       │ - health check │
└───────┬───────┘       └────────────────┘       └───────┬────────┘
        │                                                 │
        ▼                                                 ▼
┌───────────────┐                               ┌────────────────┐
│ domain.enums  │                               │  PostgreSQL    │
│ utils.dates   │                               │  (empty)       │
│ exceptions    │                               │                │
│ constants     │                               └────────────────┘
└───────────────┘
```

## Component status

| Component | Status | Phase |
|---|---|---|
| Configuration (`config.py`) | **Implemented** | 1 |
| Structured logging (`logging_config.py`) | **Implemented** | 1 |
| Exception hierarchy (`exceptions.py`) | **Implemented** | 1 |
| Domain enumerations (`domain/enums.py`) | **Implemented** | 1 |
| Date utilities (`utils/dates.py`) | **Implemented** (weekday/timezone only) | 1 |
| Database base, engine, sessions, health | **Implemented** | 1 |
| CLI | **Implemented** (read-only commands) | 1 |
| Causal series statistics (`research/series.py`) | **Implemented** | 1.5 |
| Regime rule (`research/regime.py`) | **Implemented** | 1.5 |
| Performance & drawdown metrics (`research/metrics.py`) | **Implemented** | 1.5 |
| Cost/tax overlay (`research/overlay.py`) | **Implemented** | 1.5 |
| CSV series loader (`data/csv_series.py`) | **Implemented** | 1.5 |
| H4 experiment & scorecard (`research/h4_experiment.py`) | **Implemented** | 1.5 |
| Database schema / ORM models | Not implemented | 2 |
| Market-data collector | Not implemented | 2 |
| Corporate-action processor | Not implemented | 2 |
| Index-membership reconstruction | Not implemented | 2 |
| Surveillance-list archiver | Not implemented | 2 |
| Backtester | Not implemented | 3 |
| Signal engine | Not implemented | 4 |
| Fundamentals collector | Not implemented | 5 |
| News / filing parser | Not implemented | 5 |
| Portfolio constructor | Not implemented | 6 |
| Risk engine | Not implemented | 6 |
| Shadow portfolio & reporting | Not implemented | 7 |
| Reconciliation, OMS, order state machine | Not implemented | Later |
| **Groww connector** | **Not implemented, not scheduled** | Optional future |

## Design constraints

**Small data, deliberately.** A few hundred instruments, twenty years, daily
frequency. Total volume is measured in gigabytes. Distributed compute,
streaming platforms and orchestration clusters would add cost, operational
surface and failure modes while buying nothing. See ADR 0001.

**Fail closed.** When state or data is uncertain, the system stops rather than
guesses. This matters little in Phase 1 and matters enormously later; the
principle is established now so it is not bolted on.

**Deterministic core.** Every decision must be reproducible from the raw data
plus a code version. Non-deterministic components, if ever added, may produce
*features* but may never produce *decisions*.

**Point-in-time or nothing.** See [`data_principles.md`](data_principles.md).

**Phase 1.5 is index-level only.** The modules above consume published index
series read from local CSVs. They contain no stock-level logic, no corporate
actions and no universe reconstruction; those arrive with Phase 2 and are what
H1, H2, H3 and H6 require.

**The benchmark is a product you can buy.** The primary signal is already an
investable ETF at 0.22% a year. Any component built here must justify itself
against that, not against a plain index. See [`benchmarks.md`](benchmarks.md).
