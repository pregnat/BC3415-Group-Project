# Assumptions

| # | Assumption | Why | Source |
|---|---|---|---|
| 1 | NVDA, AAPL and MSFT use 40% initial / 30% maintenance / 20% soft edge. TSLA uses 50% / 35% / 25%. See `data/margin_ratios.csv`. | Help-centre figures are worked examples, not real per-stock rates | moomoo SG help centre (link TODO); TSLA is a team assumption |
| 2 | Soft-edge uplift before weekends/holidays = x1.25 | Help centre says it "may be raised" without saying by how much | Team assumption |
| 3 | Equity = market value + cash - margin loan | The plan's formula leaves out cash, but `accounts.csv` has cash balances that a customer could use to cover a shortfall | Team assumption; **differs from the plan, team to confirm** |
| 4 | Below maintenance with a blank `below_mm_since` reports `hours_below_mm` as unknown and liquidation risk as `anytime` | We can't show the 48 hours are still running, so we take the cautious reading | Team assumption |
| 5 | `pct_drop_to_mm` and `pct_drop_to_se` assume every position falls by the same percentage, and are capped at 100% | A cap of 100% means that even losing every position would not reach the threshold | Team assumption |
| 6 | The uplift is only applied in `weekend_risk_check`. `margin_status` always reports against the normal soft edge. | Moomoo doesn't publish when an uplift takes effect | Team assumption |
