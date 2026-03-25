"""
NCA UKFIU Glossary Code mappings.

Maps internal AML rule IDs to the applicable NCA glossary codes
and provides plain-English descriptions for SAR narrative use.
"""

RULE_TO_GLOSSARY_CODES: dict[str, list[str]] = {
    "RULE-01": ["XXMLTF", "XXSS"],       # Structuring / Smurfing
    "RULE-02": ["XXMLTF", "XXLAY"],      # Rapid Movement of Funds
    "RULE-03": ["XXHRCJ"],               # High-Risk Jurisdiction Transfer
    "RULE-04": ["XXMLTF"],               # Transaction-Profile Mismatch
    "RULE-05": ["XXMLTF"],               # Dormant Account Reactivation
    "RULE-06": ["XXMLTF", "XXSS"],       # Third-Party Funding
    "RULE-07": ["XXPEP", "XXSAN"],       # PEP / Sanctions Proximity
    "RULE-08": ["XXLAY"],                # Round Tripping / Layering
}

GLOSSARY_CODE_DESCRIPTIONS: dict[str, str] = {
    "XXMLTF": "Money Laundering / Terrorism Financing",
    "XXSS":   "Suspected Structuring (Smurfing)",
    "XXLAY":  "Suspected Layering of Criminal Funds",
    "XXHRCJ": "Transaction Involving High-Risk Country or Jurisdiction",
    "XXPEP":  "Politically Exposed Person",
    "XXSAN":  "Sanctions-Related Activity",
}
