"""
Pydantic schema for the investigation verdict output.
"""

from typing import List, Optional
from pydantic import BaseModel

class WatchlistHit(BaseModel):
    watchlist_id: str
    entity_name: str
    match_type: str
    watchlist_type: str
    source: str
    risk_score: int
    is_absolute_prohibition: bool

class SupportingData(BaseModel):
    amounts: Optional[List[str]] = None
    dates: Optional[List[str]] = None
    counterparties: Optional[List[str]] = None
    accounts_involved: Optional[List[str]] = None
    transaction_ids: Optional[List[str]] = None
    watchlist_ids: Optional[List[str]] = None
    watchlist_hits: Optional[List[WatchlistHit]] = None

class KeyEvidenceItem(BaseModel):
    rule_mapped: str
    finding: str
    supporting_data: SupportingData
    regulatory_significance: str
    source_table: str
    statistical_context: Optional[str] = None

class FalsePositiveHypothesis(BaseModel):
    hypothesis: str
    assessment: str
    reason: str

class InvestigationVerdict(BaseModel):
    investigation_id: Optional[str] = None
    alert_id: Optional[str] = None
    customer_id: Optional[str] = None
    verdict: str  # TRUE_POSITIVE / FALSE_POSITIVE / INCONCLUSIVE
    confidence: str  # HIGH / MEDIUM / LOW
    sar_recommended: bool
    duplicate_sar_safe: bool
    rules_triggered: list[str]
    investigation_summary: Optional[str] = None
    summary: Optional[str] = None
    false_positive_hypotheses_considered: Optional[List[FalsePositiveHypothesis]] = None
    key_evidence: Optional[List[KeyEvidenceItem]] = None
    chain_of_thought: Optional[list[dict]] = None
    total_tools_called: Optional[int] = None
