"""
Tool: get_transaction_history

Fetches transactions for an account over a date range with summary statistics
and pre-computed AML signal flags.
"""

import json
from datetime import datetime, timedelta
from langchain_core.tools import tool
from tools.db import get_connection


@tool
def get_transaction_history(
    account_id: str,
    date_from: str,
    date_to: str,
    direction: str = "BOTH",
    min_amount_gbp: float = 0.0,
) -> str:
    """Fetch transactions for a specific account over a date range. Returns raw
    transactions and pre-computed summary statistics. Always call get_account_summary
    first to get valid account_ids. The direction filter accepts CREDIT, DEBIT, or
    BOTH. Use min_amount_gbp to focus on large transactions in follow-up queries."""

    with get_connection() as conn:
        query = (
            "SELECT * FROM transactions "
            "WHERE account_id = ? "
            "AND date(transaction_datetime) BETWEEN date(?) AND date(?) "
            "AND amount_gbp >= ?"
        )
        params = [account_id, date_from, date_to, min_amount_gbp]

        if direction.upper() in ("CREDIT", "DEBIT"):
            query += " AND direction = ?"
            params.append(direction.upper())

        query += " ORDER BY transaction_datetime ASC"

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    transactions = [dict(row) for row in rows]

    # Round monetary values
    for txn in transactions:
        if txn.get("amount_gbp") is not None:
            txn["amount_gbp"] = round(txn["amount_gbp"], 2)
        if txn.get("original_amount") is not None:
            txn["original_amount"] = round(txn["original_amount"], 2)

    if not transactions:
        return json.dumps({
            "SUMMARY": None,
            "COMPUTED_FLAGS": {"no_transactions_found": True},
            "SAMPLE_TRANSACTIONS_TOP_5": [],
            "total_transaction_count": 0,
            "note": "No transactions found matching criteria.",
        })

    # Summary statistics
    credits = [t for t in transactions if t.get("direction") == "CREDIT"]
    debits = [t for t in transactions if t.get("direction") == "DEBIT"]

    total_credits_gbp = round(sum(t["amount_gbp"] for t in credits), 2)
    total_debits_gbp = round(sum(t["amount_gbp"] for t in debits), 2)
    net_change_gbp = round(total_credits_gbp - total_debits_gbp, 2)

    if total_credits_gbp == 0:
        retention_ratio = 1.0
    else:
        retention_ratio = round(net_change_gbp / total_credits_gbp, 4)

    counterparty_account_ids = set()
    counterparty_names = set()
    for t in transactions:
        if t.get("counterparty_account_id"):
            counterparty_account_ids.add(t["counterparty_account_id"])
        if t.get("counterparty_name"):
            counterparty_names.add(t["counterparty_name"])

    international_count = sum(1 for t in transactions if t.get("is_international") == 1)
    high_risk_count = sum(
        1 for t in transactions if t.get("counterparty_is_high_risk_jurisdiction") == 1
    )

    summary = {
        "total_credits_gbp": total_credits_gbp,
        "total_debits_gbp": total_debits_gbp,
        "net_change_gbp": net_change_gbp,
        "retention_ratio": retention_ratio,
        "unique_counterparty_accounts": len(counterparty_account_ids),
        "unique_counterparty_names": len(counterparty_names),
        "counterparty_names_list": sorted(list(counterparty_names)),
        "international_transaction_count": international_count,
        "high_risk_jurisdiction_count": high_risk_count,
    }

    # Computed flags

    # rapid_outflow_detected
    rapid_outflow_detected = False
    large_credits = [
        t for t in credits if t["amount_gbp"] > 5000
    ]
    for credit_txn in large_credits:
        try:
            credit_dt = datetime.fromisoformat(credit_txn["transaction_datetime"])
        except (ValueError, TypeError):
            continue
        window_end = credit_dt + timedelta(hours=48)
        for debit_txn in debits:
            if debit_txn["amount_gbp"] > 1000:
                try:
                    debit_dt = datetime.fromisoformat(debit_txn["transaction_datetime"])
                except (ValueError, TypeError):
                    continue
                if credit_dt <= debit_dt <= window_end:
                    rapid_outflow_detected = True
                    break
        if rapid_outflow_detected:
            break

    # structuring_presignal
    structuring_presignal = False
    if credits:
        structured_credits = [
            t for t in credits if 8000 <= t["amount_gbp"] <= 9999
        ]
        pct = len(structured_credits) / len(credits)
        if pct >= 0.40 and len(structured_credits) >= 5:
            structuring_presignal = True

    # low_retention
    low_retention = retention_ratio < 0.05

    # high_counterparty_diversity
    high_counterparty_diversity = len(counterparty_account_ids) > 10

    # has_high_risk_jurisdiction_transactions
    has_high_risk = high_risk_count > 0

    computed_flags = {
        "rapid_outflow_detected": rapid_outflow_detected,
        "structuring_presignal": structuring_presignal,
        "low_retention": low_retention,
        "high_counterparty_diversity": high_counterparty_diversity,
        "has_high_risk_jurisdiction_transactions": has_high_risk,
    }

    # Separate high-risk and regular transactions
    high_risk_txns = [t for t in transactions
                      if t.get("counterparty_is_high_risk_jurisdiction")]

    regular = [t for t in transactions
               if not t.get("counterparty_is_high_risk_jurisdiction")]

    # If structuring presignal, prioritise sub-threshold credits
    if computed_flags["structuring_presignal"]:
        structured = sorted(
            [t for t in regular if 8000 <= t.get("amount_gbp", 0) <= 9999],
            key=lambda t: t.get("amount_gbp", 0),
            reverse=True
        )[:5]
        top_transactions = high_risk_txns + structured
    else:
        top_regular = sorted(
            regular, key=lambda t: t.get("amount_gbp", 0), reverse=True
        )[:5]
        top_transactions = high_risk_txns + top_regular

    result = {
        "SUMMARY": summary,
        "COMPUTED_FLAGS": computed_flags,
        "SAMPLE_TRANSACTIONS_TOP_5": top_transactions,
        "total_transaction_count": len(transactions),
        "note": "Full transaction detail available via filtered query",
    }

    return json.dumps(result, default=str)
