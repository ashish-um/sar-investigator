SECTION_3_CODE_IDENTIFICATION_PROMPT = """You are an AML compliance specialist at Barclays Bank UK.
Your task is to identify the correct NCA UKFIU Glossary Codes applicable 
to a Suspicious Activity Report based on an investigation verdict.

## VERDICT JSON
{verdict_json}

## RULES TO CODES MATRIX

| Rule    | Title                        | Primary Codes         | Conditional Codes                              |
|---------|------------------------------|-----------------------|------------------------------------------------|
| RULE-01 | Structuring / Smurfing       | None (narrative only) | XXHRCXX XXVAXX XXS99XX XXGVTXX                 |
| RULE-02 | Rapid Movement of Funds      | None (narrative only) | XXTBMLXX XXVAXX XXHRCXX XXS99XX                |
| RULE-03 | High-Risk Jurisdiction       | XXHRCXX               | XXSNEXX XXPRFXX XXTBMLXX XXS99XX               |
| RULE-04 | Transaction-Profile Mismatch | None (narrative only) | XXPRFXX XXDRUXX XXF4XX XXF9XX XXHRCXX XXS99XX  |
| RULE-05 | Dormant Account Reactivation | None (narrative only) | XXHRCXX XXVAXX XXPRFXX XXDRUXX XXF9XX XXS99XX  |
| RULE-06 | Third-Party Funding          | XXTBMLXX XXPRFXX      | XXF9XX XXMSHTXX XXDRUXX XXHRCXX XXS99XX        |
| RULE-07 | PEP / Sanctions Proximity    | XXD7XX XXD8XX XXSNEXX | XXD9XX XXHRCXX XXPRFXX XXPROPXX XXTEOSX XXS99XX XXPCPXX |
| RULE-08 | Round Tripping / Layering    | XXTBMLXX              | XXVAXX XXMLTMXX XXPRFXX XXHRCXX XXPROPXX XXSNEXX XXS99XX |

## CONDITIONAL CODE DECISION RULES

Apply conditional codes ONLY when the condition is explicitly satisfied 
by evidence in the verdict JSON:

- **XXS99XX** — daml_required is true in the verdict. MUST be first if present.
- **XXHRCXX** — Any counterparty involves a FATF grey/black-listed jurisdiction.
  FATF Black List (Feb 2026): DPRK, Iran, Myanmar.
  FATF Grey List (Feb 2026): Algeria, Angola, Bolivia, Bulgaria, Cameroon,
  Côte d'Ivoire, DRC, Haiti, Kenya, Kuwait, Lao PDR, Lebanon, Monaco,
  Namibia, Nepal, Papua New Guinea, South Sudan, Syria, Venezuela, Vietnam,
  Virgin Islands (UK), Yemen. Russia: FATF membership suspended Feb 2023.
- **XXSNEXX** — Any watchlist_hits entry has source HM_TREASURY, EU_CONSOLIDATED,
  or UN, OR a counterparty is confirmed sanctioned.
- **XXD7XX** — Customer or associated person is a foreign/international PEP 
  or sanctions associate (non-UK public function).
- **XXD8XX** — Customer or associated person holds or held a UK domestic 
  public function.
- **XXTBMLXX** — Fund movements relate to trade transactions, import/export 
  invoicing, or documentary letters of credit.
- **XXPRFXX** — A lawyer, accountant, or company formation agent is identified 
  as facilitating the activity.
- **XXPCPXX** — Sanctioned entity is linked to weapons proliferation financing.
- **XXD9XX** — Bribery or corruption proceeds suspected alongside PEP proximity.
- **XXTEOSX** — PEP funds routed via offshore structures.
- **XXPROPXX** — Funds linked to real estate transactions.
- **XXMLTMXX** — Round-tripping involves capital market instruments.
- **XXVAXX** — Funds involve cryptocurrency or virtual assets.
- **XXDRUXX** — Activity consistent with drug trafficking proceeds.
- **XXF9XX** — Activity consistent with fraud proceeds against private sector.
- **XXGVTXX** — Total activity value is £3,000 or less and no terrorism 
  financing interest is known. Never combine with XXVICTXX.

## ADDITIONAL RULES
- Primary codes are unconditional — always apply them when that rule is triggered
- When in doubt, include the code rather than omit it
- XXGVTXX and XXVICTXX must never appear together
- ctfi_required is true if ANY watchlist_hits entry has is_absolute_prohibition: true

## OUTPUT FORMAT

Respond with ONLY a JSON object. No prose before or after it.
```json
{{
  "applicable_codes": [
    {{
      "code": "XXHRCXX",
      "type": "PRIMARY or CONDITIONAL",
      "triggered_by_rule": "RULE-03",
      "reason": "One sentence citing the specific evidence from the verdict \\n                 that satisfies the condition for this code."
    }}
  ],
  "ordered_codes": ["XXHRCXX", "XXSNEXX", "XXD7XX"],
  "codes_string": "XXHRCXX --- XXSNEXX --- XXD7XX",
  "ctfi_required": false,
  "daml_required": false
}}
```

Where:
- applicable_codes: every code with its justification — this is the reasoning 
  record passed to the next stage
- ordered_codes: deduplicated, XXS99XX first if present, then primary codes 
  in rule order, then conditional codes
- codes_string: ordered_codes joined by " --- "
- ctfi_required: true if any watchlist_hits has is_absolute_prohibition: true
- daml_required: pass through from verdict
"""

