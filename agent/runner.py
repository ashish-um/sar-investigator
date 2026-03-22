"""
Runner for the AML investigation agent.

Entry point for running a single investigation from an AlertPayload.
Prints the full chain of thought and final verdict.
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage

from schemas.alert import AlertPayload
from agent.prompts import SYSTEM_PROMPT
from agent.graph import graph


def run_investigation(alert: AlertPayload) -> str:
    """
    Run an AML investigation for the given alert.

    Args:
        alert: An AlertPayload instance describing the suspicious activity.

    Returns:
        The final AI message content as a string.
    """
    alert_dict = alert.model_dump()

    # Build initial messages
    human_content = (
        f"ALERT RECEIVED:\n"
        f"{json.dumps(alert_dict, indent=2)}\n\n"
        f"Begin your investigation. Start by forming a hypothesis, then use the "
        f"available tools to gather evidence. The customer under investigation is: "
        f"{alert.customer_id}"
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

    # Invoke the graph
    print("=" * 80)
    print("STARTING AML INVESTIGATION")
    print(f"Alert ID: {alert.alert_id}")
    print(f"Customer ID: {alert.customer_id}")
    print("=" * 80)

    result = graph.invoke(initial_state)

    # Print chain of thought
    print("\n" + "=" * 80)
    print("CHAIN OF THOUGHT")
    print("=" * 80)

    for i, msg in enumerate(result["messages"]):
        msg_type = type(msg).__name__
        label_map = {
            "SystemMessage": "System",
            "HumanMessage": "Human",
            "AIMessage": "AI",
            "ToolMessage": "Tool",
        }
        label = label_map.get(msg_type, msg_type)

        print(f"\n--- [{i+1}] {label} ---")

        if hasattr(msg, "content") and msg.content:
            # Truncate very long tool responses for readability
            content = str(msg.content)
            if label == "Tool" and len(content) > 500:
                print(content[:500] + "... [truncated]")
            else:
                print(content)

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  -> Tool call: {tc['name']}({tc['args']})")

    # Extract and print final verdict
    final_message = result["messages"][-1]
    final_content = final_message.content if hasattr(final_message, "content") else ""

    print("\n" + "=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    try:
        # Find JSON in the response (may be wrapped in markdown code blocks)
        json_str = final_content
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()
        else:
            # Fallback: extract substring between first { and last }
            start = json_str.find('{')
            end = json_str.rfind('}')
            if start != -1 and end != -1:
                json_str = json_str[start:end+1]

        verdict = json.loads(json_str)
        print(json.dumps(verdict, indent=2))
    except (json.JSONDecodeError, IndexError):
        print(final_content)

    return final_content
