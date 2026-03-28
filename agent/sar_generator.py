import json
import datetime
import asyncio
from agent.llm import get_llm
from tools.internal.get_customer_profile import get_customer_profile
from agent.sar_prompts import SECTION_1_TEMPLATE, SECTION_2_TEMPLATE, SECTION_3_CODE_IDENTIFICATION_PROMPT, SECTION_3_NARRATIVE_PROMPT, XAI_FORMATTING_RULES, SECTION_4_PROFILE_PROMPT, SECTION_5_CHRONOLOGY_PROMPT, SECTION_6_RULE_ANALYSIS_PROMPT, SECTION_6_STATUTORY_PROMPT, SECTION_7_WATCHLIST_PROMPT, SECTION_8_STATISTICS_PROMPT, SECTION_9_HYPOTHESIS_PROMPT, SECTION_10_HISTORY_PROMPT, SECTION_11_DAML_PROMPT
from agent.config_manager import config

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
            verdict_json=json.dumps(verdict, indent=2),
            rules_to_codes_matrix=config.format_matrix_for_prompt(),
            conditional_code_decision_rules=config.format_conditional_rules_for_prompt()
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

async def generate_section_5(verdict: dict, legal_context: dict = None):
    """
    Generates Section 5: Chronological Description of Suspicious Activity.
    Streams tokens via SSE to the frontend.
    """
    try:
        llm = get_llm()
        
        # Format the prompt. We do not need to inject legal_context here, 
        # but we keep the parameter for architectural consistency.
        prompt = SECTION_5_CHRONOLOGY_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2)
        )

        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 5 CHRONOLOGY PROMPT ===\n{prompt}\n=========================================\n\n"})

        # Signal frontend to start streaming this section
        yield _sse_event("section_start", "section_5")

        accumulated_text = ""
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                accumulated_text += text_chunk
                yield _sse_event("token", {
                    "section": "section_5",
                    "token": text_chunk
                })
        
        # Signal frontend that the stream is complete
        yield _sse_event("section_done", "section_5")

    except Exception as e:
        yield _sse_event("error", {
            "section": "section_5", 
            "message": str(e)
        })

async def generate_section_6(verdict: dict, legal_context: dict):
    """
    Generates Section 6 using a looping architecture to ensure legal precision.
    """
    try:
        llm = get_llm()
        yield _sse_event("section_start", "section_6")
        
        # Output the main Section Header first
        yield _sse_event("token", {"section": "section_6", "token": "**SECTION 6 — REGULATORY BASIS AND LEGAL ANALYSIS**\n\n"})

        triggered_rules = verdict.get("rules_triggered", [])
        key_evidence = verdict.get("key_evidence", [])
        
        # Combine rule-specific laws and sanctions laws for the LLM to select from
        available_laws = legal_context.get("rule_specific", []) + legal_context.get("sanctions_specific", [])
        laws_string = "\n- ".join(available_laws)

        subsection_index = 1

        # --- LOOP 1: Analyze Each Triggered Rule ---
        for rule_id in triggered_rules:
            # Find the specific evidence block for this rule
            evidence_block = next((e for e in key_evidence if e.get("rule_mapped") == rule_id), None)
            if not evidence_block:
                continue

            heading = f"6.{subsection_index} {rule_id} Analysis"
            
            prompt = SECTION_6_RULE_ANALYSIS_PROMPT.format(
                xai_formatting_rules=XAI_FORMATTING_RULES,
                subsection_heading=heading,
                rule_evidence_json=json.dumps(evidence_block, indent=2),
                legal_context_laws=laws_string
            )

            # Surface prompt to Agent Raw Reasoning
            yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 6 {rule_id} ANALYSIS PROMPT ===\n{prompt}\n=========================================\n\n"})

            for chunk in llm.stream(prompt):
                text_chunk = _extract_text(getattr(chunk, "content", ""))
                if text_chunk:
                    yield _sse_event("token", {"section": "section_6", "token": text_chunk})
            
            # Add spacing between subsections
            yield _sse_event("token", {"section": "section_6", "token": "\n\n"})
            subsection_index += 1

        # --- FINAL CALL: Statutory Reporting Obligation ---
        statutory_heading_num = f"6.{subsection_index}"
        statutory_prompt = SECTION_6_STATUTORY_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            subsection_number=statutory_heading_num,
            always_present="\n- ".join(legal_context.get("always_present", [])),
            caselaw=legal_context.get("caselaw", ""),
            daml_required=str(legal_context.get("daml_required", False)).upper()
        )

        # Surface statutory prompt to Agent Raw Reasoning
        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 6 STATUTORY PROMPT ===\n{statutory_prompt}\n=========================================\n\n"})

        for chunk in llm.stream(statutory_prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                yield _sse_event("token", {"section": "section_6", "token": text_chunk})

        yield _sse_event("section_done", "section_6")

    except Exception as e:
        yield _sse_event("error", {"section": "section_6", "message": str(e)})

async def generate_section_7(verdict: dict, legal_context: dict):
    """
    Generates Section 7: Watchlist Screening Results.
    """
    try:
        llm = get_llm()
        
        # Inject only the sanctions-specific laws to keep the LLM focused
        prompt = SECTION_7_WATCHLIST_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2),
            sanctions_specific="\n- ".join(legal_context.get("sanctions_specific", []))
        )

        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 7 WATCHLIST PROMPT ===\n{prompt}\n=========================================\n\n"})

        yield _sse_event("section_start", "section_7")

        accumulated_text = ""
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                accumulated_text += text_chunk
                yield _sse_event("token", {
                    "section": "section_7",
                    "token": text_chunk
                })
        
        yield _sse_event("section_done", "section_7")

    except Exception as e:
        yield _sse_event("error", {
            "section": "section_7", 
            "message": str(e)
        })

