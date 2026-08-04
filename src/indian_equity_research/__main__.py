"""Allow the package to be executed with ``python -m indian_equity_research``."""

from __future__ import annotations

import sys

from indian_equity_research.cli import main

if __name__ == "__main__":
    sys.exit(main())
