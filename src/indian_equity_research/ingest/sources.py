"""Registry of sources that overwrite themselves and must be archived daily.

Why this is config-driven
-------------------------
Exchange URLs change without notice, and a stale URL hard-coded in Python is a
silent failure. The registry lives in ``configs/archive_sources.yaml`` so a
broken endpoint is a one-line edit, not a code change and a release.

Every source ships **disabled** until it has been verified reachable with
``archive --check``. That is deliberate: an archiver that appears to work while
saving HTML error pages is worse than one that refuses to start.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from indian_equity_research.exceptions import ConfigurationError

__all__ = ["ArchiveSource", "load_sources"]


@dataclass(frozen=True, slots=True)
class ArchiveSource:
    """One thing to snapshot each day.

    Attributes:
        name: Short identifier, used as the archive subdirectory.
        url: Absolute URL of the published file.
        description: What it is and why it must be captured prospectively.
        extension: File extension to save under, e.g. ``csv`` or ``json``.
        enabled: Whether the archiver will fetch it. Sources start disabled
            until verified with ``archive --check``.
        expect_html: ``True`` only for sources that legitimately return HTML.
            Everything else is rejected if it looks like a web page.
        manual: ``True`` when the data exists only behind a JavaScript page or
            an endpoint requiring a session handshake. Such sources are
            reported so they are not forgotten, but never fetched: defeating a
            bot check would contradict the licensing position in
            ``docs/data_sources.md``. Capture them by hand instead.
        manual_url: Page a human should visit for a ``manual`` source.
    """

    name: str
    url: str
    description: str
    extension: str = "csv"
    enabled: bool = False
    expect_html: bool = False
    manual: bool = False
    manual_url: str = ""

    def filename_for(self, when: date) -> str:
        """Return the archive filename for a given capture date.

        Args:
            when: Capture date.

        Returns:
            A dated filename, e.g. ``asm_list_2026-08-06.csv``.
        """
        return f"{self.name}_{when.isoformat()}.{self.extension}"


def load_sources(path: Path) -> list[ArchiveSource]:
    """Load the source registry from YAML.

    Args:
        path: Path to ``archive_sources.yaml``.

    Returns:
        Every declared source, enabled or not, in file order.

    Raises:
        ConfigurationError: If the file is missing or malformed, a source is
            missing a required field, names are duplicated, or a source does
            not point somewhere over HTTPS.
    """
    if not path.is_file():
        message = f"Archive source registry not found: {path}"
        raise ConfigurationError(message)
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        message = f"{path.name} is not valid YAML: {exc}"
        raise ConfigurationError(message) from exc

    if not isinstance(raw, dict) or "sources" not in raw:
        message = f"{path.name} must contain a top-level 'sources' list."
        raise ConfigurationError(message)
    entries = raw["sources"]
    if not isinstance(entries, list):
        message = f"{path.name}: 'sources' must be a list."
        raise ConfigurationError(message)

    sources: list[ArchiveSource] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            message = f"{path.name}: source #{index} must be a mapping."
            raise ConfigurationError(message)
        missing = {"name", "url", "description"} - entry.keys()
        if missing:
            message = f"{path.name}: source #{index} is missing {sorted(missing)}."
            raise ConfigurationError(message)
        name = str(entry["name"])
        if name in seen:
            message = f"{path.name}: duplicate source name {name!r}."
            raise ConfigurationError(message)
        seen.add(name)

        # Every source must point somewhere over HTTPS: an automated source
        # needs a fetchable `url`, a manual one needs a `manual_url` for the
        # human. Validating here means a malformed registry fails at startup
        # with a readable message rather than surfacing as a 404 at 18:30.
        is_manual = bool(entry.get("manual", False))
        target_field = "manual_url" if is_manual else "url"
        target = str(entry.get(target_field, ""))
        if not target.startswith("https://"):
            how = "downloaded by hand" if is_manual else "fetched automatically"
            message = (
                f"{path.name}: source {name!r} is {how}, so it needs a https "
                f"{target_field!r}, got {target!r}."
            )
            raise ConfigurationError(message)
        sources.append(
            ArchiveSource(
                name=name,
                url=str(entry["url"]),
                description=str(entry["description"]),
                extension=str(entry.get("extension", "csv")),
                enabled=bool(entry.get("enabled", False)),
                expect_html=bool(entry.get("expect_html", False)),
                manual=bool(entry.get("manual", False)),
                manual_url=str(entry.get("manual_url", "")),
            )
        )
    return sources
