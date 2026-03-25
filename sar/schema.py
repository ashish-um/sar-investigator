"""
Pydantic model for the SAR Document — the final NCA-compliant
SAR narrative produced by the generation layer.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class SARDocument(BaseModel):
    sar_draft_id: str                       # "SAR-DRAFT-{investigation_id}"
    investigation_id: str
    customer_id: str
    generated_at: str
    nca_glossary_codes: List[str]

    # ── Six narrative sections ────────────────────────────────────────
    section_1_subject_identity: str
    section_2_account_overview: str
    section_3_transaction_chronology: str
    section_4_reason_for_suspicion: str
    section_5_exculpatory_analysis: str
    section_6_conclusion: str

    # ── Metadata ─────────────────────────────────────────────────────
    total_suspected_criminal_proceeds_gbp: float
    poca_offence_section: str               # e.g. "s.327 POCA 2002 (Concealing)"
    status: str                             # DRAFT | ANALYST_REVIEWED | APPROVED
    analyst_edits: Optional[Dict[str, str]] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
