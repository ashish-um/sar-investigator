"""
SAR narrative generator.

Takes a validated EvidencePackage and generates a complete NCA-compliant
SAR narrative through 6 sequential LLM calls — one per SAR section.
Provides both async streaming (for FastAPI) and sync (for CLI) interfaces.
"""

import json
import os
import logging
from datetime import datetime
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from evidence.schema import EvidencePackage
from sar.schema import SARDocument
from sar.prompts import (
    build_section_1_prompt,
    build_section_2_prompt,
    build_section_3_prompt,
    build_section_4_prompt,
    build_section_5_prompt,
    build_section_6_prompt,
)

logger = logging.getLogger(__name__)

# Section definitions: (display_name, prompt_builder, field_name)
SECTIONS = [
    ("Subject Identity",       build_section_1_prompt, "section_1_subject_identity"),
    ("Account Overview",       build_section_2_prompt, "section_2_account_overview"),
    ("Transaction Chronology", build_section_3_prompt, "section_3_transaction_chronology"),
    ("Reason for Suspicion",   build_section_4_prompt, "section_4_reason_for_suspicion"),
    ("Exculpatory Analysis",   build_section_5_prompt, "section_5_exculpatory_analysis"),
    ("Conclusion",             build_section_6_prompt, "section_6_conclusion"),
]


def _get_llm():
    """Get an LLM instance using the project's existing factory."""
    from agent.llm import get_llm
    return get_llm()


def _determine_poca_offence(evidence: EvidencePackage) -> str:
    """Determine the applicable POCA offence section from triggered rules."""
    triggered_ids = [r.rule_id for r in evidence.rules_triggered]
    if "RULE-02" in triggered_ids:
        return "s.328 POCA 2002 (entering into an arrangement facilitating the acquisition, retention, use or control of criminal property)"
    elif "RULE-03" in triggered_ids or "RULE-07" in triggered_ids:
        return "s.327 POCA 2002 (concealing, disguising, converting, transferring, or removing criminal property from the jurisdiction)"
    else:
        return "s.329 POCA 2002 (acquisition, use, or possession of criminal property)"


def _build_sar_document(
    evidence: EvidencePackage,
    written_sections: dict,
    poca_offence: str,
) -> SARDocument:
    """Assemble the final SARDocument from generated sections."""
    return SARDocument(
        sar_draft_id=f"SAR-DRAFT-{evidence.investigation_id}",
        investigation_id=evidence.investigation_id,
        customer_id=evidence.customer_id,
        generated_at=datetime.utcnow().isoformat(),
        nca_glossary_codes=evidence.nca_glossary_codes,
        **written_sections,
        total_suspected_criminal_proceeds_gbp=evidence.total_value_flagged_gbp,
        poca_offence_section=poca_offence,
        status="DRAFT",
    )


def _save_sar(sar: SARDocument, evidence: EvidencePackage) -> tuple[str, str]:
    """Save SAR document as JSON and plain text. Returns (json_path, txt_path)."""
    os.makedirs("output/sar", exist_ok=True)

    json_path = f"output/sar/{evidence.investigation_id}_draft.json"
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(sar.model_dump_json(indent=2))

    txt_path = f"output/sar/{evidence.investigation_id}_draft.txt"
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
    with open(txt_path, "w", encoding="utf-8") as f:
        for i, (name, field) in enumerate(zip(section_names, section_fields), 1):
            text = getattr(sar, field, "")
            f.write(f"=== SECTION {i}: {name.upper()} ===\n\n{text}\n\n")

    return json_path, txt_path


def _cleanup_partial_output(investigation_id: str):
    """Remove partially saved output files on failure."""
    for path in [
        f"output/sar/{investigation_id}_draft.json",
        f"output/sar/{investigation_id}_draft.txt",
    ]:
        if os.path.exists(path):
            os.remove(path)


# ── Async streaming generator (for FastAPI endpoint) ─────────────────────

async def generate_sar_stream(evidence: EvidencePackage) -> AsyncGenerator[str, None]:
    """
    Async generator that yields JSON event strings as SAR sections are
    generated. The FastAPI endpoint wraps each in SSE format.
    """
    llm = _get_llm()
    written_sections: dict[str, str] = {}
    evidence_dict = evidence.model_dump()
    poca_offence = _determine_poca_offence(evidence)

    for i, (display_name, prompt_fn, field_name) in enumerate(SECTIONS, 1):
        # Signal section start
        yield json.dumps({"type": "section_start", "section": display_name, "index": i})

        prompt = prompt_fn(evidence_dict, written_sections)

        # Call LLM with one retry
        section_text = None
        last_error = None
        for attempt in range(2):
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                section_text = response.content
                break
            except Exception as e:
                last_error = e
                logger.warning(
                    f"LLM call failed for {display_name} (attempt {attempt + 1}): {e}"
                )

        if section_text is None:
            _cleanup_partial_output(evidence.investigation_id)
            yield json.dumps({
                "type": "error",
                "section": display_name,
                "message": f"LLM generation failed after 2 attempts: {str(last_error)}",
            })
            return

        written_sections[field_name] = section_text

        # Signal section complete
        yield json.dumps({
            "type": "section_complete",
            "section": display_name,
            "field": field_name,
            "content": section_text,
            "index": i,
            "char_count": len(section_text),
        })

    # Build and save the final document
    sar = _build_sar_document(evidence, written_sections, poca_offence)
    json_path, txt_path = _save_sar(sar, evidence)

    yield json.dumps({
        "type": "complete",
        "sar_draft_id": sar.sar_draft_id,
        "json_path": json_path,
        "txt_path": txt_path,
        "total_suspected_criminal_proceeds_gbp": sar.total_suspected_criminal_proceeds_gbp,
        "poca_offence_section": sar.poca_offence_section,
    })


# ── Synchronous generator (for CLI / pipeline testing) ───────────────────

def generate_sar_sync(evidence: EvidencePackage) -> SARDocument:
    """
    Synchronous SAR generation — runs the same logic as the async
    generator but blocks and prints progress to stdout.
    """
    llm = _get_llm()
    written_sections: dict[str, str] = {}
    evidence_dict = evidence.model_dump()
    poca_offence = _determine_poca_offence(evidence)

    for i, (display_name, prompt_fn, field_name) in enumerate(SECTIONS, 1):
        print(f"[Section {i}/6] Generating: {display_name}...", flush=True)
        prompt = prompt_fn(evidence_dict, written_sections)

        # Call LLM with one retry
        section_text = None
        last_error = None
        for attempt in range(2):
            try:
                response = llm.invoke([HumanMessage(content=prompt)])
                section_text = response.content
                break
            except Exception as e:
                last_error = e
                print(f"  ⚠ Attempt {attempt + 1} failed: {e}", flush=True)

        if section_text is None:
            _cleanup_partial_output(evidence.investigation_id)
            raise RuntimeError(
                f"LLM generation failed for {display_name} after 2 attempts: {last_error}"
            )

        written_sections[field_name] = section_text
        print(f"  ✓ {display_name} — {len(section_text)} chars", flush=True)

    sar = _build_sar_document(evidence, written_sections, poca_offence)
    json_path, txt_path = _save_sar(sar, evidence)
    print(f"\nSaved: {json_path}")
    print(f"Saved: {txt_path}")

    return sar
