"""
FastAPI SSE endpoint for the AML Investigation Agent.

Provides a POST /investigate endpoint that accepts an AlertPayload JSON body
and returns a Server-Sent Events stream with real-time investigation output.

Run with:  uvicorn api:app --reload
"""

import json
import os
import re
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from langchain_core.messages import SystemMessage, HumanMessage, AIMessageChunk

from schemas.alert import AlertPayload
from agent.prompts import build_system_prompt
from agent.graph import graph, drain_rate_limit_events, clear_rate_limit_events
from agent.llm import get_llm_config
from agent.sar_generator import generate_section_1, generate_section_2, generate_section_3, generate_section_4, generate_section_5, generate_section_6, generate_section_7, generate_section_8, generate_section_9, generate_section_10, generate_section_11
from agent.legal_context_builder import build_legal_context
from agent.config_manager import config

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(
    title="AML SAR Investigator API",
    description="Real-time AML investigation via Server-Sent Events",
    version="1.0.0",
)

# Add CORS middleware to allow the frontend to access the API when testing locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Jinja2 templates for serving the frontend
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(_BASE_DIR, "templates"))


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


from typing import Any

def _sse_event(event_type: str, data: Any) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"


def _stream_investigation(alert: AlertPayload):
    """Generator that yields SSE events as the investigation progresses."""

    alert_dict = alert.model_dump()
    human_content = (
        f"ALERT RECEIVED:\n"
        f"{json.dumps(alert_dict, indent=2)}\n\n"
        f"Begin your investigation. Start by forming a hypothesis, then use "
        f"the available tools to gather evidence. "
        f"The customer under investigation is: {alert.customer_id}"
    )

    dynamic_prompt = build_system_prompt(alert_dict)

    initial_state = {
        "messages": [
            SystemMessage(content=dynamic_prompt),
            HumanMessage(content=human_content),
        ],
        "alert": alert_dict,
        "customer_id": alert.customer_id,
        "verdict": None,
    }

    final_content = ""
    current_node = None
    ai_message_index = 0
    tool_message_index = 0
    tool_call_buffer = {}

    # Clear any stale rate-limit events from previous runs
    clear_rate_limit_events()

    try:
        # Emit the dynamically built system prompt to the frontend so it can be logged
        yield _sse_event("system_prompt", {"content": dynamic_prompt})

        for chunk, metadata in graph.stream(
            initial_state,
            stream_mode="messages"
        ):
            node = metadata.get("langgraph_node")

            # ── node transition ──────────────────────────────────
            if node != current_node:
                current_node = node
                if node == "agent":
                    ai_message_index += 1
                elif node == "tools":
                    tool_message_index += 1

            # ── AI content (reasoning tokens) ────────────────────
            if isinstance(chunk, AIMessageChunk):

                if chunk.content:
                    text = _extract_text(chunk.content)
                    if text:
                        final_content += text
                        yield _sse_event("thinking", {
                            "content": text,
                            "step": ai_message_index,
                        })

                # ── Tool call accumulation ────────────────────────
                if chunk.tool_call_chunks:
                    for tc in chunk.tool_call_chunks:
                        call_id = tc.get("id") or tc.get("index", 0)
                        if call_id not in tool_call_buffer:
                            tool_call_buffer[call_id] = {"name": "", "args": ""}
                        if tc.get("name"):
                            tool_call_buffer[call_id]["name"] += tc["name"]
                        if tc.get("args"):
                            tool_call_buffer[call_id]["args"] += tc["args"]

                    # Emit completed tool calls
                    for call_id, tc in list(tool_call_buffer.items()):
                        if tc["args"].strip().endswith("}"):
                            yield _sse_event("tool_call", {
                                "tool": tc["name"],
                                "arguments": json.loads(tc["args"]),
                                "step": ai_message_index,
                            })
                            del tool_call_buffer[call_id]

            # ── Tool results ─────────────────────────────────────
            else:
                content = _extract_text(chunk.content) if hasattr(chunk, "content") else str(chunk)
                if content.strip():
                    tool_message_index_current = tool_message_index
                    # Try to parse as JSON for structured output
                    try:
                        result_data = json.loads(content)
                    except (json.JSONDecodeError, TypeError):
                        result_data = content

                    yield _sse_event("tool_result", {
                        "result": result_data,
                        "step": tool_message_index_current,
                    })

            # ── Emit any pending rate-limit events ────────────────
            for rl_event in drain_rate_limit_events():
                yield _sse_event("rate_limit", rl_event)

        # ── Extract and emit final verdict ────────────────────────
        try:
            json_match = re.search(r'\{.*\}', final_content, re.DOTALL)
            if json_match:
                verdict = json.loads(json_match.group())
                yield _sse_event("verdict", verdict)
            else:
                yield _sse_event("verdict", {"raw": final_content})
        except json.JSONDecodeError:
            yield _sse_event("verdict", {"raw": final_content})

    except Exception as e:
        yield _sse_event("error", {"message": str(e)})


