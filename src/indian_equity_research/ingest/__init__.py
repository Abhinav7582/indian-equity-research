"""Data acquisition.

Phase 2a covers **prospective archiving** only: capturing sources that
overwrite themselves, before the history is lost. Nothing here parses market
data or builds a research dataset; that arrives with the bhavcopy ingest.

Two constraints shape every module in this package:

1. **Licensing.** Exchange data usage policies restrict systematic collection
   and prohibit redistribution. The archiver fetches each published file at
   most once per day, honours a configurable delay, never re-fetches what it
   already holds, and writes only into the git-ignored data directory. See
   ``docs/data_sources.md``. This is not legal advice.
2. **Testability.** Network access is behind a protocol, so the archiver is
   exercised offline against a fake, exactly as the broker layer would be.
"""
