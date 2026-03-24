"""
LangGraph graph definition for the AML investigation agent.

Builds a StateGraph with an agent node (LLM + tools) and a tools node,
connected in a reasoning loop.
"""

import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from agent.state import AgentState
from agent.llm import get_llm
from tools import tools

load_dotenv()

# ── Rate-limit event queue (consumed by api.py SSE stream) ────────────
_rate_limit_events: list[dict] = []

def drain_rate_limit_events() -> list[dict]:
    """Return and clear all pending rate-limit events."""
    global _rate_limit_events
    events = _rate_limit_events.copy()
    _rate_limit_events = []
    return events

def clear_rate_limit_events():
    """Clear the rate-limit event queue (call at investigation start)."""
    global _rate_limit_events
    _rate_limit_events = []


def should_continue(state: AgentState) -> str:
    """Route based on whether the last message has tool calls."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# Cache the bound LLM so we don't recreate the model on every invocation
_llm_with_tools = None

def agent_node(state: AgentState) -> dict:
    """Call the LLM with the current message history."""
    global _llm_with_tools
    
    # Check if we are using groq to determine if we should handle rate limits
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    
    if _llm_with_tools is None:
        llm = get_llm()
        _llm_with_tools = llm.bind_tools(tools)
        
    if provider != "groq":
        # No key hopping for non-Groq providers
        response = _llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}
        
    import groq
    from agent.llm import rotate_groq_key, get_groq_key_count
    import agent.llm as _llm_module
    import logging
    logger = logging.getLogger(__name__)
    
    attempts = get_groq_key_count()
    last_error = None
    
    for attempt in range(attempts):
        try:
            response = _llm_with_tools.invoke(state["messages"])
            return {"messages": [response]}
        except groq.RateLimitError as e:
            last_error = e
            old_index = _llm_module._current_groq_index + 1
            if attempt < attempts - 1:
                logger.warning("Rate limit hit in agent_node. Hopping to next Groq key...")
                # Rotate the key
                rotate_groq_key()
                new_index = _llm_module._current_groq_index + 1
                _rate_limit_events.append({
                    "type": "key_rotated",
                    "exhausted_key": old_index,
                    "new_key": new_index,
                    "total_keys": attempts,
                    "remaining_keys": attempts - attempt - 1,
                })
                # Rebuild the LLM cache with the new key
                llm = get_llm()
                _llm_with_tools = llm.bind_tools(tools)
            else:
                _rate_limit_events.append({
                    "type": "all_keys_exhausted",
                    "total_keys": attempts,
                })
                logger.error("All Groq API keys exhausted (rate limited).")
                
    raise last_error  # type: ignore


# Build the graph
tool_node = ToolNode(tools)

graph_builder = StateGraph(AgentState)

# Add nodes
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", tool_node)

# Set entry point
graph_builder.set_entry_point("agent")

# Add conditional edge from agent
graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})

# Edge from tools back to agent
graph_builder.add_edge("tools", "agent")

# Compile
graph = graph_builder.compile()
