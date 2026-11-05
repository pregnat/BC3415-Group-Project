# Data quality notes

## Checks

`test_data_files_are_consistent` in `tests/test_margin.py` runs the notebook's validation on the
CSVs in `data/`: unique IDs, positive quantities and prices, and every position having a price and
a ratio.

## Known issues

- **M-006 and M-010 had no `below_mm_since`** even though both are below maintenance on the
  snapshot. We added synthetic values: M-006 is 24 hours in at the demo time, so one account shows
  a running 48-hour clock. The notebook's saved outputs still show them blank.
- **`below_mm_since` doesn't follow prices.** It is a fixed value in `accounts.csv`, so refreshing
  `stock_prices.csv` can change an account's status without changing its clock.
- **Snapshot timestamps are dates only**, because moomoo's `data_date` has no time of day.
- **`stock_prices_backup.csv` isn't read by any code.** It holds moomoo prices stamped 16:51 UTC on
  2 Nov and is kept for reference.

## Price checks

`python -m engine.price_checks` checks `data/stock_prices.csv` for missing prices (a held ticker with
no price), invalid prices (zero, negative or NaN), stale prices (more than one completed US trading
session old at the demo clock), suspected splits (a price near 1:2, 1:3, 1:4, 1:5, 1:10 or 1:20 of
the cost basis or of a second source) and source mismatches (more than 2% apart). By default the
second source is `data/stock_prices_backup.csv`; `--live` compares against yfinance instead. Tests
are in `tests/test_price_checks.py`.

Result on the frozen snapshot at the demo clock (Fri 6 Nov 2026):

| Check | Result |
|---|---|
| Missing | None: every held ticker has a price |
| Invalid | None |
| Stale | **All 4 tickers.** Prices are from 2 Nov, 3 trading sessions before the demo clock. This is deliberate, because the demo runs on a frozen snapshot, but the agent should say prices are as of 2 Nov. |
| Split-adjusted | None suspected against cost basis or the backup |
| Source mismatch | None: the snapshot and the backup (both moomoo, 2 Nov) are within 0.4% |

The yfinance cross-check (`--live`) hasn't been run for this write-up. Run it before the demo and
add the result here.
