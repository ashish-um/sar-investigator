"""
Evidence Package builder.

Transforms an agent verdict dict + alert dict into a structured,
auditable EvidencePackage by re-querying the SQLite database for
full KYC, account, and transaction data.

This module does NOT call the LangGraph agent or any LangChain tools.
"""

import json
import os
from datetime import datetime, timedelta

from tools.db import get_connection
from evidence.schema import (
    EvidencePackage,
    SubjectProfile,
    AccountSummary,
    TransactionEvidence,
    RuleEvidence,
    ExculpatoryHypothesis,
)
from sar.glossary_codes import RULE_TO_GLOSSARY_CODES


# ── Rule definitions (mirror of agent/prompts.py) ────────────────────────

RULE_DEFINITIONS: dict[str, dict[str, str]] = {
    "RULE-01": {
        "name": "Structuring / Smurfing",
        "regulatory_basis": "POCA 2002 s.327; FATF Recommendation 1",
    },
    "RULE-02": {
        "name": "Rapid Movement of Funds",
        "regulatory_basis": "FATF Rec. 20; FCA Financial Crime Guide 3.2",
    },
    "RULE-03": {
        "name": "High-Risk Jurisdiction Transfer",
        "regulatory_basis": "FATF Rec. 19; HM Treasury Advisory Notice",
    },
    "RULE-04": {
        "name": "Transaction-Profile Mismatch",
        "regulatory_basis": "FCA SYSC 6.3; MLR 2017 Reg. 28",
    },
    "RULE-05": {
        "name": "Dormant Account Reactivation",
        "regulatory_basis": "JMLSG Guidance Part I, 6.42",
    },
    "RULE-06": {
        "name": "Third-Party Funding",
        "regulatory_basis": "FATF Typology Report on Trade-Based ML",
    },
    "RULE-07": {
        "name": "PEP / Sanctions Proximity",
        "regulatory_basis": "MLR 2017 Reg. 35; HM Treasury Consolidated List",
    },
    "RULE-08": {
        "name": "Round Tripping / Layering",
        "regulatory_basis": "FATF Typology; HMRC Structured Guidance",
    },
}

RULE_NARRATIVES: dict[str, str] = {
    "RULE-01": "structured below the £10,000 reporting threshold",
    "RULE-02": "moved rapidly within 48 hours of receipt",
    "RULE-03": "sent to or received from high-risk jurisdictions",
    "RULE-04": "inconsistent with declared income profile",
    "RULE-05": "on a previously dormant account",
    "RULE-06": "received from multiple unrelated third parties",
    "RULE-07": "involving a PEP or sanctions-linked individual",
    "RULE-08": "exhibiting round-trip layering patterns",
}


