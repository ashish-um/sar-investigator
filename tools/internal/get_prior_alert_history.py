"""
Tool: get_prior_alert_history

Retrieves all previous AML alerts for a customer with risk context flags.
"""

import json
from datetime import date, datetime
from langchain_core.tools import tool
from tools.db import get_connection


@tool
def get_prior_alert_history(customer_id: str) -> str:
    """Retrieve all previous AML alerts for a customer including their dispositions,
    SAR filing status, and analyst notes. Always call this before recommending a SAR
    filing to check for duplicates. A duplicate SAR for the same activity window is
    prohibited by the NCA."""

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM aml_alerts_history WHERE customer_id = ? ORDER BY alert_date DESC",
            (customer_id,),
        )
        rows = cursor.fetchall()

    if not rows:
        # No prior alerts
        result = {
            "SUMMARY": None,
            "COMPUTED_FLAGS": {
                "duplicate_sar_safe": True,
                "prior_true_positives": 0,
                "prior_false_positives": 0,
                "sar_ever_filed": False,
                "repeat_offender": False,
            },
            "SAMPLE_ALERTS_TOP_3": [],
            "total_alert_count": 0,
            "note": "No prior alerts found.",
        }
        return json.dumps(result, default=str)

    today = date.today()
    alerts = []

    for row in rows:
        alert = dict(row)

        # Split rules_triggered into a list
        if alert.get("rules_triggered"):
            alert["rules_triggered"] = alert["rules_triggered"].split("|")
        else:
            alert["rules_triggered"] = []

        alerts.append(alert)

    # Compute risk context
    prior_true_positives = sum(
        1 for a in alerts if a.get("disposition") == "TRUE_POSITIVE"
    )
    prior_false_positives = sum(
        1 for a in alerts if a.get("disposition") == "FALSE_POSITIVE"
    )
    sar_ever_filed = any(a.get("sar_filed") == 1 for a in alerts)
    repeat_offender = prior_true_positives >= 2

    # duplicate_sar_safe: check if any SAR filed within last 365 days
    duplicate_sar_safe = True
    for a in alerts:
        if a.get("sar_filed") == 1 and a.get("alert_date"):
            try:
                alert_date = datetime.strptime(a["alert_date"], "%Y-%m-%d").date()
                if (today - alert_date).days <= 365:
                    duplicate_sar_safe = False
                    break
            except ValueError:
                continue

    result = {
        "SUMMARY": None,
        "COMPUTED_FLAGS": {
            "duplicate_sar_safe": duplicate_sar_safe,
            "prior_true_positives": prior_true_positives,
            "prior_false_positives": prior_false_positives,
            "sar_ever_filed": sar_ever_filed,
            "repeat_offender": repeat_offender,
        },
        "SAMPLE_ALERTS_TOP_3": alerts[:3],
        "total_alert_count": len(alerts),
        "note": "Full alert history detail available via filtered query",
    }

    return json.dumps(result, default=str)
