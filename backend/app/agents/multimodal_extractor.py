"""
Multimodal Extractor — Agente C del sistema Smart-Claims de Seguros Pepín.

Responsabilidad ÚNICA: extraer datos estructurados de los documentos
adjuntos (facturas, fotos de daños, actas policiales) usando Claude
con capacidades de visión (VLM).

Si la confianza de extracción es baja, hace fallback a OCR clásico
(Tesseract).

Referencia en la memoria del TFM: Agente C (multimodal_extractor.py)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.tools.claim_tools import extract_multimodal, log_decision

if TYPE_CHECKING:
    from app.agents.orchestrator import ClaimState

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Eres el Agente C (Multimodal Extractor) del sistema Smart-Claims de Seguros Pepín.

Tu responsabilidad es la extracción de datos estructurados de los documentos
adjuntos: facturas, fotografías de daños y actas policiales.

Proceso:
1. Por cada documento aportado, llama a extract_multimodal con su tipo.
2. Si la confianza es < 0.85, marca el resultado para revisión manual.
3. Agrega todos los resultados en un dict consolidado.

Reglas:
- Sé exhaustivo: nunca dejes un documento sin procesar.
- Reporta la confianza de cada extracción.
- Responde en español.
"""


def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        temperature=0,
    ).bind_tools([extract_multimodal, log_decision])


def multimodal_extractor_node(state: "ClaimState") -> dict:
    """
    Nodo LangGraph del Agente C.

    Lee del estado: claim_id, documents.
    Escribe en el estado: extraction_result, status, messages.
    """
    from app.db.models import ClaimStatus

    claim_id  = state["claim_id"]
    documents = state.get("documents") or []

    logger.info(
        "[Agent C — MultimodalExtractor] Iniciando — expediente %s | docs: %s",
        claim_id, documents,
    )

    # Extracción determinista por cada documento aportado
    extracted: dict = {}
    low_confidence_docs: list[str] = []

    for doc_type in documents:
        result = extract_multimodal.invoke({
            "claim_id": claim_id,
            "file_url": f"file://{claim_id}/{doc_type}.bin",  # mock URL
            "doc_type": doc_type,
        })
        extracted[doc_type] = result
        if result.get("confidence", 0) < 0.85:
            low_confidence_docs.append(doc_type)
        logger.info(
            "[Agent C] %s → confidence=%.3f | data=%s",
            doc_type, result.get("confidence", 0), result.get("extracted"),
        )

    # Llamada LLM para consolidar y razonar sobre la extracción
    user_content = (
        f"Expediente: {claim_id}\n"
        f"Documentos procesados: {documents}\n"
        f"Datos extraídos: {extracted}\n"
        f"Baja confianza en: {low_confidence_docs}\n\n"
        f"Resume los hallazgos clave para los siguientes agentes."
    )
    llm      = _build_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_content),
    ])

    # ── Consolida el resultado ────────────────────────────────────────────
    # Intenta inferir el importe total de las facturas si está disponible
    inferred_amount = 0.0
    for doc_data in extracted.values():
        amount = doc_data.get("extracted", {}).get("amount", 0)
        if isinstance(amount, (int, float)):
            inferred_amount = max(inferred_amount, float(amount))

    extraction_result = {
        "claim_id":            claim_id,
        "by_document":         extracted,
        "low_confidence_docs": low_confidence_docs,
        "inferred_amount":     inferred_amount,
    }

    reasoning = (
        response.content
        if hasattr(response, "content") and isinstance(response.content, str)
        else f"Extracción multimodal: {len(extracted)} documentos procesados."
    )
    log_decision.invoke({
        "claim_id":  claim_id,
        "agent":     "agent_c_multimodal_extractor",
        "reasoning": reasoning,
        "action":    "extracted",
    })

    logger.info(
        "[Agent C — MultimodalExtractor] Completado — %d docs | importe inferido: %.2f€",
        len(extracted), inferred_amount,
    )

    # Si no había importe en el state, usar el inferido para los siguientes agentes
    updates = {
        "messages":           [response],
        "extraction_result":  extraction_result,
        "status":             ClaimStatus.CHECKING_POLICY,
    }
    if state.get("amount_requested", 0) == 0 and inferred_amount > 0:
        updates["amount_requested"] = inferred_amount

    return updates
