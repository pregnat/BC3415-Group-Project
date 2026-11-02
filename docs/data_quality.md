# Data quality notes

## Checks

`test_data_files_are_consistent` in `tests/test_margin.py` runs the notebook's validation on the
CSVs in `data/`: unique IDs, positive quantities and prices, and every position having a price and
a ratio.

## Known issues

- **M-006 and M-010 have no `below_mm_since`.** Both are below maintenance on the snapshot, so
  `hours_below_mm` is unknown for them. M-010 is below soft edge, so its risk is unaffected. M-006
  reports `anytime` (see `docs/assumptions.md`, #4).
- **`below_mm_since` doesn't follow prices.** It is a fixed value in `accounts.csv`, so refreshing
  `stock_prices.csv` can change an account's status without changing its clock.
- **Snapshot timestamps are dates only**, because moomoo's `data_date` has no time of day.
- **`stock_prices_backup.csv` isn't read by any code.** It holds moomoo prices from later on 2 Nov
  and is kept for reference.

TODO(A): stale, missing and split-adjusted price checks, and the OpenAPI vs yfinance cross-check.
