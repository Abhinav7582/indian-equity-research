"""Indian Equity Research System.

A point-in-time research platform for Indian equities.

Phase 1 (Research Foundation) contains configuration, logging, database
plumbing and a small CLI. It contains no market-data ingestion, no strategy
logic, no broker integration and no ability to place orders.
"""

from __future__ import annotations

from importlib import metadata

__all__ = ["__version__"]

try:
    __version__: str = metadata.version("indian-equity-research")
except metadata.PackageNotFoundError:  # pragma: no cover - only when not installed
    # The package is being used from a source checkout without installation.
    __version__ = "0.0.0+unknown"
