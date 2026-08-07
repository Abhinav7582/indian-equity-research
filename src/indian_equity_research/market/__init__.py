"""Market reference data: what a trading day is, and what an instrument is.

Two things this package exists to prevent, both of which corrupt results
silently rather than loudly:

* **Confusing a weekday with a trading day.** Republic Day 2024 fell on a
  Friday. A calendar derived from ``weekday() < 5`` counts it as a session and
  every lagged feature slips by one.
* **Joining market data on ticker symbol.** Symbols are reused after
  delisting, change on restructuring, and differ between exchanges. A pipeline
  keyed on symbol will eventually attribute one company's history to another.
"""