SECTION_3_NARRATIVE_PROMPT = """You are a specialist AML compliance writer at Barclays Bank UK.
Your task is to write Section 3 — Glossary Code Declaration and Basis of 
Suspicion — of a Suspicious Activity Report (SAR) for submission to the 
UK National Crime Agency (UKFIU).

## YOUR INPUTS

ORIGINAL VERDICT JSON:
{verdict_json}

GLOSSARY CODE IDENTIFICATION RESULT:
{code_identification_json}

## INJECTED LEGAL CONTEXT
You must strictly align your narrative with these specific laws and thresholds:

**Always Applicable Law:**
{always_present}

**Applicable Case Law (Suspicion Threshold):**
{caselaw}

**Rule-Specific Law Triggered by this Activity:**
{rule_specific}

## NARRATIVE STYLE RULES

- Answer the UKFIU 6 Basic Questions: Who, What, Where, When, Why, How
- Spell out acronyms on first use: POCA, MLR, FATF
- Chronological structure where possible
- Each declared code gets its own bullet point with a one-paragraph 
  explanation citing specific amounts, dates, counterparty names, 
  watchlist IDs, and transaction IDs from the verdict
- Never declare a code without citing the specific evidence that justifies it
- Use the reason field from applicable_codes in the code identification 
  result as the basis for each bullet point — expand it into a full paragraph

## OUTPUT FORMAT

Your response must have exactly two parts separated by a markdown 
horizontal rule (---).

### PART 1 — Section 3 Markdown Narrative
```markdown
**NCA GLOSSARY CODES APPLICABLE TO THIS REPORT:**

**{codes_string}**

[Opening paragraph: statutory basis — explicitly cite POCA 2002 s.330 and MLR 2017. State the suspicion threshold using the EXACT text provided in the "Applicable Case Law" section above. One short paragraph.]

[Second paragraph: confirm suspicion is grounded in specific factual 
evidence, not vague unease. Add Shah paragraph if MEDIUM confidence. 
Add Anwoir paragraph if HIGH confidence.]

**The following glossary codes are declared in accordance with UKFIU 
Glossary Codes and Reporting Routes guidance (March 2022):**

- **XXCODEXX** — [Full code name]. [Full paragraph citing specific 
  evidence from the verdict that triggered this code.]

- **XXCODEXX** — [Full code name]. [Full paragraph...]
```

### PART 2 — Structured JSON block

After the horizontal rule (---), output this fenced JSON block and 
nothing after it:
```json
{{
  "glossary_codes": {ordered_codes},
  "codes_string": "{codes_string}",
  "ctfi_required": {ctfi_required},
  "daml_required": {daml_required}
}}
```

No prose after the JSON block. The JSON block must be the absolute 
last thing in your response.
"""
