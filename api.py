"""
FastAPI SSE endpoint for the AML Investigation Agent.

Provides a POST /investigate endpoint that accepts an AlertPayload JSON body
and returns a Server-Sent Events stream with real-time investigation output.

Run with:  uvicorn api:app --reload
"""

import json
import re
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import SystemMessage, HumanMessage, AIMessageChunk

from schemas.alert import AlertPayload
from agent.prompts import SYSTEM_PROMPT
from agent.graph import graph

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


def _sse_event(event_type: str, data: dict) -> str:
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

    initial_state = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT),
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

    try:
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


@app.get("/")
async def root():
    """Serve the frontend HTML test client."""
    import os
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "API is running. index.html not found."}
