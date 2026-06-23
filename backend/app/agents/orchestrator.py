"""
Agent A — Orquestrador + Agent E (resolució) i graf LangGraph.

Patró orquestrador-treballadors: A fa el triatge, deriva als agents
especialistes (G frau, B documents, C extracció, D cobertura) i finalment
E resol de forma autònoma (PAGO / RECHAZO / REVISIÓN). La persistència de
decisions es centralitza a process_claim.
"""
from __future__ import annotations

import logging
import os

from langgraph.graph import END, StateGraph

from app.agents.reasoning import reason
from app.agents.specialists import (
    agent_b_validate,
    agent_c_extract,
    agent_d_policy,
    agent_g_fraud,
)
from app.agents.state import ClaimState
from app.db.models import ClaimStatus
from app.db.repository import log_agent_decision, save_claim
from app.tools.claim_tools import approve_payment, request_more_info, send_rejection

logger = logging.getLogger(__name__)

# Constants de decisió
PAGO = "PAGO"
RECHAZO = "RECHAZO"
REVISION = "REVISIÓN_HUMANA"
SOLICITUD_INFO = "SOLICITUD_INFO"

_CLIENT_EMAIL = "client@example.com"  # 🔌 MOCK → API: email real del client a Seguros Pepín


def _hitl_threshold() -> float:
    return float(os.getenv("HITL_AMOUNT_THRESHOLD", "5000"))


# ── Nodes ──────────────────────────────────────────────────────────────────

async def triage_node(state: ClaimState) -> dict:
    """Agent A — triatge i inici del cribratge."""
    fallback = (
        f"Agent A: expedient {state['claim_id']} de tipus "
        f"'{state.get('claim_type')}' per import {state.get('amount_requested')}€. "
        f"S'inicia el cribratge antifrau."
    )
    reasoning = reason(
        system="Ets l'Agent A, orquestrador del sistema Smart-Claims de "
               "Seguros Pepín. Raona el triatge pas a pas.",
        prompt=f"Reclamació rebuda: {dict(state)}",
        fallback=fallback,
    )
    return {
        "status": ClaimStatus.OPEN.value,
        "reasoning_trace": [reasoning],
        "decisions_log": [{"agent": "agent_a", "action": "triage",
                           "reasoning": reasoning, "confidence": None,
                           "hitl_required": False}],
    }


async def hitl_node(state: ClaimState) -> dict:
    """Revisió humana (HITL) activada per frau detectat per l'Agent G."""
    risk = state.get("fraud_check", {}).get("risk_score")
    reasoning = (
        f"Agent A: l'expedient {state['claim_id']} es deriva a REVISIÓ HUMANA "
        f"per indicis de frau (risc {risk})."
    )
    return {
        "status": ClaimStatus.PENDING_REVIEW.value,
        "decision": REVISION,
        "hitl_required": True,
        "reasoning_trace": [reasoning],
        "decisions_log": [{"agent": "agent_a", "action": "route_hitl_fraud",
                           "reasoning": reasoning, "confidence": None,
                           "hitl_required": True}],
    }


async def request_info_node(state: ClaimState) -> dict:
    """Agent B deriva: falten documents → es demana informació al client.

    🔌 MOCK → API: enviament real d'email/portal al client de Seguros Pepín.
    """
    missing = state.get("validation", {}).get("missing_docs", [])
    request_more_info.invoke({
        "claim_id": state["claim_id"],
        "missing_fields": missing,
        "client_email": _CLIENT_EMAIL,
    })
    reasoning = (
        f"Agent B: falten documents {missing}; se sol·licita informació "
        f"addicional al client abans de continuar."
    )
    return {
        "status": ClaimStatus.OPEN.value,
        "decision": SOLICITUD_INFO,
        "hitl_required": False,
        "reasoning_trace": [reasoning],
        "decisions_log": [{"agent": "agent_b", "action": "request_more_info",
                           "reasoning": reasoning, "confidence": None,
                           "hitl_required": False}],
    }


