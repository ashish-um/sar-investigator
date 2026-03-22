"""
Unit tests for the four internal investigation tools.

Tests run against the actual SQLite database populated from CSVs.
Each test:
  - Calls the tool function directly
  - Asserts the return value is valid JSON
  - Asserts key fields are present
  - Asserts computed_flags key exists
"""

import json
import pytest

from tools.internal.get_customer_profile import get_customer_profile
from tools.internal.get_account_summary import get_account_summary
from tools.internal.get_transaction_history import get_transaction_history
from tools.internal.get_prior_alert_history import get_prior_alert_history


class TestGetCustomerProfile:
    """Tests for get_customer_profile tool."""

    def test_valid_customer(self):
        result = get_customer_profile.invoke({"customer_id": "CUST-UK-004821"})
        assert isinstance(result, str)
        data = json.loads(result)
        assert "customer_id" in data
        assert data["customer_id"] == "CUST-UK-004821"
        assert "full_name" in data
        assert "annual_income_declared_gbp" in data
        assert "computed_flags" in data
        flags = data["computed_flags"]
        assert "kyc_overdue_days" in flags
        assert "kyc_is_lapsed" in flags
        assert "document_expired" in flags
        assert "income_tier" in flags
        assert "is_pep_or_sanctioned" in flags
        assert "requires_enhanced_due_diligence" in flags

    def test_invalid_customer(self):
        result = get_customer_profile.invoke({"customer_id": "NONEXISTENT"})
        data = json.loads(result)
        assert "error" in data


class TestGetAccountSummary:
    """Tests for get_account_summary tool."""

    def test_valid_customer(self):
        result = get_account_summary.invoke({"customer_id": "CUST-UK-004821"})
        assert isinstance(result, str)
        data = json.loads(result)
        assert "accounts" in data
        assert len(data["accounts"]) > 0
        assert "computed_flags" in data
        flags = data["computed_flags"]
        assert "any_dormant_reactivation" in flags
        assert "multiple_accounts" in flags
        assert "has_multi_currency_account" in flags
        assert "active_account_ids" in flags

    def test_invalid_customer(self):
        result = get_account_summary.invoke({"customer_id": "NONEXISTENT"})
        data = json.loads(result)
        assert "error" in data


class TestGetTransactionHistory:
    """Tests for get_transaction_history tool."""

    def test_valid_account(self):
        result = get_transaction_history.invoke({
            "account_id": "ACC-UK-000001",
            "date_from": "2024-01-01",
            "date_to": "2024-12-31",
        })
        assert isinstance(result, str)
        data = json.loads(result)
        assert "total_transaction_count" in data
        assert "SAMPLE_TRANSACTIONS_TOP_5" in data
        assert "COMPUTED_FLAGS" in data
        if data["total_transaction_count"] > 0:
            assert "SUMMARY" in data
            summary = data["SUMMARY"]
            assert "total_credits_gbp" in summary
            assert "total_debits_gbp" in summary
            assert "retention_ratio" in summary
            flags = data["COMPUTED_FLAGS"]
            assert "rapid_outflow_detected" in flags
            assert "structuring_presignal" in flags
            assert "low_retention" in flags
            assert "high_counterparty_diversity" in flags
            assert "has_high_risk_jurisdiction_transactions" in flags

    def test_no_transactions(self):
        result = get_transaction_history.invoke({
            "account_id": "ACC-UK-000001",
            "date_from": "1990-01-01",
            "date_to": "1990-12-31",
        })
        data = json.loads(result)
        assert data["total_transaction_count"] == 0
        assert data["COMPUTED_FLAGS"]["no_transactions_found"] is True


class TestGetPriorAlertHistory:
    """Tests for get_prior_alert_history tool."""

    def test_customer_with_alerts(self):
        result = get_prior_alert_history.invoke({"customer_id": "CUST-UK-007341"})
        assert isinstance(result, str)
        data = json.loads(result)
        assert "SAMPLE_ALERTS_TOP_3" in data
        assert len(data["SAMPLE_ALERTS_TOP_3"]) > 0
        assert "COMPUTED_FLAGS" in data
        ctx = data["COMPUTED_FLAGS"]
        assert "duplicate_sar_safe" in ctx
        assert "prior_true_positives" in ctx
        assert "prior_false_positives" in ctx
        assert "sar_ever_filed" in ctx
        assert "repeat_offender" in ctx
        # Verify rules_triggered is a list, not a pipe-separated string
        first_alert = data["SAMPLE_ALERTS_TOP_3"][0]
        assert isinstance(first_alert["rules_triggered"], list)

    def test_customer_without_alerts(self):
        result = get_prior_alert_history.invoke({"customer_id": "CUST-UK-004821"})
        data = json.loads(result)
        assert data["SAMPLE_ALERTS_TOP_3"] == []
        assert data["COMPUTED_FLAGS"]["duplicate_sar_safe"] is True
