import json
from agent.llm import get_llm
from agent.sar_prompts import SECTION_3_CODE_IDENTIFICATION_PROMPT, SECTION_3_NARRATIVE_PROMPT, XAI_FORMATTING_RULES, SECTION_4_PROFILE_PROMPT

from typing import Any

def _extract_text(content) -> str:
    """Extract plain text from content (handles Groq strings and Gemini list-of-dicts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)

def _sse_event(event_type: str, data: Any) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else json.dumps(data)
    # data is expected to be a dict mostly, except error messages and similar if structured as dicts
    # In api.py it was used like this
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"

async def generate_section_3(verdict: dict, legal_context: dict):
    """
    Two-call pipeline to generate Section 3 of the SAR.
    1. Call 1: Identify Glossary Codes (non-streaming)
    2. Call 2: Generate Narrative (streaming)
    """
    try:
        llm = get_llm()

        # Step 1: Code Identification
        prompt1 = SECTION_3_CODE_IDENTIFICATION_PROMPT.format(
            verdict_json=json.dumps(verdict, indent=2)
        )
        response1_text = ""
        for chunk in llm.stream(prompt1):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                response1_text += text_chunk
                yield _sse_event("debug_token", {"token": text_chunk})
        
        # Parse the JSON out of response1_text (which may have markdown fences)
        if "```json" in response1_text:
            response1_text = response1_text.split("```json")[-1].split("```")[0].strip()
        elif "```" in response1_text:
            response1_text = response1_text.split("```")[-1].split("```")[0].strip()
            
        code_identification = json.loads(response1_text)

        # Yield SSE event for code identification complete
        yield _sse_event("section3_codes_identified", code_identification)

        # Step 2: Narrative Generation
        prompt2 = SECTION_3_NARRATIVE_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2),
            code_identification_json=json.dumps(code_identification, indent=2),
            codes_string=code_identification.get("codes_string", ""),
            ordered_codes=json.dumps(code_identification.get("ordered_codes", [])),
            ctfi_required=str(code_identification.get("ctfi_required", False)).lower(),
            daml_required=str(code_identification.get("daml_required", False)).lower(),
            always_present="\n- ".join(legal_context["always_present"]),
            caselaw=legal_context["caselaw"],
            rule_specific="\n- ".join(legal_context["rule_specific"])
        )

        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 3 NARRATIVE PROMPT ===\n{prompt2}\n========================================\n\n"})

        accumulated_narrative = ""
        for chunk in llm.stream(prompt2):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                accumulated_narrative += text_chunk
                yield _sse_event("token", {
                    "section": "section_3",
                    "token": text_chunk
                })

        # Step 3: Parse the metadata after stream exhaustion
        if "\\n---\\n" in accumulated_narrative:
            metadata_part = accumulated_narrative.split("\\n---\\n")[-1]
        elif "---" in accumulated_narrative:
            metadata_part = accumulated_narrative.split("---")[-1]
        else:
            metadata_part = accumulated_narrative

        if "```json" in metadata_part:
            metadata_part = metadata_part.split("```json")[-1].split("```")[0].strip()
        elif "```" in metadata_part:
            metadata_part = metadata_part.split("```")[-1].split("```")[0].strip()
            
        try:
            section_3_metadata = json.loads(metadata_part)
        except json.JSONDecodeError:
            section_3_metadata = {
                "glossary_codes": code_identification.get("ordered_codes", []),
                "codes_string": code_identification.get("codes_string", ""),
                "ctfi_required": code_identification.get("ctfi_required", False),
                "daml_required": code_identification.get("daml_required", False)
            }
        
        yield _sse_event("section3_done", section_3_metadata)

    except Exception as e:
        yield _sse_event("error", {
            "section": "section_3", 
            "message": str(e)
        })

async def generate_section_4(verdict: dict, legal_context: dict):
    """
    Generates Section 4: Customer and Account Profile.
    Streams tokens via SSE to the frontend.
    """
    try:
        llm = get_llm()
        
        # Format the prompt, injecting ONLY the always_present legal context
        prompt = SECTION_4_PROFILE_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2),
            always_present="\n- ".join(legal_context.get("always_present", []))
        )

        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 4 PROFILE PROMPT ===\n{prompt}\n======================================\n\n"})

        # Signal frontend to start streaming this section
        yield _sse_event("section_start", "section_4")

        accumulated_text = ""
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                accumulated_text += text_chunk
                yield _sse_event("token", {
                    "section": "section_4",
                    "token": text_chunk
                })
        
        # Signal frontend that the stream is complete
        yield _sse_event("section_done", "section_4")

    except Exception as e:
        yield _sse_event("error", {
            "section": "section_4", 
            "message": str(e)
        })