@app.post("/investigate")
async def investigate(alert: AlertPayload):
    """
    Run an AML investigation and stream results as Server-Sent Events.

    Event types:
    - thinking: LLM reasoning tokens (real-time chain of thought)
    - tool_call: tool invocation with name and arguments
    - tool_result: tool response data
    - verdict: final parsed investigation verdict (JSON)
    - error: error message if something fails
    """
    return StreamingResponse(
        _stream_investigation(alert),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/alerts")
async def get_alerts():
    """Return a list of available sample alerts from tests/sample_alerts."""
    import glob
    alerts = {"fp": [], "tp": []}
    base_dir = os.path.join(os.path.dirname(__file__), "tests", "sample_alerts")
    
    for category in ["fp", "tp"]:
        cat_dir = os.path.join(base_dir, category)
        if os.path.exists(cat_dir):
            for file_path in glob.glob(os.path.join(cat_dir, "*.json")):
                filename = os.path.basename(file_path)
                with open(file_path, "r") as f:
                    try:
                        content = json.load(f)
                        alerts[category].append({"name": filename, "content": content})
                    except Exception:
                        pass
            # sort by filename
            alerts[category].sort(key=lambda x: x["name"])
            
    return alerts


@app.get("/")
async def root(request: Request):
    """Serve the frontend HTML test client."""
    return templates.TemplateResponse(request, "index.html", {"llm_config": get_llm_config()})


@app.get("/sar-editor")
async def sar_editor(request: Request):
    """Serve the SAR Editor mockup screen."""
    return templates.TemplateResponse(request, "sar_editor.html", {"llm_config": get_llm_config()})


@app.get("/rules-editor")
async def rules_editor(request: Request):
    """Serve the Admin Rules Editor screen."""
    return templates.TemplateResponse(request, "rules_editor.html", {"llm_config": get_llm_config()})


import asyncio

@app.post("/generate-section/{section_id}")
async def generate_specific_section(section_id: str, request: Request):
    """
    Modular endpoint to generate a specific SAR section on demand.
    """
    try:
        verdict = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # 1. Build the legal context synchronously ONCE
    legal_context = build_legal_context(verdict)
    
    # 2. Route to the correct section generator
    if section_id == "section_1":
        generator = generate_section_1(verdict, legal_context)
    elif section_id == "section_2":
        generator = generate_section_2(verdict, legal_context)
    elif section_id == "section_3":
        generator = generate_section_3(verdict, legal_context)
    elif section_id == "section_4":
        generator = generate_section_4(verdict, legal_context)
    elif section_id == "section_5":
        generator = generate_section_5(verdict, legal_context)
    elif section_id == "section_6":
        generator = generate_section_6(verdict, legal_context)
    elif section_id == "section_7":
        generator = generate_section_7(verdict, legal_context)
    elif section_id == "section_8":
        generator = generate_section_8(verdict, legal_context)
    elif section_id == "section_9":
        generator = generate_section_9(verdict, legal_context)
    elif section_id == "section_10":
        generator = generate_section_10(verdict, legal_context)
    elif section_id == "section_11":
        generator = generate_section_11(verdict, legal_context)
    else:
        raise HTTPException(status_code=404, detail=f"Generator for {section_id} not implemented yet.")

    return StreamingResponse(
        generator, 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

@app.get("/generate-sar-mock")
async def generate_sar_mock():
    """Simulate streaming of a generated SAR document via SSE."""
    async def mock_generator():
        sections = [
            ("Filing Particulars", [
                "The **subject of this SAR** is an individual suspected of involvement ",
                "in a complex web of shell companies designed to obfuscate ",
                "the true nature of international wire transfers. ",
                "Multiple high-value transactions were observed ",
                "originating from jurisdictions known for weak AML controls.\n\n",
                "| Activity Type | Total Amount | Transaction Count |\n",
                "|--------------|--------------|-------------------|\n",
                "| Cash Deposits | $94,500 | 12 |\n",
                "| Outbound Wires | $90,000 | 3 |\n\n",
                "The transaction pattern indicates suspected structuring ",
                "with deposits consistently held just below the $10,000 threshold."
            ]),
            ("Subject Identification", [
                "The primary subject, John Doe (DOB: 15-May-1980), ",
                "maintains three personal and two business accounts.\n\n",
                "Key findings:\n",
                "- High velocity of funds\n",
                "- Missing KYC documentation\n",
                "- Adverse media hits"
            ])
        ]
        
        for section_title, tokens in sections:
            yield _sse_event("section_start", section_title)
            await asyncio.sleep(0.5)
            
            for token in tokens:
                yield _sse_event("token", {"text": token})
                await asyncio.sleep(0.05)
                
            yield _sse_event("section_done", section_title)
            await asyncio.sleep(0.5)
            
        yield _sse_event("complete", "done")

    return StreamingResponse(
        mock_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Data Lookup Endpoints (Evidence Verification) ────────────────────────

_TABLE_PRIMARY_KEYS = {
    "transactions": "transaction_id",
    "accounts": "account_id",
    "customers": "customer_id",
    "aml_alerts_history": "alert_id",
    "watchlists": "watchlist_id",
}


@app.get("/data/watchlists/{watchlist_id}")
async def get_watchlist_entry(watchlist_id: str):
    """Return a single watchlist row with aliases split into a list."""
    from tools.db import get_connection

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM watchlists WHERE watchlist_id = ?", (watchlist_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"No watchlist entry found: {watchlist_id}"}
        data = dict(row)
        # Split aliases from pipe-separated string to list
        aliases_raw = data.get("aliases") or ""
        data["aliases"] = [a.strip() for a in aliases_raw.split("|") if a.strip()] if aliases_raw else []
        return {"table": "watchlists", "id": watchlist_id, "data": data}


@app.get("/data/transactions/counterparty/{name}")
async def get_transactions_by_counterparty(name: str):
    """Return all transaction rows matching a counterparty name."""
    from tools.db import get_connection

    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM transactions WHERE counterparty_name = ?", (name,)
        )
        rows = cursor.fetchall()
        if not rows:
            return {"error": f"No transactions found for counterparty: {name}", "rows": []}
        return {"rows": [dict(row) for row in rows]}


@app.get("/data/{table}/{record_id}")
async def get_data_record(table: str, record_id: str):
    """Return a single raw database row by primary key."""
    from tools.db import get_connection

    if table not in _TABLE_PRIMARY_KEYS:
        return {"error": f"Unknown table: {table}. Valid: {list(_TABLE_PRIMARY_KEYS.keys())}"}

    pk = _TABLE_PRIMARY_KEYS[table]

    with get_connection() as conn:
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE {pk} = ?", (record_id,)
        )
        row = cursor.fetchone()
        if not row:
            return {"error": f"No record found: {table}/{record_id}"}
        return {"table": table, "id": record_id, "data": dict(row)}


# ── Dynamic Config Endpoints (Glossary Codes UI) ────────────────────────

@app.get("/api/rules/glossary-codes")
async def get_glossary_codes():
    """Return the current glossary codes configuration."""
    return config.glossary_codes


@app.put("/api/rules/glossary-codes")
async def update_glossary_codes(request: Request):
    """Update the glossary codes configuration from a JSON payload."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    config.save_glossary_codes(payload)
    return {"status": "ok", "message": "Glossary codes updated and reloaded successfully."}


@app.get("/api/rules/aml-rules")
async def get_aml_rules():
    """Return the current AML rules configuration."""
    return config.aml_rules


@app.put("/api/rules/aml-rules")
async def update_aml_rules(request: Request):
    """Update the AML rules configuration from a JSON payload."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    config.save_aml_rules(payload)
    return {"status": "ok", "message": "AML rules updated and reloaded successfully."}


@app.get("/api/rules/legal-snippets")
async def get_legal_snippets():
    """Return the current legal snippets configuration."""
    return config.legal_snippets


@app.put("/api/rules/legal-snippets")
async def update_legal_snippets(request: Request):
    """Update the legal snippets configuration from a JSON payload."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    config.save_legal_snippets(payload)
    return {"status": "ok", "message": "Legal snippets updated and reloaded successfully."}