def build_evidence_package(verdict: dict, alert: dict) -> EvidencePackage:
    """
    Build a complete, auditable EvidencePackage from the agent verdict
    and the original alert, re-querying the database for full detail.

    Raises ValueError if the customer is not found in the database.
    """

    # ── Step 1: Extract identifiers ──────────────────────────────────
    customer_id = alert["customer_id"]
    alert_id = alert["alert_id"]
    obs_start = alert["observation_window_start"]
    obs_end = alert["observation_window_end"]
    investigation_id = f"INV-{alert_id}"

    # Reference date for date computations (NOT date.today())
    ref_date = datetime.strptime(obs_end, "%Y-%m-%d").date()

    # ── Step 2: Build SubjectProfile ─────────────────────────────────
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        )
        row = cursor.fetchone()

    if not row:
        raise ValueError(f"Customer {customer_id} not found in database")

    cust = dict(row)

    # Compute KYC lapse
    kyc_overdue_days = None
    kyc_is_lapsed = False
    if cust.get("kyc_last_reviewed"):
        try:
            reviewed = datetime.strptime(cust["kyc_last_reviewed"], "%Y-%m-%d").date()
            kyc_overdue_days = (ref_date - reviewed).days
        except ValueError:
            pass

    if cust.get("kyc_status") in ("EXPIRED", "PENDING"):
        kyc_is_lapsed = True
    elif kyc_overdue_days is not None and kyc_overdue_days > 365:
        kyc_is_lapsed = True

    # Compute income tier
    income = cust.get("annual_income_declared_gbp") or 0
    if income == 0:
        income_tier = "UNDECLARED"
    elif income < 25000:
        income_tier = "LOW"
    elif income < 60000:
        income_tier = "MEDIUM"
    elif income < 150000:
        income_tier = "HIGH"
    else:
        income_tier = "ULTRA_HIGH"

    subject = SubjectProfile(
        full_name=cust.get("full_name", ""),
        date_of_birth=str(cust.get("date_of_birth", "")),
        nationality=cust.get("nationality", ""),
        country_of_residence=cust.get("country_of_residence", ""),
        occupation=cust.get("occupation", ""),
        employer_name=cust.get("employer_name", ""),
        annual_income_declared_gbp=round(float(income), 2),
        income_tier=income_tier,
        kyc_status=cust.get("kyc_status", ""),
        kyc_document_type=cust.get("kyc_document_type", ""),
        kyc_document_expiry=str(cust.get("kyc_document_expiry", "")),
        kyc_is_lapsed=kyc_is_lapsed,
        kyc_overdue_days=kyc_overdue_days,
        pep_flag=bool(cust.get("pep_flag")),
        sanctions_flag=bool(cust.get("sanctions_flag")),
        risk_rating=cust.get("risk_rating", ""),
        address=cust.get("address", ""),
        customer_type=cust.get("customer_type", ""),
    )

    # ── Step 3: Build AccountSummary list ────────────────────────────
    with get_connection() as conn:
        acc_cursor = conn.execute(
            "SELECT * FROM accounts WHERE customer_id = ?", (customer_id,)
        )
        acc_rows = acc_cursor.fetchall()

    accounts_examined = []
    all_account_ids = []
    total_transactions_reviewed = 0

    for acc_row in acc_rows:
        acc = dict(acc_row)
        account_id = acc["account_id"]
        all_account_ids.append(account_id)

        # Compute credits/debits/retention in the observation window
        with get_connection() as conn:
            txn_cursor = conn.execute(
                "SELECT * FROM transactions "
                "WHERE account_id = ? "
                "AND date(transaction_datetime) BETWEEN date(?) AND date(?)",
                (account_id, obs_start, obs_end),
            )
            txns = [dict(r) for r in txn_cursor.fetchall()]

        total_transactions_reviewed += len(txns)
        credits = sum(t["amount_gbp"] for t in txns if t.get("direction") == "CREDIT")
        debits = sum(t["amount_gbp"] for t in txns if t.get("direction") == "DEBIT")
        retention = round((credits - debits) / credits, 4) if credits > 0 else 1.0

        # Dormant reactivation check
        dormant_reactivation = False
        if acc.get("account_status") == "DORMANT":
            if acc.get("last_activity_date"):
                try:
                    last_act = datetime.strptime(acc["last_activity_date"], "%Y-%m-%d").date()
                    if (ref_date - last_act).days <= 30:
                        dormant_reactivation = True
                except ValueError:
                    pass

        accounts_examined.append(AccountSummary(
            account_id=account_id,
            account_type=acc.get("account_type", ""),
            currency=acc.get("currency", "GBP"),
            account_status=acc.get("account_status", ""),
            iban=acc.get("iban", ""),
            average_monthly_balance_gbp=round(float(acc.get("average_monthly_balance_gbp", 0)), 2),
            last_activity_date=str(acc.get("last_activity_date", "")),
            dormant_reactivation=dormant_reactivation,
            total_credits_in_window_gbp=round(credits, 2),
            total_debits_in_window_gbp=round(debits, 2),
            retention_ratio=retention,
        ))

    # ── Step 4: Build RuleEvidence list ──────────────────────────────
    triggered_rules = verdict.get("rules_triggered", [])
    key_evidence = verdict.get("key_evidence", [])

    rules_evidence = []
    for rule_id in triggered_rules:
        rule_def = RULE_DEFINITIONS.get(rule_id, {})

        # Find matching key_evidence entry
        matching_ev = None
        for ev in key_evidence:
            mapped = ev.get("rule_mapped", "")
            if mapped == rule_id:
                matching_ev = ev
                break

        if matching_ev:
            evidence_summary = matching_ev.get("significance", matching_ev.get("finding", ""))
            data_points = [matching_ev.get("data_point", "")]
            # Add statistical_context if present
            stat_ctx = matching_ev.get("statistical_context")
            if stat_ctx:
                data_points.append(stat_ctx)
        else:
            evidence_summary = f"{rule_id} triggered during investigation"
            data_points = []

        rules_evidence.append(RuleEvidence(
            rule_id=rule_id,
            rule_name=rule_def.get("name", rule_id),
            regulatory_basis=rule_def.get("regulatory_basis", ""),
            triggered=True,
            evidence_summary=evidence_summary,
            data_points=data_points,
        ))

    # ── Step 5: Build TransactionEvidence list ───────────────────────
    transaction_evidence = []

    for rule_id in triggered_rules:
        rule_txns = _query_transactions_for_rule(
            rule_id, all_account_ids, obs_start, obs_end
        )
        if not rule_txns:
            continue

        txn_ids = [t["transaction_id"] for t in rule_txns]
        dates = sorted(set(
            t["transaction_datetime"].split("T")[0] if "T" in str(t["transaction_datetime"])
            else str(t["transaction_datetime"])[:10]
            for t in rule_txns
        ))
        amounts = [round(t["amount_gbp"], 2) for t in rule_txns]
        counterparties = sorted(set(
            t.get("counterparty_name", "Unknown") for t in rule_txns
            if t.get("counterparty_name")
        ))
        countries = sorted(set(
            t.get("counterparty_country", "Unknown") for t in rule_txns
            if t.get("counterparty_country")
        ))
        refs = sorted(set(
            t.get("payment_reference", "") for t in rule_txns
            if t.get("payment_reference")
        ))
        total_val = round(sum(amounts), 2)
        count = len(rule_txns)
        narrative_desc = RULE_NARRATIVES.get(rule_id, "flagged by investigation")
        narrative = f"{count} transaction{'s' if count != 1 else ''} totalling £{total_val:,.2f} {narrative_desc}"

        transaction_evidence.append(TransactionEvidence(
            rule_id=rule_id,
            transaction_ids=txn_ids,
            dates=dates,
            amounts_gbp=amounts,
            counterparties=counterparties,
            counterparty_countries=countries,
            payment_references=refs,
            total_value_gbp=total_val,
            transaction_count=count,
            narrative=narrative,
        ))

    # ── Step 6: Map glossary codes ───────────────────────────────────
    all_codes: list[str] = []
    for rule_id in triggered_rules:
        all_codes.extend(RULE_TO_GLOSSARY_CODES.get(rule_id, []))
    nca_glossary_codes = sorted(set(all_codes))

    # ── Step 7: Exculpatory hypotheses ───────────────────────────────
    hyp_list = verdict.get("false_positive_hypotheses_considered", [])
    exculpatory = [
        ExculpatoryHypothesis(
            hypothesis=h.get("hypothesis", ""),
            assessment=h.get("assessment", ""),
            reason=h.get("reason", ""),
        )
        for h in hyp_list
    ]

    # ── Step 8: Prior SAR check ──────────────────────────────────────
    duplicate_sar_safe = True
    prior_sar_reference = None

    with get_connection() as conn:
        hist_cursor = conn.execute(
            "SELECT * FROM aml_alerts_history WHERE customer_id = ? ORDER BY alert_date DESC",
            (customer_id,),
        )
        hist_rows = hist_cursor.fetchall()

    for h in hist_rows:
        h_dict = dict(h)
        if h_dict.get("sar_filed") == 1 and h_dict.get("alert_date"):
            try:
                alert_date = datetime.strptime(h_dict["alert_date"], "%Y-%m-%d").date()
                if (ref_date - alert_date).days <= 365:
                    duplicate_sar_safe = False
                    prior_sar_reference = h_dict.get("sar_reference")
                    break
            except ValueError:
                continue

    # ── Step 9: Compute totals ───────────────────────────────────────
    total_value_flagged = sum(te.total_value_gbp for te in transaction_evidence)

    # ── Step 10: Validate, save, return ──────────────────────────────
    investigation_summary = verdict.get(
        "investigation_summary",
        verdict.get("summary", ""),
    )

    package = EvidencePackage(
        investigation_id=investigation_id,
        alert_id=alert_id,
        customer_id=customer_id,
        generated_at=datetime.utcnow().isoformat(),
        agent_verdict=verdict.get("verdict", ""),
        agent_confidence=verdict.get("confidence", ""),
        agent_investigation_summary=investigation_summary or "",
        subject=subject,
        accounts_examined=accounts_examined,
        observation_window_start=obs_start,
        observation_window_end=obs_end,
        total_transactions_reviewed=total_transactions_reviewed,
        total_value_flagged_gbp=round(total_value_flagged, 2),
        transaction_evidence=transaction_evidence,
        rules_triggered=rules_evidence,
        exculpatory_hypotheses=exculpatory,
        duplicate_sar_safe=duplicate_sar_safe,
        prior_sar_reference=prior_sar_reference,
        nca_glossary_codes=nca_glossary_codes,
    )

    # Save to output/evidence/
    os.makedirs("output/evidence", exist_ok=True)
    out_path = f"output/evidence/{investigation_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(package.model_dump_json(indent=2))

    return package


