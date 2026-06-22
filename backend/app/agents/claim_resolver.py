"""
Claim Resolver — Agente E del sistema Smart-Claims de Seguros Pepín.

Responsabilidad ÚNICA: tomar la decisión final basándose en los outputs
de los agentes anteriores y ejecutarla a través de las Mock APIs.

Reglas de decisión:
- No cubierto                       → RECHAZO justificado
- Cubierto + importe ≤ umbral HITL  → PAGO automático
- Cubierto + importe > umbral HITL  → activa HITL (pausa el flujo)

Referencia en la memoria del TFM: Agente E (claim_resolver.py)
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.claim_tools import (
    approve_payment,
    send_rejection,
    log_decision,
)

if TYPE_CHECKING:
    from app.agents.orchestrator import ClaimState

logger = logging.getLogger(__name__)

HITL_THRESHOLD = float(os.getenv("HITL_AMOUNT_THRESHOLD", "5000.0"))


SYSTEM_PROMPT = """Eres el Agente E (Claim Resolver) del sistema Smart-Claims de Seguros Pepín.

Tu responsabilidad es la decisión y ejecución finales:
- Si el siniestro está cubierto y el importe es bajo: aprueba el pago.
- Si el siniestro está cubierto pero el importe es alto: marca para HITL.
- Si no está cubierto: envía rechazo justificado al cliente.

Reglas:
- Justifica siempre tu decisión con la sección de la póliza aplicable.
- Tono profesional, empático cuando rechazas.
- Responde en español.
"""


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        temperature=0,
    ).bind_tools([approve_payment, send_rejection, log_decision])


def claim_resolver_node(state: dict) -> dict:
    """
    Nodo LangGraph del Agente E.

    Lee del estado: claim_id, client_email, amount_requested, coverage_result.
    Escribe en el estado: resolution, status, hitl_required, terminate, messages.
    """
    from app.db.models import ClaimStatus

    claim_id     = state["claim_id"]
    client_email = state.get("client_email", "cliente@example.com")
    amount       = state.get("amount_requested", 0.0)
    coverage     = state.get("coverage_result") or {}

    is_covered  = coverage.get("covered", False)
    net_payable = coverage.get("net_payable", 0.0)

    logger.info(
        "[Agent E — ClaimResolver] Iniciando — expediente %s | covered=%s | net=%.2f€",
        claim_id, is_covered, net_payable,
    )

    # ── Decisión determinista basada en la cobertura ──────────────────────

    # Caso 1: NO CUBIERTO → rechazo
    if not is_covered:
        section = coverage.get("policy_section", "póliza estándar")
        reason  = f"El siniestro no está cubierto según la sección {section} de la póliza."

        rejection_result = send_rejection.invoke({
            "claim_id":     claim_id,
            "reason":       reason,
            "client_email": client_email,
        })

        resolution = {
            "decision":    "rejected",
            "reason":      reason,
            "amount_paid": 0.0,
            "details":     rejection_result,
        }
        log_decision.invoke({
            "claim_id":  claim_id,
            "agent":     "agent_e_claim_resolver",
            "reasoning": reason,
            "action":    "rejected",
        })
        logger.info("[Agent E] RECHAZO — expediente %s", claim_id)

        return {
            "resolution":         resolution,
            "status":             ClaimStatus.REJECTED,
            "terminate":          True,
            "termination_reason": "rechazado por no cobertura",
        }

    # Caso 2: CUBIERTO + importe > umbral → HITL
    if net_payable > HITL_THRESHOLD:
        logger.info(
            "[Agent E] HITL REQUERIDO — importe %.2f€ supera el umbral %.2f€",
            net_payable, HITL_THRESHOLD,
        )
        log_decision.invoke({
            "claim_id":  claim_id,
            "agent":     "agent_e_claim_resolver",
            "reasoning": f"Importe {net_payable}€ supera umbral HITL ({HITL_THRESHOLD}€)",
            "action":    "hitl_required",
        })
        return {
            "hitl_required":      True,
            "status":             ClaimStatus.PENDING_REVIEW,
            "termination_reason": f"importe {net_payable}€ > umbral HITL",
        }

    # Caso 3: CUBIERTO + importe ≤ umbral → pago automático
    # Usamos un IBAN ficticio; en producción vendría del CRM
    user_content = (
        f"Expediente: {claim_id}\n"
        f"Importe a pagar: {net_payable}€\n"
        f"Cliente: {client_email}\n\n"
        f"Procede al pago automático y justifica la decisión."
    )
    llm      = _build_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    payment_result = approve_payment.invoke({
        "claim_id": claim_id,
        "amount":   net_payable,
        "iban":     "ES7621000418401234567891",  # mock IBAN
    })

    reasoning = (
        response.content
        if hasattr(response, "content") and isinstance(response.content, str)
        else f"Pago automático aprobado por {net_payable}€."
    )
    resolution = {
        "decision":    "approved",
        "reason":      reasoning,
        "amount_paid": net_payable,
        "details":     payment_result,
    }
    log_decision.invoke({
        "claim_id":  claim_id,
        "agent":     "agent_e_claim_resolver",
        "reasoning": reasoning,
        "action":    "approved",
    })
    logger.info(
        "[Agent E] PAGO APROBADO — expediente %s | %.2f€",
        claim_id, net_payable,
    )

    return {
        "messages":           [response],
        "resolution":         resolution,
        "status":             ClaimStatus.RESOLVED,
        "terminate":          True,
        "termination_reason": "pago aprobado",
    }
