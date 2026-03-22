"""
Tool: get_customer_profile

Retrieves the full KYC profile for a customer with computed risk flags.
"""

import json
from datetime import date, datetime
from langchain_core.tools import tool
from tools.db import get_connection


@tool
def get_customer_profile(customer_id: str) -> str:
    """Retrieve the full KYC profile for a customer including identity details,
    declared income, occupation, document validity status, and PEP/sanctions flags.
    Use this as the FIRST tool in any investigation to establish the financial
    baseline before examining any transactions."""

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        )
        row = cursor.fetchone()

    if not row:
        return json.dumps({"error": f"Customer {customer_id} not found"})

    data = dict(row)

    # Round monetary values
    if data.get("annual_income_declared_gbp") is not None:
        data["annual_income_declared_gbp"] = round(data["annual_income_declared_gbp"], 2)

    # Compute flags
    today = date.today()

    # kyc_overdue_days
    kyc_overdue_days = None
    if data.get("kyc_last_reviewed"):
        try:
            reviewed = datetime.strptime(data["kyc_last_reviewed"], "%Y-%m-%d").date()
            kyc_overdue_days = (today - reviewed).days
        except ValueError:
            kyc_overdue_days = None

    # kyc_is_lapsed
    kyc_is_lapsed = False
    if data.get("kyc_status") in ("EXPIRED", "PENDING"):
        kyc_is_lapsed = True
    elif kyc_overdue_days is not None and kyc_overdue_days > 365:
        kyc_is_lapsed = True

    # document_expired
    document_expired = False
    if data.get("kyc_document_expiry"):
        try:
            expiry = datetime.strptime(data["kyc_document_expiry"], "%Y-%m-%d").date()
            document_expired = expiry < today
        except ValueError:
            document_expired = False

    # income_tier
    income = data.get("annual_income_declared_gbp")
    if income is None or income == 0:
        income_tier = "UNDECLARED"
    elif income < 25000:
        income_tier = "LOW"
    elif income < 60000:
        income_tier = "MEDIUM"
    elif income < 150000:
        income_tier = "HIGH"
    else:
        income_tier = "ULTRA_HIGH"

    # is_pep_or_sanctioned
    is_pep_or_sanctioned = bool(data.get("pep_flag") == 1 or data.get("sanctions_flag") == 1)

    # requires_enhanced_due_diligence
    requires_edd = bool(data.get("pep_flag") == 1 or data.get("risk_rating") == "HIGH")

    data["computed_flags"] = {
        "kyc_overdue_days": kyc_overdue_days,
        "kyc_is_lapsed": kyc_is_lapsed,
        "document_expired": document_expired,
        "income_tier": income_tier,
        "is_pep_or_sanctioned": is_pep_or_sanctioned,
        "requires_enhanced_due_diligence": requires_edd,
    }

    return json.dumps(data, default=str)
