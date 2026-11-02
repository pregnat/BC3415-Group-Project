import pandas as pd
import numpy as np

def get_account(account_id):

    # Retrieve customer account
    customer = accounts[
        accounts["account_id"] == account_id
    ]

    if customer.empty:
        raise ValueError("Account not found")

    customer = customer.iloc[0]

    # Retrieve customer's stock positions
    customer_positions = positions[
        positions["account_id"] == account_id
    ]

    # Convert stock positions into a list
    position_list = customer_positions[
        ["ticker", "qty", "avg_cost"]
    ].to_dict(orient="records")

    return {
        "account_id": account_id,
        "currency": customer["currency"],
        "cash": float(customer["cash"]),
        "margin_loan": float(customer["margin_loan"]),
        "positions": position_list
    }

def get_prices(tickers, mode="snapshot"):

    if isinstance(tickers, str):
        tickers = [tickers]

    results = {}

    for ticker in tickers:

        price_row = stock_prices[
            stock_prices["ticker"] == ticker
        ]

        if price_row.empty:
            raise ValueError(f"Price not found: {ticker}")

        price_row = price_row.iloc[0]

        results[ticker] = {
            "price": float(price_row["price"]),
            "timestamp": str(price_row["timestamp"]),
            "source": str(price_row["source"])
        }

    return results

def margin_status(account_id, now):

    # 1. Retrieve customer's account data
    customer = account_values[
        account_values["account_id"] == account_id
    ]

    if customer.empty:
        raise ValueError("Account not found")

    customer = customer.iloc[0]

    # 2. Convert evaluation time to datetime
    now = pd.Timestamp(now)

    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    else:
        now = now.tz_convert("UTC")

    # 3. Determine margin status
    if customer["equity"] < customer["se_req"]:
        status = "below_se"

    elif customer["equity"] < customer["mm_req"]:
        status = "below_mm"

    else:
        status = "healthy"

    # 4. Calculate hours below maintenance margin
    if status == "healthy":
        hours_below_mm = 0.0

    elif pd.notna(customer["below_mm_since"]):
        hours_below_mm = max(
            0.0,
            (
                now - customer["below_mm_since"]
            ).total_seconds() / 3600
        )

    else:
        hours_below_mm = None

    # 5. Return results
    return {
        "market_value": float(customer["total_market_value"]),
        "equity": float(customer["equity"]),
        "im_req": float(customer["im_req"]),
        "mm_req": float(customer["mm_req"]),
        "se_req": float(customer["se_req"]),
        "status": status,
        "hours_below_mm": hours_below_mm
    }

def liquidation_distance(account_id, shocks=None):

    # Get customer's stock positions
    customer = portfolio[
        portfolio["account_id"] == account_id
    ].copy()

    if customer.empty:
        raise ValueError("Account not found")

    # Apply simulated stock price changes
    shocks = shocks or {}

    customer["stressed_price"] = customer.apply(
        lambda row: row["price"] *
        (1 + shocks.get(row["ticker"], 0)),
        axis=1
    )

    # Calculate stressed market values
    customer["stressed_value"] = (
        customer["qty"] * customer["stressed_price"]
    )

    # Get the customer's account details
    account = accounts[
        accounts["account_id"] == account_id
    ].iloc[0]

    # Calculate stressed equity
    stressed_value = customer["stressed_value"].sum()

    stressed_equity = (
        stressed_value
        + account["cash"]
        - account["margin_loan"]
    )

    # Recalculate stressed margin requirements
    stressed_mm = (
        customer["stressed_value"] *
        customer["maintenance_ratio"]
    ).sum()

    stressed_se = (
        customer["stressed_value"] *
        customer["soft_edge_ratio"]
    ).sum()

    # Calculate distance to each threshold
    # Assuming all positions decline by the same percentage
    current_value = customer["market_value"].sum()
    current_equity = (
        current_value
        + account["cash"]
        - account["margin_loan"]
    )

    current_mm = customer["mm_req"].sum()
    current_se = customer["se_req"].sum()

    mm_buffer = current_equity - current_mm
    se_buffer = current_equity - current_se

    mm_exposure = current_value - current_mm
    se_exposure = current_value - current_se

    pct_drop_mm = (
        max(0, mm_buffer / mm_exposure)
        if mm_exposure > 0 else None
    )

    pct_drop_se = (
        max(0, se_buffer / se_exposure)
        if se_exposure > 0 else None
    )

    # Identify the largest stressed position
    binding_position = customer.loc[
        customer["stressed_value"].idxmax(),
        "ticker"
    ]

    return {
        "pct_drop_to_mm": pct_drop_mm,
        "pct_drop_to_se": pct_drop_se,
        "stressed_equity": float(stressed_equity),
        "binding_position": binding_position
    }

def weekend_risk_check(account_id, now):

    # Get customer's current margin status
    risk = margin_status(account_id, now)

    # Convert evaluation time
    now = pd.Timestamp(now)

    # Check whether today is Friday
    is_pre_weekend = now.weekday() == 4

    # Current soft-edge requirement
    current_se = risk["se_req"]

    # Hypothetical 25% increase in soft-edge requirement
    raised_se = current_se * 1.25

    # Determine whether account breaches raised requirement
    would_breach = (
        risk["equity"] < raised_se
        if is_pre_weekend
        else False
    )

    return {
        "is_pre_weekend": is_pre_weekend,
        "se_ratio_now": (
            current_se / risk["market_value"]
            if risk["market_value"] > 0 else None
        ),
        "se_ratio_raised": (
            raised_se / risk["market_value"]
            if risk["market_value"] > 0 else None
        ),
        "would_breach": would_breach
    }