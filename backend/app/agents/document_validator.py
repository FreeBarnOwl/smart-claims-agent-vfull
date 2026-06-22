"""
Document Validator — Agente B del sistema Smart-Claims de Seguros Pepín.

Responsabilidad ÚNICA: validar la documentación aportada por el cliente
contra los requisitos del tipo de siniestro.

Arquitectura interna:
- VALIDACIÓN: lógica determinista basada en REQUIRED_DOCS (auditable).
- RAZONAMIENTO: LLM (Claude Sonnet) explica el resultado en lenguaje natural.

NO decide el siguiente agente — devuelve el control al supervisor del
Agente A, que enruta según el resultado.

Referencia en la memoria del TFM: Agente B (document_validator.py)
"""
from __future__ import annotations

import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.claim_tools import request_more_info, log_decision

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

Tu responsabilidad es la VALIDACIÓN DOCUMENTAL de las reclamaciones entrantes.

La validación en sí (qué documentos faltan) se calcula de forma determinista
fuera de ti. Tu papel es:
1. Razonar paso a paso (Chain of Thought) sobre el resultado de la validación.
2. Justificar profesionalmente por qué la documentación es suficiente o no.
3. Si faltan documentos, redactar mentalmente el mensaje que recibirá el cliente.

Reglas:
- Tono profesional y empático.
- Responde siempre en español.
- Sé conciso pero completo en la justificación.
"""


def _build_llm() -> ChatAnthropic:
    """LLM sin tools — solo razona, no actúa."""
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
    )


def document_validator_node(state: dict) -> dict:
    """
    Nodo LangGraph del Agente B.

    Flujo:
    1. Calcula validation_result de forma determinista (REQUIRED_DOCS).
    2. Si faltan documentos, llama a request_more_info para notificar al cliente.
    3. Llama al LLM para que razone sobre el resultado (Chain of Thought).
    4. Registra la decisión en MariaDB vía log_decision.
    """
    from app.db.models import ClaimStatus

    claim_id     = state["claim_id"]
    claim_type   = state.get("claim_type") or "default"
    documents    = state.get("documents") or []
    client_email = state.get("client_email", "cliente@example.com")

    logger.info(
        "[Agent B — DocumentValidator] Iniciando — expediente %s | tipo: %s | docs: %s",
        claim_id, claim_type, documents,
    )

    # ── 1. Validación determinista ────────────────────────────────────────
    required = REQUIRED_DOCS.get(claim_type, REQUIRED_DOCS["default"])
    missing  = [d for d in required if d not in documents]
    validation_result = {
        "claim_id":        claim_id,
        "is_valid":        len(missing) == 0,
        "missing_docs":    missing,
        "contract_active": True,
        "required_docs":   required,
        "provided_docs":   documents,
    }

    logger.info(
        "[Agent B] Validación → is_valid=%s | missing=%s",
        validation_result["is_valid"], missing,
    )

    # ── 2. Si faltan documentos, notificar al cliente ─────────────────────
    if not validation_result["is_valid"]:
        request_more_info.invoke({
            "claim_id":       claim_id,
            "missing_fields": missing,
            "client_email":   client_email,
        })

    # ── 3. LLM razona sobre el resultado (Chain of Thought) ──────────────
    user_content = (
        f"Expediente: {claim_id}\n"
        f"Tipo de siniestro: {claim_type}\n"
        f"Documentos requeridos: {', '.join(required)}\n"
        f"Documentos aportados: {', '.join(documents) if documents else 'ninguno'}\n"
        f"Resultado: {'VÁLIDO' if validation_result['is_valid'] else 'INCOMPLETO'}\n"
        f"Documentos faltantes: {', '.join(missing) if missing else 'ninguno'}\n\n"
        f"Justifica el resultado paso a paso y, si la documentación es "
        f"incompleta, indica qué debe aportar el cliente."
    )

    llm      = _build_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    reasoning = (
        response.content
        if hasattr(response, "content") and isinstance(response.content, str)
        else f"Validación documental: {validation_result}"
    )

    # ── 4. Log de la decisión ─────────────────────────────────────────────
    log_decision.invoke({
        "claim_id":  claim_id,
        "agent":     "agent_b_document_validator",
        "reasoning": reasoning,
        "action":    "validated" if validation_result["is_valid"] else "info_requested",
    })

    logger.info(
        "[Agent B — DocumentValidator] Completado — is_valid=%s",
        validation_result["is_valid"],
    )

    new_status = (
        ClaimStatus.EXTRACTING
        if validation_result["is_valid"]
        else ClaimStatus.VALIDATING
    )

    return {
        "messages":          [response],
        "validation_result": validation_result,
        "status":            new_status,
    }