async def resolve_node(state: ClaimState) -> dict:
    """Agent E — resolució autònoma: PAGO / RECHAZO / REVISIÓN per import."""
    policy = state.get("policy_check", {})
    amount = state.get("amount_requested") or 0.0
    threshold = _hitl_threshold()

    if not policy.get("covered", False):
        reasoning = reason(
            system="Ets l'Agent E, resolució autònoma.",
            prompt=f"Sense cobertura per a {state.get('claim_type')}: {policy}",
            fallback=(f"Agent E: el sinistre '{state.get('claim_type')}' no té "
                      f"cobertura (secció {policy.get('policy_section')}). Es RECHAZA."),
        )
        # 🔌 MOCK → API: enviament real de la carta de rebuig al client.
        send_rejection.invoke({"claim_id": state["claim_id"], "reason": reasoning,
                               "client_email": _CLIENT_EMAIL})
        return {"status": ClaimStatus.REJECTED.value, "decision": RECHAZO,
                "hitl_required": False, "reasoning_trace": [reasoning],
                "decisions_log": [{"agent": "agent_e", "action": "send_rejection",
                                   "reasoning": reasoning, "confidence": None,
                                   "hitl_required": False}]}

    if amount > threshold:
        reasoning = reason(
            system="Ets l'Agent E, resolució autònoma.",
            prompt=f"Import {amount}€ supera el llindar HITL ({threshold}€).",
            fallback=(f"Agent E: l'import {amount}€ supera el llindar de "
                      f"{threshold}€; es deriva a REVISIÓ HUMANA."),
        )
        return {"status": ClaimStatus.PENDING_REVIEW.value, "decision": REVISION,
                "hitl_required": True, "reasoning_trace": [reasoning],
                "decisions_log": [{"agent": "agent_e", "action": "route_hitl_amount",
                                   "reasoning": reasoning, "confidence": None,
                                   "hitl_required": True}]}

    net = policy.get("net_payable", amount)
    reasoning = reason(
        system="Ets l'Agent E, resolució autònoma.",
        prompt=f"Cobertura OK, import {amount}€ <= llindar {threshold}€. Net {net}€.",
        fallback=(f"Agent E: cobertura confirmada i import {amount}€ dins del "
                  f"llindar; s'aprova el PAGAMENT de {net}€."),
    )
    # 🔌 MOCK → API: ordre de pagament real a la passarel·la/core de Seguros Pepín.
    approve_payment.invoke({"claim_id": state["claim_id"], "amount": net,
                            "iban": "ES0000000000000000000000"})
    return {"status": ClaimStatus.RESOLVED.value, "decision": PAGO,
            "hitl_required": False, "reasoning_trace": [reasoning],
            "decisions_log": [{"agent": "agent_e", "action": "approve_payment",
                               "reasoning": reasoning, "confidence": None,
                               "hitl_required": False}]}


# ── Routers condicionals ─────────────────────────────────────────────────────

def route_after_fraud(state: ClaimState) -> str:
    return "hitl" if state.get("fraud_check", {}).get("is_flagged") else "agent_b"


def route_after_validation(state: ClaimState) -> str:
    return "agent_c" if state.get("validation", {}).get("is_valid") else "request_info"


# ── Graf ─────────────────────────────────────────────────────────────────────

def build_orchestrator():
    g = StateGraph(ClaimState)
    g.add_node("triage", triage_node)
    g.add_node("agent_g", agent_g_fraud)
    g.add_node("agent_b", agent_b_validate)
    g.add_node("agent_c", agent_c_extract)
    g.add_node("agent_d", agent_d_policy)
    g.add_node("resolve", resolve_node)
    g.add_node("hitl", hitl_node)
    g.add_node("request_info", request_info_node)

    g.set_entry_point("triage")
    g.add_edge("triage", "agent_g")
    g.add_conditional_edges("agent_g", route_after_fraud,
                            {"hitl": "hitl", "agent_b": "agent_b"})
    g.add_conditional_edges("agent_b", route_after_validation,
                            {"agent_c": "agent_c", "request_info": "request_info"})
    g.add_edge("agent_c", "agent_d")
    g.add_edge("agent_d", "resolve")
    g.add_edge("resolve", END)
    g.add_edge("hitl", END)
    g.add_edge("request_info", END)
    return g.compile()


orchestrator = build_orchestrator()


# ── API pública ──────────────────────────────────────────────────────────────

async def process_claim(claim_id: str, client_id: str, claim_type: str,
                        amount_requested: float | None = None,
                        channel: str = "email",
                        doc_types: list[str] | None = None) -> ClaimState:
    """Processa un expedient pel graf d'agents i persisteix les decisions.

    La persistència va dins d'un try/except: si no hi ha base de dades
    disponible (p. ex. la CLI de demo sense MariaDB), el flux retorna igualment.
    """
    initial: ClaimState = {
        "claim_id": claim_id, "client_id": client_id, "claim_type": claim_type,
        "amount_requested": amount_requested, "channel": channel,
        "doc_types": doc_types or [], "reasoning_trace": [], "decisions_log": [],
    }
    final = await orchestrator.ainvoke(initial)

    try:
        await save_claim(claim_id, client_id, claim_type, channel, amount_requested,
                         status=ClaimStatus(final.get("status", ClaimStatus.OPEN.value)))
        for d in final.get("decisions_log", []):
            await log_agent_decision(claim_id, d["agent"], d["action"],
                                     d["reasoning"], d.get("confidence"),
                                     d.get("hitl_required", False))
    except Exception as exc:  # la demo sense BD no s'ha de trencar
        logger.warning("No s'han pogut persistir les decisions de %s: %s",
                       claim_id, exc)

    return final
