"""
Fraud & Compliance — Agente G del sistema Smart-Claims de Seguros Pepín.

Responsabilidad ÚNICA: cribado del cliente contra listas restrictivas
(OFAC, ONU) y cálculo del score de fraude.

Se invoca como FILTRO DE ENTRADA, no como filtro de salida, alineado
con la política PEPIN-POL-CP-0006.

Referencia en la memoria del TFM: Agente G (fraud_compliance.py)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.claim_tools import check_fraud, log_decision

if TYPE_CHECKING:
    from app.agents.orchestrator import ClaimState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres el Agente G (Fraud & Compliance) del sistema Smart-Claims de Seguros Pepín.

Tu responsabilidad es la verificación de cumplimiento normativo y fraude:
1. Cribado contra listas OFAC y ONU.
2. Cálculo del score de riesgo de fraude.
3. Marcar el caso como flagged si el riesgo supera el umbral.

Reglas:
- Usa la tool check_fraud con el client_id y el importe.
- Si is_flagged=True, justifica detalladamente los indicadores.
- Tono técnico y conciso. Responde en español.
"""


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        temperature=0,
    ).bind_tools([check_fraud, log_decision])


def fraud_compliance_node(state: "ClaimState") -> dict:
    """
    Nodo LangGraph del Agente G.

    Lee del estado: claim_id, client_id, amount_requested.
    Escribe en el estado: fraud_result, status, messages.
    """
    from app.db.models import ClaimStatus

    claim_id  = state["claim_id"]
    client_id = state.get("client_id", "UNKNOWN")
    amount    = state.get("amount_requested", 0.0)

    logger.info(
        "[Agent G — FraudCompliance] Iniciando — expediente %s | cliente: %s | importe: %.2f€",
        claim_id, client_id, amount,
    )

    user_content = (
        f"Expediente: {claim_id}\n"
        f"Cliente: {client_id}\n"
        f"Importe reclamado: {amount}€\n\n"
        f"Realiza el cribado OFAC y calcula el score de fraude."
    )

    llm      = _build_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    # ── Procesa tool_calls ─────────────────────────────────────────────────
    fraud_result: dict = {}

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "check_fraud":
                fraud_result = check_fraud.invoke(tool_call["args"])
                logger.info(
                    "[Agent G] check_fraud → flagged=%s | score=%.3f",
                    fraud_result.get("is_flagged"),
                    fraud_result.get("risk_score", 0.0),
                )

    # Fallback determinista si el LLM no llama a la tool
    if not fraud_result:
        fraud_result = check_fraud.invoke({
            "claim_id":  claim_id,
            "client_id": client_id,
            "amount":    amount,
        })

    # ── Log de decisión ────────────────────────────────────────────────────
    reasoning = (
        response.content
        if hasattr(response, "content") and isinstance(response.content, str)
        else f"Cribado OFAC/fraude: {fraud_result}"
    )
    log_decision.invoke({
        "claim_id":  claim_id,
        "agent":     "agent_g_fraud_compliance",
        "reasoning": reasoning,
        "action":    "blocked" if fraud_result.get("is_flagged") else "cleared",
    })

    new_status = (
        ClaimStatus.REJECTED
        if fraud_result.get("is_flagged")
        else ClaimStatus.EXTRACTING
    )

    termination_update = {}
    if fraud_result.get("is_flagged"):
        termination_update = {
            "terminate":          True,
            "termination_reason": "caso bloqueado por fraude/OFAC",
        }

    return {
        "messages":     [response],
        "fraud_result": fraud_result,
        "status":       new_status,
        **termination_update,
    }
