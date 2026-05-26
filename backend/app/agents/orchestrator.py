"""
Agent A — Orquestrador de triatge i enrutament.

Implementa el patró ReAct (Reason → Act → Observe) via LangGraph.
Gestiona l'estat de cada expedient i delega als agents especialitzats.
"""
from __future__ import annotations

import logging
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.tools.claim_tools import AGENT_TOOLS
from app.db.models import ClaimStatus

logger = logging.getLogger(__name__)


# ── State ──────────────────────────────────────────────────────────────────

class ClaimState(TypedDict):
    claim_id: str
    messages: Annotated[list[BaseMessage], add_messages]
    status: ClaimStatus
    extracted_data: dict
    policy_check: dict | None
    decision: str | None
    hitl_required: bool


# ── LLM ────────────────────────────────────────────────────────────────────

def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        temperature=0,
    ).bind_tools(AGENT_TOOLS)


# ── Nodes ──────────────────────────────────────────────────────────────────

def triage_node(state: ClaimState) -> dict:
    """
    Analitza la reclamació entrant i decideix el primer agent a activar.
    """
    llm = _build_llm()
    system = (
        "Ets l'Agent A — Orquestrador del sistema Smart-Claims de Seguros Pepín. "
        "El teu rol és analitzar cada reclamació entrant i decidir quin agent "
        "especialitzat ha d'intervenir primer. Raona pas a pas (Chain of Thought) "
        "abans d'actuar. Sempre justifica la decisió d'enrutament."
    )
    response = llm.invoke([
        {"role": "system", "content": system},
        *state["messages"],
    ])
    return {"messages": [response]}


def route_after_triage(state: ClaimState) -> str:
    """Router: decideix el proper node basant-se en les tool_calls."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        tool_name = last.tool_calls[0]["name"]
        routing_map = {
            "validate_documents": "agent_b",
            "extract_multimodal":  "agent_c",
            "check_policy":        "agent_d",
            "resolve_claim":       "agent_e",
            "check_fraud":         "agent_g",
        }
        return routing_map.get(tool_name, END)
    return END


def hitl_node(state: ClaimState) -> dict:
    """
    Human-in-the-Loop: pausa el flux per a revisió humana.
    Activat quan l'import supera el llindar o la confiança és baixa.
    """
    logger.info("HITL activat per l'expedient %s", state["claim_id"])
    return {
        "hitl_required": True,
        "status": ClaimStatus.PENDING_REVIEW,
    }


# ── Graph ──────────────────────────────────────────────────────────────────

def build_orchestrator() -> StateGraph:
    graph = StateGraph(ClaimState)

    graph.add_node("triage", triage_node)
    graph.add_node("hitl",   hitl_node)

    # Nodes per a cada agent (s'implementen als seus mòduls respectius)
    graph.add_node("agent_b", _stub("agent_b"))
    graph.add_node("agent_c", _stub("agent_c"))
    graph.add_node("agent_d", _stub("agent_d"))
    graph.add_node("agent_e", _stub("agent_e"))
    graph.add_node("agent_g", _stub("agent_g"))

    graph.set_entry_point("triage")
    graph.add_conditional_edges("triage", route_after_triage)

    return graph.compile()


def _stub(name: str):
    """Stub temporal fins que cada agent estigui implementat."""
    def _node(state: ClaimState) -> dict:
        logger.debug("Agent %s stub cridat per %s", name, state["claim_id"])
        return {}
    _node.__name__ = name
    return _node


# ── Public API ─────────────────────────────────────────────────────────────

orchestrator = build_orchestrator()


async def process_claim(claim_id: str, claim_text: str) -> ClaimState:
    """
    Punt d'entrada públic: rep una reclamació i executa el graf d'agents.

    Args:
        claim_id: Identificador únic de l'expedient.
        claim_text: Text de la reclamació (correu, formulari web, etc.).

    Returns:
        Estat final del graf amb la decisió i el raonament CoT.
    """
    initial_state: ClaimState = {
        "claim_id": claim_id,
        "messages": [HumanMessage(content=claim_text)],
        "status": ClaimStatus.OPEN,
        "extracted_data": {},
        "policy_check": None,
        "decision": None,
        "hitl_required": False,
    }
    return await orchestrator.ainvoke(initial_state)
