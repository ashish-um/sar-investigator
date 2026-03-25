"""
SAR section prompt templates.

Each function returns a fully assembled prompt string for one SAR section.
The LLM receives the evidence package dict and all previously written
sections as context.
"""

import json


# ── Universal instruction block (included in EVERY prompt) ───────────────

_UNIVERSAL_RULES = """
MANDATORY INSTRUCTIONS — follow these rules exactly:
1. Write in plain English suitable for a UK law enforcement officer who is not a financial specialist.
2. Use only facts present in the Evidence Package below. Do not invent, infer, or extrapolate.
3. Include specific numbers in every paragraph: exact GBP amounts, dates, account IDs, transaction counts.
4. Write in past tense. Write as flowing prose — no bullet points, no headers inside the section.
5. Do not mention AI, automated systems, machine learning, or software tools of any kind.
6. Do not use legal Latin. If you cite a legal section, explain it in plain English immediately after.
7. Do not include any preamble or meta-commentary. Output ONLY the section text.
""".strip()


def _format_evidence(evidence: dict) -> str:
    """Compact JSON representation of the evidence for prompt inclusion."""
    return json.dumps(evidence, indent=2, default=str)


def _format_prior_sections(written_sections: dict) -> str:
    """Format previously written sections for cross-reference context."""
    if not written_sections:
        return "None yet — this is the first section."
    parts = []
    for key, text in written_sections.items():
        label = key.replace("section_", "Section ").replace("_", " ").title()
        parts.append(f"--- {label} ---\n{text}")
    return "\n\n".join(parts)


# ── Section 1: Subject Identity ──────────────────────────────────────────

def build_section_1_prompt(evidence: dict, written_sections: dict) -> str:
    subject = evidence.get("subject", {})
    codes = evidence.get("nca_glossary_codes", [])

    return f"""{_UNIVERSAL_RULES}

TASK: Write Section 1 — Subject Identity for a Suspicious Activity Report (SAR).

Begin the section with each applicable NCA glossary code on its own line, in the format:
XXCODE
(one code per line, before the paragraph)

The applicable glossary codes are: {', '.join(codes)}

Then write ONE paragraph identifying the reported subject. You MUST include ALL of the following fields from the subject profile:
- Full name: {subject.get('full_name', '')}
- Date of birth: {subject.get('date_of_birth', '')}
- Nationality: {subject.get('nationality', '')}
- Country of residence: {subject.get('country_of_residence', '')}
- Occupation: {subject.get('occupation', '')}
- Employer: {subject.get('employer_name', '')}
- Declared annual income: £{subject.get('annual_income_declared_gbp', 0):,.2f}
- Income tier: {subject.get('income_tier', '')}
- Home address: {subject.get('address', '')}
- KYC document type: {subject.get('kyc_document_type', '')}
- KYC document expiry: {subject.get('kyc_document_expiry', '')}
- KYC review status: {subject.get('kyc_status', '')}
- KYC lapsed: {subject.get('kyc_is_lapsed', False)} (if lapsed, state that it is {subject.get('kyc_overdue_days', 'N/A')} days overdue)
- PEP flag: {subject.get('pep_flag', False)}
- Sanctions flag: {subject.get('sanctions_flag', False)}
- Risk rating: {subject.get('risk_rating', '')}
- Customer type: {subject.get('customer_type', '')}

EVIDENCE PACKAGE:
{_format_evidence(evidence)}
"""


# ── Section 2: Account Overview ──────────────────────────────────────────

def build_section_2_prompt(evidence: dict, written_sections: dict) -> str:
    return f"""{_UNIVERSAL_RULES}

TASK: Write Section 2 — Account Overview for a Suspicious Activity Report (SAR).

For EACH account in the accounts_examined list below, write one paragraph covering:
- Account type, currency, and status
- IBAN
- Average monthly balance
- Last activity date
- Total credits and total debits during the observation window ({evidence.get('observation_window_start', '')} to {evidence.get('observation_window_end', '')})
- If retention_ratio is below 0.10, state explicitly that less than 10% of received funds were retained, indicating pass-through activity
- If dormant_reactivation is true, state the account was dormant before this activity

PREVIOUSLY WRITTEN SECTIONS (for cross-reference, do not repeat):
{_format_prior_sections(written_sections)}

EVIDENCE PACKAGE:
{_format_evidence(evidence)}
"""


# ── Section 3: Transaction Chronology ────────────────────────────────────

def build_section_3_prompt(evidence: dict, written_sections: dict) -> str:
    return f"""{_UNIVERSAL_RULES}

TASK: Write Section 3 — Transaction Chronology for a Suspicious Activity Report (SAR).

Write a chronological narrative of all suspicious transactions, grouped by the AML rule they triggered. For EACH group in the transaction_evidence list:
- State which AML rule the transactions relate to
- State the date range of the transactions
- State the number of transactions and the total value in GBP
- For each transaction or cluster, state the exact amount and date
- Name the counterparties and their countries
- Include account IDs and payment references where available
- Note transactions to high-risk jurisdictions explicitly
- Cross-reference account IDs from the Account Overview section

Write as flowing prose in chronological order. Do not use bullet points.

PREVIOUSLY WRITTEN SECTIONS (for cross-reference, do not repeat):
{_format_prior_sections(written_sections)}

EVIDENCE PACKAGE:
{_format_evidence(evidence)}
"""