async def generate_section_8(verdict: dict, legal_context: dict = None):
    """
    Generates Section 8: Statistical and Behavioural Analysis.
    """
    try:
        llm = get_llm()
        
        prompt = SECTION_8_STATISTICS_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2)
        )

        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 8 STATISTICS PROMPT ===\n{prompt}\n=========================================\n\n"})

        yield _sse_event("section_start", "section_8")

        accumulated_text = ""
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                accumulated_text += text_chunk
                yield _sse_event("token", {
                    "section": "section_8",
                    "token": text_chunk
                })
        
        yield _sse_event("section_done", "section_8")

    except Exception as e:
        yield _sse_event("error", {
            "section": "section_8", 
            "message": str(e)
        })

async def generate_section_9(verdict: dict, legal_context: dict):
    """
    Generates Section 9: Innocent Explanations Considered and Assessed.
    """
    try:
        llm = get_llm()
        
        prompt = SECTION_9_HYPOTHESIS_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2),
            caselaw=legal_context.get("caselaw", "R v Da Silva [2006] EWCA Crim 1654")
        )

        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 9 HYPOTHESIS PROMPT ===\n{prompt}\n=========================================\n\n"})

        yield _sse_event("section_start", "section_9")

        accumulated_text = ""
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                accumulated_text += text_chunk
                yield _sse_event("token", {
                    "section": "section_9",
                    "token": text_chunk
                })
        
        yield _sse_event("section_done", "section_9")

    except Exception as e:
        yield _sse_event("error", {
            "section": "section_9", 
            "message": str(e)
        })

async def generate_section_10(verdict: dict, legal_context: dict = None):
    try:
        llm = get_llm()
        prompt = SECTION_10_HISTORY_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2)
        )
        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 10 HISTORY PROMPT ===\n{prompt}\n=========================================\n\n"})
        yield _sse_event("section_start", "section_10")
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                yield _sse_event("token", {"section": "section_10", "token": text_chunk})
        yield _sse_event("section_done", "section_10")
    except Exception as e:
        yield _sse_event("error", {"section": "section_10", "message": str(e)})

async def generate_section_11(verdict: dict, legal_context: dict = None):
    try:
        llm = get_llm()
        prompt = SECTION_11_DAML_PROMPT.format(
            xai_formatting_rules=XAI_FORMATTING_RULES,
            verdict_json=json.dumps(verdict, indent=2)
        )
        yield _sse_event("debug_token", {"token": f"\n\n\n=== FINAL SECTION 11 DAML PROMPT ===\n{prompt}\n======================================\n\n"})
        yield _sse_event("section_start", "section_11")
        for chunk in llm.stream(prompt):
            text_chunk = _extract_text(getattr(chunk, "content", ""))
            if text_chunk:
                yield _sse_event("token", {"section": "section_11", "token": text_chunk})
        yield _sse_event("section_done", "section_11")
    except Exception as e:
        yield _sse_event("error", {"section": "section_11", "message": str(e)})