# ── Per-rule transaction queries ─────────────────────────────────────────

def _query_transactions_for_rule(
    rule_id: str,
    account_ids: list[str],
    obs_start: str,
    obs_end: str,
) -> list[dict]:
    """Query transactions matching a specific rule's trigger conditions."""

    if not account_ids:
        return []

    placeholders = ",".join("?" for _ in account_ids)
    base_where = (
        f"account_id IN ({placeholders}) "
        f"AND date(transaction_datetime) BETWEEN date(?) AND date(?)"
    )
    base_params: list = list(account_ids) + [obs_start, obs_end]

    with get_connection() as conn:
        if rule_id == "RULE-01":
            # Structuring: credits clustered below £10,000
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "AND direction = 'CREDIT' AND amount_gbp >= 7500 AND amount_gbp < 10000 "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-02":
            # Rapid movement: all credits > 5000 AND debits > 1000
            # (we return all involved transactions for the narrative)
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "AND ((direction = 'CREDIT' AND amount_gbp > 5000) "
                "OR (direction = 'DEBIT' AND amount_gbp > 1000)) "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-03":
            # High-risk jurisdiction
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "AND counterparty_is_high_risk_jurisdiction = 1 "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-04":
            # Profile mismatch: all credits in the window
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "AND direction = 'CREDIT' "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-05":
            # Dormant reactivation: all transactions in the window
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-06":
            # Third-party funding: credits from many distinct counterparties
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "AND direction = 'CREDIT' "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-07":
            # PEP/Sanctions: all transactions in the window
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        elif rule_id == "RULE-08":
            # Round tripping: SWIFT debits + credits from different counterparties
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "AND (transaction_type LIKE '%SWIFT%' OR transaction_type LIKE '%WIRE%' "
                "OR is_international = 1) "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )
        else:
            # Fallback: all transactions
            cursor = conn.execute(
                f"SELECT * FROM transactions WHERE {base_where} "
                "ORDER BY transaction_datetime ASC",
                base_params,
            )

        return [dict(r) for r in cursor.fetchall()]
