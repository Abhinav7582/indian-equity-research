# Notebooks

Exploration only.

## Rules

1. **Nothing in `src/` may import from here.** Notebooks depend on the
   package; the package never depends on a notebook.
2. **No notebook output is committed.** `.ipynb` files are git-ignored
   precisely because their outputs are large, non-diffable and frequently
   contain data that should not be in version control.
3. **No result from a notebook is evidence.** Notebooks run out of order, hold
   stale state, and make point-in-time violations easy and invisible. Any
   finding worth keeping must be reproduced by the backtester from raw data.
4. **Nothing here writes to `data/raw/`.** The raw layer is append-only and is
   written exclusively by ingestion code.
5. **No credentials.** Load configuration via
   `from indian_equity_research.config import get_settings`.

## Suggested pattern

```python
from indian_equity_research.config import get_settings
from indian_equity_research.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
```

When an exploration turns into something worth keeping, move it into `src/`
with tests, and record the resulting hypothesis in `HYPOTHESES.md`
**before** testing it.
