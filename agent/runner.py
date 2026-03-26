"""
Runner for the AML investigation agent.

Entry point for running a single investigation from an AlertPayload.
Prints the full chain of thought and final verdict.
"""

import json
import re
from langchain_core.messages import SystemMessage, HumanMessage, AIMessageChunk

from schemas.alert import AlertPayload
from agent.prompts import build_system_prompt
from agent.graph import graph
from agent.llm import get_llm_config


def _extract_text(content) -> str:
    """Extract plain text from content that may be a string or a list of dicts (Gemini format)."""
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

def run_investigation(alert: AlertPayload) -> str:
    """
    Run an AML investigation for the given alert.

    Args:
        alert: An AlertPayload instance describing the suspicious activity.

    Returns:
        The final AI message content as a string.
    """
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

    print("=" * 80)
    print("STARTING AML INVESTIGATION")
    print(f"Alert ID:    {alert.alert_id}")
    print(f"Customer ID: {alert.customer_id}")
    config = get_llm_config()
    print(f"LLM Provider: {config['provider'].upper()}")
    print(f"LLM Model:    {config['model']}")
    print("=" * 80)

    print("\n" + "=" * 80)
    print("CHAIN OF THOUGHT")
    print("=" * 80)

    final_content = ""
    current_node = None
    ai_message_index = 0
    tool_message_index = 0
    tool_call_buffer = {}

    # stream_mode="messages" yields (chunk, metadata) tuples
    # Each chunk is a message fragment as the LLM generates it
    for chunk, metadata in graph.stream(
        initial_state,
        stream_mode="messages"
    ):
        node = metadata.get("langgraph_node")

        # ── node transition header ─────────────────────────────────
        if node != current_node:
            current_node = node

            if node == "agent":
                ai_message_index += 1
                print(f"\n--- [AI {ai_message_index}] ---")

            elif node == "tools":
                tool_message_index += 1
                print(f"\n--- [Tool {tool_message_index}] ---")

        # ── stream AI content token by token ──────────────────────
        if isinstance(chunk, AIMessageChunk):

            # Reasoning text — print as it streams
            if chunk.content:
                text = _extract_text(chunk.content)
                if text:
                    print(text, end="", flush=True)
                    final_content += text

            # Tool call — accumulate and print when the call is complete
            if chunk.tool_call_chunks:
                for tc in chunk.tool_call_chunks:
                    call_id = tc.get("id") or tc.get("index", 0)
                    if call_id not in tool_call_buffer:
                        tool_call_buffer[call_id] = {"name": "", "args": ""}
                    if tc.get("name"):
                        tool_call_buffer[call_id]["name"] += tc["name"]
                    if tc.get("args"):
                        tool_call_buffer[call_id]["args"] += tc["args"]

                # Print completed tool calls (args ends with closing brace)
                for call_id, tc in list(tool_call_buffer.items()):
                    if tc["args"].strip().endswith("}"):
                        print(f"\n  -> Tool call: {tc['name']}({tc['args']})", flush=True)
                        del tool_call_buffer[call_id]

        # ── print tool results when they arrive ───────────────────
        else:
            content = _extract_text(chunk.content) if hasattr(chunk, "content") else str(chunk)
            if content.strip():
                print(content, flush=True)

    # ── extract and print final verdict ───────────────────────────
    print("\n\n" + "=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    try:
        json_match = re.search(r'\{.*\}', final_content, re.DOTALL)
        if json_match:
            verdict = json.loads(json_match.group())
            print(json.dumps(verdict, indent=2, ensure_ascii=False))
        else:
            print(final_content)
    except json.JSONDecodeError:
        print(final_content)

    return final_content
