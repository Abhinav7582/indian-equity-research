"""Loading of locally stored reference data.

Phase 1.5 reads CSV files that the user downloaded by hand from the exchange
and index-provider websites. There is deliberately no scraper: NSE's data
policy restricts automated collection, and for a one-off four-file experiment
an automated fetcher would buy nothing while contradicting the principles set
out in ``docs/data_sources.md``.
"""
