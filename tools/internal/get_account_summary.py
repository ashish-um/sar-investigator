"""
Tool: get_account_summary

Retrieves all accounts held by a customer with dormancy and reactivation flags.
"""

import json
from datetime import date, datetime
from langchain_core.tools import tool
from tools.db import get_connection


@tool
def get_account_summary(customer_id: str, observation_window_end: str = None) -> str:
    """Retrieve all accounts held by a customer including type, status, average
    balance, and last activity date. Call this after get_customer_profile to get
    the list of account IDs before fetching transactions. Automatically identifies
    dormant account reactivation. 
    Make sure to pass the observation_window_end from the alert payload so dormancy 
    is calculated relative to the alert window, not today's date."""

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM accounts WHERE customer_id = ?", (customer_id,)
        )
        rows = cursor.fetchall()

    if not rows:
        return json.dumps({"error": f"No accounts found for customer {customer_id}"})

    if observation_window_end:
        try:
            reference_date = datetime.strptime(observation_window_end, "%Y-%m-%d").date()
        except ValueError:
            reference_date = date.today()
    else:
        reference_date = date.today()
    accounts = []

    for row in rows:
        account = dict(row)

        # Round monetary values
        if account.get("average_monthly_balance_gbp") is not None:
            account["average_monthly_balance_gbp"] = round(
                account["average_monthly_balance_gbp"], 2
            )

        # Per-account computed flags
        days_since_last_activity = None
        if account.get("last_activity_date"):
            try:
                last_activity = datetime.strptime(
                    account["last_activity_date"], "%Y-%m-%d"
                ).date()
                days_since_last_activity = (reference_date - last_activity).days
            except ValueError:
                days_since_last_activity = None

        dormant_reactivation = False
        if (
            account.get("account_status") == "DORMANT"
            and days_since_last_activity is not None
            and days_since_last_activity <= 30
        ):
            dormant_reactivation = True

        account["days_since_last_activity"] = days_since_last_activity
        account["dormant_reactivation"] = dormant_reactivation

        accounts.append(account)

    # Top-level computed flags
    any_dormant_reactivation = any(a["dormant_reactivation"] for a in accounts)
    multiple_accounts = len(accounts) > 1
    has_multi_currency_account = any(
        a.get("account_type") == "MULTI_CURRENCY" for a in accounts
    )
    active_account_ids = [
        a["account_id"] for a in accounts if a.get("account_status") == "ACTIVE"
    ]

    result = {
        "customer_id": customer_id,
        "accounts": accounts,
        "computed_flags": {
            "any_dormant_reactivation": any_dormant_reactivation,
            "multiple_accounts": multiple_accounts,
            "has_multi_currency_account": has_multi_currency_account,
            "active_account_ids": active_account_ids,
        },
    }

    return json.dumps(result, default=str)
