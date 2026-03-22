"""
Pydantic schema for the investigation verdict output.
"""

from pydantic import BaseModel


class InvestigationVerdict(BaseModel):
    investigation_id: str
    alert_id: str
    customer_id: str
    verdict: str  # TRUE_POSITIVE / FALSE_POSITIVE / INCONCLUSIVE
    confidence: str  # HIGH / MEDIUM / LOW
    sar_recommended: bool
    duplicate_sar_safe: bool
    rules_triggered: list[str]
    summary: str
    chain_of_thought: list[dict]
    total_tools_called: int
