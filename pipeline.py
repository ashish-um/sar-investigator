"""
CLI pipeline for Evidence + SAR generation.

Usage:
    python pipeline.py <alert_json_path> <verdict_json_path>

Loads both JSON files, builds an EvidencePackage, then generates
a complete SAR draft via sequential LLM calls.
"""

import json
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 3:
        print("Usage: python pipeline.py <alert.json> <verdict.json>")
        print("  alert.json   — the alert payload that started the investigation")
        print("  verdict.json — the agent's final verdict output")
        sys.exit(1)

    alert_path = sys.argv[1]
    verdict_path = sys.argv[2]

    # Load inputs
    with open(alert_path, "r", encoding="utf-8") as f:
        alert = json.load(f)
    print(f"✓ Loaded alert: {alert_path}")

    with open(verdict_path, "r", encoding="utf-8") as f:
        verdict = json.load(f)
    print(f"✓ Loaded verdict: {verdict_path}")
    print(f"  Verdict: {verdict.get('verdict', '?')} | Confidence: {verdict.get('confidence', '?')}")
    print(f"  Rules triggered: {verdict.get('rules_triggered', [])}")

    # Build Evidence Package
    print("\n" + "=" * 60)
    print("BUILDING EVIDENCE PACKAGE")
    print("=" * 60)

    from evidence.builder import build_evidence_package
    evidence = build_evidence_package(verdict, alert)
    print(f"\n✓ Evidence package built: {evidence.investigation_id}")
    print(f"  Customer: {evidence.subject.full_name} ({evidence.customer_id})")
    print(f"  Accounts examined: {len(evidence.accounts_examined)}")
    print(f"  Transactions reviewed: {evidence.total_transactions_reviewed}")
    print(f"  Total flagged value: £{evidence.total_value_flagged_gbp:,.2f}")
    print(f"  Glossary codes: {evidence.nca_glossary_codes}")
    print(f"  Evidence saved to: output/evidence/{evidence.investigation_id}.json")

    # Check for FALSE_POSITIVE
    if evidence.agent_verdict == "FALSE_POSITIVE":
        print("\n✓ Verdict is FALSE_POSITIVE — no SAR generated.")
        print("  Evidence package saved for audit purposes.")
        return

    # Generate SAR
    print("\n" + "=" * 60)
    print("GENERATING SAR DRAFT")
    print("=" * 60 + "\n")

    from sar.generator import generate_sar_sync
    sar = generate_sar_sync(evidence)

    # Print the full SAR
    print("\n" + "=" * 60)
    print("SAR DRAFT — PLAIN TEXT")
    print("=" * 60)

    section_names = [
        "Subject Identity",
        "Account Overview",
        "Transaction Chronology",
        "Reason for Suspicion",
        "Exculpatory Analysis",
        "Conclusion",
    ]
    section_fields = [
        "section_1_subject_identity",
        "section_2_account_overview",
        "section_3_transaction_chronology",
        "section_4_reason_for_suspicion",
        "section_5_exculpatory_analysis",
        "section_6_conclusion",
    ]
    for i, (name, field) in enumerate(zip(section_names, section_fields), 1):
        text = getattr(sar, field, "")
        print(f"\n=== SECTION {i}: {name.upper()} ===\n")
        print(text)
        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  SAR Draft ID: {sar.sar_draft_id}")
    print(f"  POCA Offence: {sar.poca_offence_section}")
    print(f"  Criminal Proceeds: £{sar.total_suspected_criminal_proceeds_gbp:,.2f}")
    print(f"  Status: {sar.status}")
    print(f"  JSON: output/sar/{evidence.investigation_id}_draft.json")
    print(f"  Text: output/sar/{evidence.investigation_id}_draft.txt")


if __name__ == "__main__":
    main()
