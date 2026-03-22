"""
Pydantic schema for an incoming AML alert payload.
"""

from pydantic import BaseModel


class AlertPayload(BaseModel):
    alert_id: str
    generated_at: str
    alert_source: str
    alert_type: str
    severity: str  # LOW / MEDIUM / HIGH / CRITICAL
    customer_id: str
    triggered_rules: list[str]
    observation_window_start: str  # YYYY-MM-DD
    observation_window_end: str  # YYYY-MM-DD
    total_flagged_transactions: int
    flagged_amount_gbp: float
    alert_narrative: str
