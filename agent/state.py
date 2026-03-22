"""
LangGraph state definition for the AML investigation agent.
"""

from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # Annotated with add_messages reducer
    alert: dict  # The incoming alert payload as a dict
    customer_id: str  # Extracted from the alert for convenience
    verdict: dict | None  # Populated at the end of investigation
