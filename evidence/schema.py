"""
Pydantic models for the Evidence Package — the auditable record
of all data examined during an AML investigation.
"""

from typing import List, Optional
from pydantic import BaseModel


class SubjectProfile(BaseModel):
    full_name: str
    date_of_birth: str
    nationality: str
    country_of_residence: str
    occupation: str
    employer_name: str
    annual_income_declared_gbp: float
    income_tier: str                   # LOW | MEDIUM | HIGH | ULTRA_HIGH
    kyc_status: str
    kyc_document_type: str
    kyc_document_expiry: str
    kyc_is_lapsed: bool
    kyc_overdue_days: Optional[int] = None
    pep_flag: bool
    sanctions_flag: bool
    risk_rating: str
    address: str
    customer_type: str


class AccountSummary(BaseModel):
    account_id: str
    account_type: str
    currency: str
    account_status: str
    iban: str
    average_monthly_balance_gbp: float
    last_activity_date: str
    dormant_reactivation: bool
    total_credits_in_window_gbp: float
    total_debits_in_window_gbp: float
    retention_ratio: float             # net / credits — below 0.05 = pass-through


class TransactionEvidence(BaseModel):
    rule_id: str
    transaction_ids: List[str]
    dates: List[str]
    amounts_gbp: List[float]
    counterparties: List[str]
    counterparty_countries: List[str]
    payment_references: List[str]
    total_value_gbp: float
    transaction_count: int
    narrative: str                     # One quantified sentence


class RuleEvidence(BaseModel):
    rule_id: str                       # "RULE-01" ... "RULE-08"
    rule_name: str
    regulatory_basis: str
    triggered: bool
    evidence_summary: str
    data_points: List[str]


class ExculpatoryHypothesis(BaseModel):
    hypothesis: str
    assessment: str                    # REJECTED | ACCEPTED
    reason: str


class EvidencePackage(BaseModel):
    investigation_id: str              # "INV-{alert_id}"
    alert_id: str
    customer_id: str
    generated_at: str                  # ISO datetime
    agent_verdict: str                 # TRUE_POSITIVE | FALSE_POSITIVE | INCONCLUSIVE
    agent_confidence: str
    agent_investigation_summary: str

    subject: SubjectProfile
    accounts_examined: List[AccountSummary]

    observation_window_start: str
    observation_window_end: str
    total_transactions_reviewed: int
    total_value_flagged_gbp: float
    transaction_evidence: List[TransactionEvidence]
    rules_triggered: List[RuleEvidence]
    exculpatory_hypotheses: List[ExculpatoryHypothesis]

    duplicate_sar_safe: bool
    prior_sar_reference: Optional[str] = None
    nca_glossary_codes: List[str]

    # Populated later by analyst via UI
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    analyst_amendments: Optional[str] = None
