from agent.legal_library.poca_snippets import ALWAYS_PRESENT_SNIPPETS
from agent.legal_library.caselaw_snippets import CASELAW_SNIPPETS
from agent.legal_library.sanctions_snippets import SANCTIONS_SNIPPETS
from agent.config_manager import config

def build_legal_context(verdict: dict) -> dict:
    always_present = list(ALWAYS_PRESENT_SNIPPETS)
    rule_specific = []
    
    # 1. Map Rule-Specific Law
    dynamic_snippets = config.legal_snippets.get("rule_specific_snippets", {})
    for rule in verdict.get("rules_triggered", []):
        if rule in dynamic_snippets:
            rule_specific.extend(dynamic_snippets[rule])
    
    
    # 2. Map Caselaw / Suspicion Threshold
    confidence = verdict.get("confidence", "LOW").upper()
    caselaw = CASELAW_SNIPPETS.get(confidence, CASELAW_SNIPPETS["LOW"])
    
    # 3. Map Sanctions / Watchlist Specific Law
    sanctions_specific = []
    for evidence in verdict.get("key_evidence", []):
        for hit in evidence.get("supporting_data", {}).get("watchlist_hits", []):
            source = hit.get("source")
            if source in SANCTIONS_SNIPPETS and SANCTIONS_SNIPPETS[source] not in sanctions_specific:
                sanctions_specific.append(SANCTIONS_SNIPPETS[source])

    # 4. DAML Conditional Injection
    # If a DAML is required, the LLM must cite the specific POCA section for appropriate consent
    daml_required = verdict.get("daml_required", False)
    if daml_required:
        rule_specific.append("POCA 2002 s.335: Appropriate consent (Defence Against Money Laundering - DAML) is required from the NCA before undertaking a prohibited act.")

    return {
        "always_present": list(dict.fromkeys(always_present)), # Deduplicate
        "rule_specific": list(dict.fromkeys(rule_specific)),   # Deduplicate
        "caselaw": caselaw,
        "sanctions_specific": sanctions_specific,
        "graduated_language": confidence,
        "daml_required": daml_required
    }