async def generate_section_1(verdict: dict, legal_context: dict = None):
    """Deterministically generates Section 1 using pure Python formatting."""
    try:
        yield _sse_event("section_start", "section_1")
        
        daml_req = "Yes" if verdict.get("daml_required") else "No"
        prior_sar = "None on record" if verdict.get("duplicate_sar_safe") else "Prior SAR exists - see internal records"
        
        markdown_text = SECTION_1_TEMPLATE.format(
            sar_reference=f"SAR-{datetime.datetime.now().strftime('%Y-%m')}-{verdict.get('customer_id', 'UNKNOWN')[-6:]}",
            date_of_report=datetime.datetime.now().strftime("%d %B %Y"),
            total_value="See Section 8",
            daml_required=daml_req,
            prior_sar=prior_sar
        )

        # Yield in chunks to simulate streaming for the UI
        for word in markdown_text.split(" "):
            yield _sse_event("token", {"section": "section_1", "token": word + " "})
            await asyncio.sleep(0.01) # Tiny sleep to let the frontend breathe
            
        yield _sse_event("section_done", "section_1")
    except Exception as e:
        yield _sse_event("error", {"section": "section_1", "message": str(e)})

async def generate_section_2(verdict: dict, legal_context: dict = None):
    """Deterministically generates Section 2 using pure Python formatting and the customer profile tool."""
    try:
        yield _sse_event("section_start", "section_2")
        
        customer_id = verdict.get("customer_id", "UNKNOWN")
        
        # 1. Fetch the profile data dynamically using the tool
        profile = {}
        if customer_id != "UNKNOWN":
            try:
                # Assuming the tool returns a JSON string, parse it into a dict
                profile_raw = get_customer_profile.invoke({"customer_id": customer_id})
                profile = json.loads(profile_raw) if isinstance(profile_raw, str) else profile_raw
            except Exception as e:
                print(f"Error fetching customer profile: {e}")

        # 2. Extract Account Number from the verdict's key_evidence
        accounts_involved = set()
        for evidence in verdict.get("key_evidence", []):
            for acc in evidence.get("supporting_data", {}).get("accounts_involved", []):
                accounts_involved.add(acc)
        account_number = ", ".join(accounts_involved) if accounts_involved else "UNKNOWN"

        # 3. Safely map the specific tool output fields
        occupation_str = f"{profile.get('occupation', 'UNKNOWN')} / {profile.get('employer_name', 'UNKNOWN')}"
        income_val = profile.get("annual_income_declared_gbp", "UNKNOWN")
        income_str = f"£{income_val:,.2f} (Source: {profile.get('source_of_funds_declared', 'UNKNOWN')})" if isinstance(income_val, (int, float)) else str(income_val)

        markdown_text = SECTION_2_TEMPLATE.format(
            full_name=profile.get("full_name", "UNKNOWN"),
            customer_id=customer_id,
            dob=profile.get("date_of_birth", "UNKNOWN"),
            nationality=profile.get("nationality", "UNKNOWN"),
            residence=profile.get("country_of_residence", "UNKNOWN"),
            occupation=occupation_str,
            income=income_str,
            onboarding_date=profile.get("onboarding_date", "UNKNOWN"),
            kyc_status=profile.get("kyc_status", "UNKNOWN"),
            risk_rating=profile.get("risk_rating", "UNKNOWN"),
            pep_flag="True" if profile.get("pep_flag") == 1 else "False",
            sanctions_flag="True" if profile.get("sanctions_flag") == 1 else "False",
            account_number=account_number,
            account_type="Personal Current Account" # Default or fetch from get_account_summary if needed
        )

        # Yield in chunks
        for word in markdown_text.split(" "):
            yield _sse_event("token", {"section": "section_2", "token": word + " "})
            await asyncio.sleep(0.01)
            
        yield _sse_event("section_done", "section_2")
    except Exception as e:
        yield _sse_event("error", {"section": "section_2", "message": str(e)})