# ── Section 4: Reason for Suspicion ──────────────────────────────────────

def build_section_4_prompt(evidence: dict, written_sections: dict) -> str:
    # Precompute income multiple info for the prompt
    income = evidence.get("subject", {}).get("annual_income_declared_gbp", 0)
    total_flagged = evidence.get("total_value_flagged_gbp", 0)
    income_multiple = round(total_flagged / income, 1) if income > 0 else 0

    return f"""{_UNIVERSAL_RULES}

TASK: Write Section 4 — Reason for Suspicion for a Suspicious Activity Report (SAR).

This is the core section of the SAR. Open with the investigation summary:
"{evidence.get('agent_investigation_summary', '')}"

Then, for EACH triggered rule in the rules_triggered list:
1. State the rule name and cite its exact regulatory basis (e.g. "POCA 2002 s.327" or "FATF Recommendation 19"). After citing the legal section, explain in plain English what it means.
2. Explain specifically how the observed activity maps to that rule, using exact figures from the evidence.
3. If RULE-04 is triggered, explicitly compute and state the income multiple: "transactions totalling £{total_flagged:,.2f} represent {income_multiple}× the subject's declared annual income of £{income:,.2f}"
4. If RULE-07 is triggered, state the specific PEP or sanctions connection verbatim from the evidence.
5. Reference the applicable NCA glossary codes with their plain-English descriptions.
6. Cross-reference specific transaction dates and amounts from Section 3.

The NCA glossary codes and their meanings:
{json.dumps(dict((c, _get_code_desc(c)) for c in evidence.get('nca_glossary_codes', [])), indent=2)}

PREVIOUSLY WRITTEN SECTIONS (for cross-reference):
{_format_prior_sections(written_sections)}

EVIDENCE PACKAGE:
{_format_evidence(evidence)}
"""


# ── Section 5: Exculpatory Analysis ──────────────────────────────────────

def build_section_5_prompt(evidence: dict, written_sections: dict) -> str:
    return f"""{_UNIVERSAL_RULES}

TASK: Write Section 5 — Exculpatory Analysis for a Suspicious Activity Report (SAR).

For EACH entry in the exculpatory_hypotheses list:
- If assessment is "REJECTED": State the innocent explanation that was considered, then explain specifically — using numbers from the evidence — why it was ruled out.
- If assessment is "ACCEPTED": Note this explanation was found credible and explain why, making clear that the evidence supports this innocent explanation.

The tone must be objective and factual. This section demonstrates investigative due diligence — it shows that alternative explanations were properly considered before reaching a conclusion.

Do not repeat transaction details already covered in Sections 3 and 4; instead, cross-reference them briefly.

PREVIOUSLY WRITTEN SECTIONS (for cross-reference):
{_format_prior_sections(written_sections)}

EVIDENCE PACKAGE:
{_format_evidence(evidence)}
"""


# ── Section 6: Conclusion ───────────────────────────────────────────────

def build_section_6_prompt(evidence: dict, written_sections: dict) -> str:
    # Determine POCA offence
    triggered_ids = [r["rule_id"] for r in evidence.get("rules_triggered", [])]
    if "RULE-02" in triggered_ids:
        poca = "s.328 POCA 2002 (entering into an arrangement facilitating the acquisition, retention, use or control of criminal property)"
    elif "RULE-03" in triggered_ids or "RULE-07" in triggered_ids:
        poca = "s.327 POCA 2002 (concealing, disguising, converting, transferring, or removing criminal property from the jurisdiction)"
    else:
        poca = "s.329 POCA 2002 (acquisition, use, or possession of criminal property)"

    total_flagged = evidence.get("total_value_flagged_gbp", 0)

    return f"""{_UNIVERSAL_RULES}

TASK: Write Section 6 — Conclusion for a Suspicious Activity Report (SAR).

Summarise the findings in 3-5 sentences of flowing prose. Then:

1. State the total suspected criminal proceeds: £{total_flagged:,.2f}
2. Identify the most likely POCA offence as: {poca}
   After citing the section number, explain in one sentence what it means in plain English.

3. Then include these two sentences VERBATIM (copy them exactly):
"This disclosure is not a Defence Against Money Laundering (DAML) request; it is submitted as an information SAR only. The subject of this report has not been, and will not be, informed of this disclosure."

4. End the section with this sentence VERBATIM (copy it exactly):
"This report is submitted to the UK Financial Intelligence Unit (UKFIU) in compliance with s.330 Proceeds of Crime Act 2002 (failure to disclose: regulated sector)."

PREVIOUSLY WRITTEN SECTIONS (for cross-reference):
{_format_prior_sections(written_sections)}

EVIDENCE PACKAGE:
{_format_evidence(evidence)}
"""


# ── Helper ───────────────────────────────────────────────────────────────

def _get_code_desc(code: str) -> str:
    """Get plain-English description for an NCA glossary code."""
    from sar.glossary_codes import GLOSSARY_CODE_DESCRIPTIONS
    return GLOSSARY_CODE_DESCRIPTIONS.get(code, code)
