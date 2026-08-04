"""Project-wide constants and filesystem anchors.

Nothing here is market-specific. Trading-calendar constants (exchange
holidays, session timings) belong to a later phase and are deliberately
absent.
"""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

__all__ = [
    "CONFIG_DIR",
    "DEFAULT_CONFIG_FILENAME",
    "INDIA_TZ",
    "PACKAGE_DIR",
    "PACKAGE_NAME",
    "PROJECT_ROOT",
    "find_project_root",
]

PACKAGE_NAME = "indian_equity_research"

#: Indian Standard Time. Every exchange timestamp is IST; storing or comparing
#: naive datetimes is a defect, so this is required from the very first phase.
INDIA_TZ = ZoneInfo("Asia/Kolkata")

PACKAGE_DIR: Path = Path(__file__).resolve().parent

DEFAULT_CONFIG_FILENAME = "base.yaml"


def find_project_root(start: Path | None = None) -> Path:
    """Return the nearest ancestor directory containing ``pyproject.toml``.

    Walking up for a marker file keeps the project root correct for source
    checkouts, editable installs and test runs alike, without depending on the
    current working directory.

    Args:
        start: Directory to begin searching from. Defaults to the package
            directory.

    Returns:
        The project root, or the current working directory if no marker is
        found (which happens only for a non-editable install).
    """
    origin = (start or PACKAGE_DIR).resolve()
    for candidate in (origin, *origin.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path.cwd()


PROJECT_ROOT: Path = find_project_root()
CONFIG_DIR: Path = PROJECT_ROOT / "configs"
