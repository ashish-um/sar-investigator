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


def should_continue(state: AgentState) -> str:
    """Route based on whether the last message has tool calls."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def agent_node(state: AgentState) -> dict:
    """Call the LLM with the current message history."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


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
