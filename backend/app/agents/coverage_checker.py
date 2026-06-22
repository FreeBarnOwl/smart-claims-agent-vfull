"""
Coverage Checker — Agente D del sistema Smart-Claims de Seguros Pepín.

Responsabilidad ÚNICA: verificar si el siniestro está cubierto por la
póliza del cliente, consultando la base de conocimiento vectorial
(ChromaDB) mediante RAG.

Devuelve cobertura, límite máximo, franquicia e importe neto a pagar.

Referencia en la memoria del TFM: Agente D (coverage_checker.py)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.claim_tools import check_policy, log_decision

if TYPE_CHECKING:
    from app.agents.orchestrator import ClaimState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres el Agente D (Coverage Checker) del sistema Smart-Claims de Seguros Pepín.

Tu responsabilidad es verificar si el siniestro está cubierto por la póliza
del cliente, consultando la base de conocimiento RAG.

Proceso:
1. Llama a check_policy con el tipo de siniestro y el importe.
2. Compara el importe reclamado con el límite máximo y la franquicia.
3. Determina el importe neto a pagar.

Reglas:
- Si no hay cobertura, indica claramente la sección de la póliza aplicable.
- El importe neto nunca puede ser negativo.
- Responde en español.
"""


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
    ).bind_tools([check_policy, log_decision])


def coverage_checker_node(state: dict) -> dict:
    """
    Nodo LangGraph del Agente D.

    Lee del estado: claim_id, claim_type, amount_requested.
    Escribe en el estado: coverage_result, status, messages.
    """
    from app.db.models import ClaimStatus

    claim_id   = state["claim_id"]
    claim_type = state.get("claim_type") or "default"
    amount     = state.get("amount_requested", 0.0)

    logger.info(
        "[Agent D — CoverageChecker] Iniciando — expediente %s | tipo: %s | importe: %.2f€",
        claim_id, claim_type, amount,
    )

    coverage_result: dict = {}

    user_content = (
        f"Expediente: {claim_id}\n"
        f"Tipo de siniestro: {claim_type}\n"
        f"Importe reclamado: {amount}€\n\n"
        f"Verifica la cobertura y devuelve el importe neto a pagar."
    )
    llm      = _build_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "check_policy":
                coverage_result = check_policy.invoke(tool_call["args"])
                logger.info(
                    "[Agent D] check_policy → covered=%s | net_payable=%.2f€",
                    coverage_result.get("covered"),
                    coverage_result.get("net_payable", 0.0),
                )

    # Fallback determinista
    if not coverage_result:
        coverage_result = check_policy.invoke({
            "claim_id":   claim_id,
            "claim_type": claim_type,
            "amount":     amount,
        })

    reasoning = (
        response.content
        if hasattr(response, "content") and isinstance(response.content, str)
        else f"Verificación cobertura: {coverage_result}"
    )
    log_decision.invoke({
        "claim_id":  claim_id,
        "agent":     "agent_d_coverage_checker",
        "reasoning": reasoning,
        "action":    "covered" if coverage_result.get("covered") else "not_covered",
    })

    logger.info(
        "[Agent D — CoverageChecker] Completado — covered=%s",
        coverage_result.get("covered"),
    )

    return {
        "messages":        [response],
        "coverage_result": coverage_result,
        "status":          ClaimStatus.CHECKING_POLICY,
    }
