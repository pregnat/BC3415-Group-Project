# Assumptions

| # | Assumption | Why | Source |
|---|---|---|---|
| 1 | NVDA, AAPL and MSFT use 40% initial / 30% maintenance / 20% soft edge. TSLA uses 50% / 35% / 25%. See `data/margin_ratios.csv`. | Help-centre figures are worked examples, not real per-stock rates | moomoo SG help centre (link TODO); TSLA is a team assumption |
| 2 | Soft-edge uplift before weekends/holidays = x1.5, for every stock | The help centre's Friday example raises the soft edge from 20% to 30%. It is one example, not a published rule, and we apply the same multiplier to every stock (so TSLA goes from 25% to 37.5%). | [moomoo SG help centre, topic5_493](https://www.moomoo.com/sg/support/topic5_493) |
| 3 | Equity = market value + cash - margin loan | The plan's formula leaves out cash, but `accounts.csv` has cash balances that a customer could use to cover a shortfall. The help centre's examples show market value minus loan, but none of them hold cash, so they don't contradict this. | Team assumption |
| 4 | Below maintenance with a blank `below_mm_since` (no account has one today) reports `hours_below_mm` as unknown and liquidation risk as `anytime` | We can't show the 48 hours are still running, so we take the cautious reading | Team assumption |
| 5 | `pct_drop_to_mm` and `pct_drop_to_se` assume every position falls by the same percentage, and are capped at 100% | A cap of 100% means that even losing every position would not reach the threshold | Team assumption |
| 6 | The uplift is only applied in `weekend_risk_check`. `margin_status` always reports against the normal soft edge. | Moomoo doesn't publish when an uplift takes effect | Team assumption |
