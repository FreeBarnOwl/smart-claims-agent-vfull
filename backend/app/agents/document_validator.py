"""
Document Validator — Agente B del sistema Smart-Claims de Seguros Pepín.

Responsabilidad ÚNICA: validar la documentación aportada por el cliente
contra los requisitos del tipo de siniestro.

NO decide el siguiente agente — devuelve el control al supervisor del
Agente A, que enruta según el resultado.

Referencia en la memoria del TFM: Agente B (document_validator.py)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.claim_tools import (
    validate_documents,
    request_more_info,
    log_decision,
)

if TYPE_CHECKING:
    from app.agents.orchestrator import ClaimState

logger = logging.getLogger(__name__)


# ── Documentos requeridos por tipo de siniestro ────────────────────────────

REQUIRED_DOCS: dict[str, list[str]] = {
    "danys_propis":    ["foto_danys", "factura", "denuncia_companyia"],
    "responsabilitat": ["foto_danys", "acta_policial", "dades_tercer"],
    "robatori":        ["acta_policial", "llista_objectes_robats"],
    "danys_mecanics":  ["informe_taller", "factura"],
    "default":         ["foto_danys", "factura"],
}


SYSTEM_PROMPT = """Eres el Agente B (Document Validator) del sistema Smart-Claims de Seguros Pepín.

Tu única responsabilidad es la VALIDACIÓN DOCUMENTAL de las reclamaciones entrantes.

Proceso:
1. Compara los documentos aportados con los requeridos para ese tipo de siniestro.
2. Verifica el contrato del cliente vigente.
3. Razona paso a paso (Chain of Thought).
4. Si faltan docs: usa request_more_info con la lista exacta.
5. Si todo está completo: indica validación correcta.

Reglas:
- Nunca asumas documentos no mencionados explícitamente.
- Sé específico nombrando cada documento faltante.
- Tono profesional y empático hacia el cliente.
- Responde siempre en español.
"""


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        temperature=0,
    ).bind_tools([validate_documents, request_more_info, log_decision])


def document_validator_node(state: "ClaimState") -> dict:
    """
    Nodo LangGraph del Agente B.

    Lee del estado: claim_id, claim_type, documents, client_email.
    Escribe en el estado: validation_result, status, messages.
    NO decide el siguiente nodo (lo hace el supervisor).
    """
    from app.db.models import ClaimStatus

    claim_id     = state["claim_id"]
    claim_type   = state.get("claim_type") or "default"
    documents    = state.get("documents") or []
    client_email = state.get("client_email", "cliente@example.com")

    logger.info(
        "[Agent B — DocumentValidator] Iniciando — expediente %s | tipo: %s | docs: %s",
        claim_id, claim_type, documents
    )

    required = REQUIRED_DOCS.get(claim_type, REQUIRED_DOCS["default"])

    user_content = (
        f"Expediente: {claim_id}\n"
        f"Tipo de siniestro: {claim_type}\n"
        f"Documentos requeridos: {', '.join(required)}\n"
        f"Documentos aportados: {', '.join(documents) if documents else 'ninguno'}\n"
        f"Email del cliente: {client_email}\n"
    )

    llm      = _build_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    # ── Procesa tool_calls ─────────────────────────────────────────────────
    validation_result: dict = {}

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            name = tool_call["name"]
            args = tool_call["args"]

            if name == "validate_documents":
                validation_result = validate_documents.invoke(args)
                logger.info(
                    "[Agent B] validate_documents → is_valid=%s | missing=%s",
                    validation_result.get("is_valid"),
                    validation_result.get("missing_docs"),
                )

                if not validation_result.get("is_valid"):
                    request_more_info.invoke({
                        "claim_id":       claim_id,
                        "missing_fields": validation_result.get("missing_docs", []),
                        "client_email":   client_email,
                    })

            elif name == "request_more_info":
                request_more_info.invoke(args)

    # Si el LLM no ha llamado a validate_documents, hacemos la verificación
    # determinista nosotros para garantizar consistencia.
    if not validation_result:
        missing = [d for d in required if d not in documents]
        validation_result = {
            "claim_id":        claim_id,
            "is_valid":        len(missing) == 0,
            "missing_docs":    missing,
            "contract_active": True,
        }
        if missing:
            request_more_info.invoke({
                "claim_id":       claim_id,
                "missing_fields": missing,
                "client_email":   client_email,
            })

    # ── Log de decisión ────────────────────────────────────────────────────
    reasoning = (
        response.content
        if hasattr(response, "content") and isinstance(response.content, str)
        else f"Validación documental: {validation_result}"
    )
    log_decision.invoke({
        "claim_id":  claim_id,
        "agent":     "agent_b_document_validator",
        "reasoning": reasoning,
        "action":    "validated" if validation_result.get("is_valid") else "info_requested",
    })

    logger.info(
        "[Agent B — DocumentValidator] Completado — is_valid=%s",
        validation_result.get("is_valid"),
    )

    new_status = (
        ClaimStatus.EXTRACTING
        if validation_result.get("is_valid")
        else ClaimStatus.VALIDATING
    )

    return {
        "messages":          [response],
        "validation_result": validation_result,
        "status":            new_status,
    }
