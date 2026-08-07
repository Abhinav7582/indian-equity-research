# Operations

## Scheduled archiving

The archiver captures sources that overwrite themselves. **A day not captured
cannot be recovered at any price**, which is why this is scheduled rather than
run by hand.

### macOS (launchd — recommended)

```bash
make archive-install     # installs and loads the job
make archive-status      # confirm it is registered
make archive-logs        # tail recent output
make archive-uninstall   # remove it
```

launchd is preferred over cron on macOS for one specific reason: **if the
machine is asleep at 19:00, launchd runs the job when it next wakes. cron
skips it entirely.** On a laptop, cron would quietly lose days.

### Linux (cron)

Run `crontab -e` and add — as a line *inside the editor*, not at a shell
prompt:

```
0 19 * * 1-5 cd /path/to/project && /usr/local/bin/uv run python -m indian_equity_research archive >> data/raw/archive/cron.log 2>&1
```

## Manual weekly capture

`nse_asm` and `nse_gsm` cannot be automated: their CSVs come from endpoints
requiring a session-cookie handshake, and defeating a bot check would
contradict the licensing position in `docs/data_sources.md`.

Once a week, download from these pages by hand:

| Source | Page | Save as |
|---|---|---|
| ASM | https://www.nseindia.com/reports/asm | `data/raw/archive/nse_asm/nse_asm_YYYY-MM-DD.csv` |
| GSM | https://www.nseindia.com/reports/gsm | `data/raw/archive/nse_gsm/nse_gsm_YYYY-MM-DD.csv` |

Weekly is enough — securities do not enter or leave surveillance daily. These
feed H6, whose evidence base can only ever exist forward from the day capture
begins.

## Checking it is actually working

```bash
ls -lt data/raw/archive/nse_equity_master | head -5
tail -20 data/raw/archive/manifest.jsonl
```

Each capture appends a manifest line with URL, timestamp, byte count and
SHA-256. If the newest file is more than a few days old, the job is not
running.
