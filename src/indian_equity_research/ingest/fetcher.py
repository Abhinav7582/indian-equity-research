"""Fetching, behind a protocol so the archiver can be tested offline.

The real implementation uses the standard library. No HTTP dependency is
added: one polite GET per file per day does not justify one.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

from indian_equity_research.exceptions import IndianEquityResearchError
from indian_equity_research.logging_config import get_logger

__all__ = [
    "FakeFetcher",
    "FetchError",
    "FetchResult",
    "Fetcher",
    "UrlFetcher",
]

logger = get_logger(__name__)

#: Identifies this project honestly rather than impersonating a browser.
DEFAULT_USER_AGENT = (
    "indian-equity-research/0.1 (personal research archiver; one request per file per day)"
)


class FetchError(IndianEquityResearchError):
    """A source could not be retrieved."""


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Bytes retrieved from a source.

    Attributes:
        url: The URL requested.
        content: Raw response body, stored verbatim.
        content_type: Reported content type, when the server supplied one.
        status: HTTP status code.
    """

    url: str
    content: bytes
    content_type: str = ""
    status: int = 200

    def looks_like_html(self) -> bool:
        """Whether the body appears to be an HTML page rather than data.

        A CSV endpoint that has moved often returns a friendly HTML error page
        with status 200. Saving that as ``asm_list.csv`` would poison the
        archive silently, so the archiver checks before writing.
        """
        head = self.content[:512].lstrip().lower()
        return head.startswith((b"<!doctype html", b"<html")) or b"text/html" in (
            self.content_type.lower().encode()
        )


class Fetcher(Protocol):
    """Anything that can retrieve bytes for a URL."""

    def fetch(self, url: str) -> FetchResult:
        """Retrieve the resource at ``url``.

        Args:
            url: Absolute URL to retrieve.

        Returns:
            The response body and metadata.

        Raises:
            FetchError: If the resource could not be retrieved.
        """
        ...


@dataclass
class UrlFetcher:
    """Polite standard-library fetcher.

    Attributes:
        user_agent: Sent on every request.
        timeout_seconds: Per-request timeout.
        delay_seconds: Minimum pause between consecutive requests. Deliberately
            generous; this archiver is never in a hurry.
    """

    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = 30.0
    delay_seconds: float = 3.0
    _last_request_at: float = field(default=0.0, init=False, repr=False)

    def fetch(self, url: str) -> FetchResult:
        """Retrieve ``url``, pausing first if the last request was recent.

        Args:
            url: Absolute URL to retrieve.

        Returns:
            The response body and metadata.

        Raises:
            FetchError: On any network or protocol failure. The message names
                the URL and the cause without exposing anything else.
        """
        elapsed = time.monotonic() - self._last_request_at
        if self._last_request_at and elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/csv,application/json,application/octet-stream,*/*",
                "Accept-Language": "en-IN,en;q=0.9",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
                return FetchResult(
                    url=url,
                    content=body,
                    content_type=response.headers.get("Content-Type", ""),
                    status=int(response.status),
                )
        except urllib.error.HTTPError as exc:
            message = f"{url} returned HTTP {exc.code}."
            raise FetchError(message) from exc
        except urllib.error.URLError as exc:
            message = f"{url} could not be reached: {exc.reason}."
            raise FetchError(message) from exc
        except TimeoutError as exc:
            message = f"{url} timed out after {self.timeout_seconds:.0f}s."
            raise FetchError(message) from exc
        finally:
            self._last_request_at = time.monotonic()


@dataclass
class FakeFetcher:
    """In-memory fetcher for tests. Records every URL it was asked for.

    Attributes:
        responses: Mapping of URL to the bytes to return.
        failures: URLs that should raise :class:`FetchError`.
        content_types: Optional per-URL content type.
        requested: URLs requested, in order.
    """

    responses: dict[str, bytes] = field(default_factory=dict)
    failures: set[str] = field(default_factory=set)
    content_types: dict[str, str] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)

    def fetch(self, url: str) -> FetchResult:
        """Return the configured response for ``url``.

        Args:
            url: URL to look up.

        Returns:
            The configured response.

        Raises:
            FetchError: If ``url`` is configured to fail or is unknown.
        """
        self.requested.append(url)
        if url in self.failures:
            message = f"{url} could not be reached: configured failure."
            raise FetchError(message)
        if url not in self.responses:
            message = f"{url} returned HTTP 404."
            raise FetchError(message)
        return FetchResult(
            url=url,
            content=self.responses[url],
            content_type=self.content_types.get(url, "text/csv"),
        )
