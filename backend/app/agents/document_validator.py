"""
Document Validator — Agente B del sistema Smart-Claims de Seguros Pepin.

Responsabilidad unica: validar la documentacion aportada por el cliente
contra los requisitos del tipo de siniestro.

Arquitectura interna:
- VALIDACION:    logica determinista basada en REQUIRED_DOCS_BY_TYPE.
- RAZONAMIENTO:  helper reason() — LLM opcional con fallback determinista.

NO decide el siguiente agente — devuelve el control al supervisor del
Orchestrator (Agente A) acumulando su contribucion en reasoning_trace y
decisions_log.

Referencia en la memoria del TFM: Agente B (document_validator.py).
"""
from __future__ import annotations

import logging

from app.agents.reasoning import claim_type_label, reason
from app.tools.claim_tools import (
    REQUIRED_DOCS_BY_TYPE,
    request_more_info,
    validate_documents,
)

logger = logging.getLogger(__name__)

# Etiquetas en castellano para los identificadores internos de documento.
# Los identificadores (foto_danys, denuncia_companyia, ...) son claves de
# dato usadas por claim_tools/multimodal_extractor y no se renombran; esta
# tabla es solo para el texto que se muestra al usuario.
DOC_LABEL_ES = {
    "foto_danys":             "foto de daños",
    "factura":                "factura",
    "denuncia_companyia":     "denuncia a la compañía",
    "acta_policial":          "acta policial",
    "dades_tercer":           "datos del tercero",
    "llista_objectes_robats": "listado de objetos robados",
    "informe_taller":         "informe del taller",
}


def _doc_labels(doc_types: list[str]) -> list[str]:
    return [DOC_LABEL_ES.get(d, d) for d in doc_types]


async def document_validator_node(state: dict) -> dict:
    """
    Nodo LangGraph del Agente B — Document Validator.

    Lee del estado: claim_id, claim_type, documents, client_email.
    Escribe en el estado: validation_result, reasoning_trace, decisions_log.
    """
    claim_id     = state["claim_id"]
    claim_type   = state.get("claim_type") or "default"
    documents    = state.get("documents") or []
    client_email = state.get("client_email", "cliente@example.com")

    logger.info(
        "[Agente B — DocumentValidator] Inicio — expediente %s | tipo: %s | docs: %s",
        claim_id, claim_type, documents,
    )

    # ── Validacion determinista ──────────────────────────────────────────
    validation = validate_documents.invoke({
        "claim_id":   claim_id,
        "claim_type": claim_type,
        "doc_types":  documents,
    })

    # ── Si faltan documentos, notificar al cliente ───────────────────────
    if not validation["is_valid"]:
        request_more_info.invoke({
            "claim_id":       claim_id,
            "missing_fields": validation["missing_docs"],
            "client_email":   client_email,
        })

    # ── Razonamiento (LLM opcional con fallback determinista) ────────────
    claim_type_es = claim_type_label(claim_type)
    fallback = (
        f"Agente B: documentacion "
        f"{'completa y conforme' if validation['is_valid'] else 'incompleta'}. "
        f"Documentos requeridos: {', '.join(_doc_labels(validation['required_docs']))}. "
        f"Documentos faltantes: "
        f"{', '.join(_doc_labels(validation['missing_docs'])) if validation['missing_docs'] else 'ninguno'}."
    )

    reasoning = reason(
        system=(
            "Eres el Agente B (Document Validator) del sistema Smart-Claims "
            "de Seguros Pepin. Tu rol es validar la documentacion de las "
            "reclamaciones. Razona paso a paso y justifica el resultado "
            "de forma profesional. Responde siempre en castellano."
        ),
        prompt=(
            f"Resultado de la validacion documental:\n"
            f"- Expediente: {claim_id}\n"
            f"- Tipo de siniestro: {claim_type_es}\n"
            f"- Documentos requeridos: {_doc_labels(validation['required_docs'])}\n"
            f"- Documentos aportados: {_doc_labels(validation['provided_docs'])}\n"
            f"- Documentos faltantes: {_doc_labels(validation['missing_docs'])}\n"
            f"- Contrato vigente: {validation['contract_active']}\n\n"
            f"Justifica el resultado y, si la documentacion es incompleta, "
            f"indica que debe aportar el cliente."
        ),
        fallback=fallback,
    )

    logger.info(
        "[Agente B] Validacion completada — is_valid=%s",
        validation["is_valid"],
    )

    return {
        "validation_result": validation,
        "reasoning_trace":   [reasoning],
        "decisions_log":     [{
            "agent":         "agent_b_document_validator",
            "action":        "validated" if validation["is_valid"] else "info_requested",
            "reasoning":     reasoning,
            "confidence":    None,
            "hitl_required": False,
        }],
    }
