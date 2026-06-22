"""
Orchestrator — Agente A del sistema Smart-Claims de Seguros Pepín.

Implementa el patrón Supervisor (Hub-and-Spoke) sobre LangGraph.
El supervisor es el ÚNICO componente que decide el flujo: lee el estado
acumulado y enruta al siguiente agente. Los agentes son nodos puros que
hacen su trabajo y devuelven el control al supervisor.

Mapa de agentes (referencia memoria TFM):
    Agente A → orchestrator.py          (este fichero, supervisor)
    Agente B → document_validator.py     implementado
    Agente C → multimodal_extractor.py   skeleton
    Agente D → coverage_checker.py       skeleton
    Agente E → claim_resolver.py         skeleton
    Agente G → fraud_compliance.py       skeleton

Flujo (decidido siempre por el supervisor):
    triage → document_validator → fraud_compliance →
    multimodal_extractor → coverage_checker → claim_resolver → [hitl] → END

Cortocircuitos posibles:
    - document_validator detecta docs faltantes → END
    - fraud_compliance detecta OFAC/fraude alto → END
    - coverage_checker detecta no cobertura    → END (vía claim_resolver)
    - claim_resolver detecta importe > HITL    → hitl → END
"""
from __future__ import annotations

import logging
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from app.db.models import ClaimStatus

logger = logging.getLogger(__name__)


# ── State ──────────────────────────────────────────────────────────────────

class ClaimState(TypedDict):
    # ── Identidad ─────────────────────────────────
    claim_id:           str
    client_id:          str
    client_email:       str

    # ── Conversación / CoT ────────────────────────
    messages:           Annotated[list[BaseMessage], add_messages]

    # ── Datos del expediente ──────────────────────
    claim_type:         str
    amount_requested:   float
    documents:          list[str]

    # ── Resultados por agente ─────────────────────
    validation_result:  dict | None      # Agente B
    fraud_result:       dict | None      # Agente G
    extraction_result:  dict | None      # Agente C
    coverage_result:    dict | None      # Agente D
    resolution:         dict | None      # Agente E

    # ── Control de flujo ──────────────────────────
    status:             ClaimStatus
    hitl_required:      bool
    terminate:          bool
    termination_reason: str | None


# ── LLM para el triage inicial ────────────────────────────────────────────

def _build_triage_llm() -> ChatAnthropic:
    """LLM para parsear el correo entrante. No usa tools."""
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
    )


# ── Nodos del Agente A ────────────────────────────────────────────────────

def triage_node(state: ClaimState) -> dict:
    """
    Nodo de entrada. Parsea la reclamación recibida y enriquece el estado
    con los campos estructurados (tipo, importe, documentos aportados).

    No decide el siguiente agente — eso es responsabilidad del supervisor.

    Referencia en la memoria del TFM: Agente A (orchestrator.py — triage)
    """
    claim_id = state["claim_id"]
    logger.info("[Agent A — Triage] Iniciando triaje — expediente %s", claim_id)

    # Si el state ya tiene los campos rellenos (porque la API REST los pasó
    # estructurados), no hace falta llamar al LLM. Solo si solo hay texto.
    if state.get("claim_type") and state.get("documents") is not None:
        logger.info("[Agent A — Triage] Estado ya estructurado — saltando LLM")
        return {"status": ClaimStatus.VALIDATING}

    # Parseo LLM del texto inicial
    llm = _build_triage_llm()
    system = (
        "Eres el módulo de triaje del Agente A del sistema Smart-Claims. "
        "Tu única tarea es extraer información estructurada de la reclamación "
        "entrante. Responde SIEMPRE en formato JSON con los campos: "
        "claim_type (danys_propis|responsabilitat|robatori|danys_mecanics|default), "
        "amount_requested (float), "
        "documents (lista de strings: foto_danys, factura, acta_policial, etc.), "
        "client_email (string). "
        "Si no puedes determinar un campo, usa null."
    )
    response = llm.invoke([
        SystemMessage(content=system),
        *state["messages"],
    ])

    logger.info("[Agent A — Triage] Triaje completado — expediente %s", claim_id)

    # Por ahora, el parseo del JSON queda como TODO; el supervisor
    # funciona con los campos que ya vienen del state inicial.
    return {
        "messages": [response],
        "status":   ClaimStatus.VALIDATING,
    }


def hitl_node(state: ClaimState) -> dict:
    """
    Human-in-the-Loop: pausa el flujo para revisión humana.
    Lo activa el supervisor cuando claim_resolver marca hitl_required=True.
    """
    logger.info("[Agent A — HITL] Activado — expediente %s | razón: %s",
                state["claim_id"],
                state.get("termination_reason") or "importe sobre umbral")
    return {
        "status":    ClaimStatus.PENDING_REVIEW,
        "terminate": True,
    }


# ── SUPERVISOR — el cerebro del enrutamiento ─────────────────────────────

def supervisor_router(state: ClaimState) -> str:
    """
    Núcleo del patrón Hub-and-Spoke.

    Lee el estado acumulado y decide DETERMINÍSTICAMENTE el próximo agente.
    Ningún agente tiene su propio router: todos retornan aquí.

    Orden de evaluación:
    1. ¿Flujo terminado?              → END
    2. ¿HITL activado?                → hitl
    3. ¿Falta validación documental?  → document_validator (B)
    4. ¿Docs incompletos?             → END (cliente notificado)
    5. ¿Falta verificación fraude?    → fraud_compliance (G)
    6. ¿Cliente flagged?              → END (bloqueado)
    7. ¿Falta extracción VLM?         → multimodal_extractor (C)
    8. ¿Falta verificación cobertura? → coverage_checker (D)
    9. ¿Falta resolución?             → claim_resolver (E)
    10. Todo completo                 → END
    """
    claim_id = state["claim_id"]

    # 1. Flujo terminado explícitamente
    if state.get("terminate"):
        reason = state.get("termination_reason", "completado")
        logger.info("[Supervisor] %s → END (%s)", claim_id, reason)
        return END

    # 2. HITL pendiente
    if state.get("hitl_required") and state.get("resolution") is None:
        logger.info("[Supervisor] %s → hitl", claim_id)
        return "hitl"

    # 3-4. Validación documental
    if state.get("validation_result") is None:
        logger.info("[Supervisor] %s → document_validator", claim_id)
        return "document_validator"

    if not state["validation_result"].get("is_valid"):
        logger.info("[Supervisor] %s → END (docs incompletos)", claim_id)
        return END

    # 5-6. Fraude / compliance
    if state.get("fraud_result") is None:
        logger.info("[Supervisor] %s → fraud_compliance", claim_id)
        return "fraud_compliance"

    if state["fraud_result"].get("is_flagged"):
        logger.info("[Supervisor] %s → END (caso bloqueado por fraude/OFAC)", claim_id)
        return END

    # 7. Extracción multimodal
    if state.get("extraction_result") is None:
        logger.info("[Supervisor] %s → multimodal_extractor", claim_id)
        return "multimodal_extractor"

    # 8. Verificación de cobertura
    if state.get("coverage_result") is None:
        logger.info("[Supervisor] %s → coverage_checker", claim_id)
        return "coverage_checker"

    # 9. Resolución final
    if state.get("resolution") is None:
        logger.info("[Supervisor] %s → claim_resolver", claim_id)
        return "claim_resolver"

    # 10. Nada pendiente
    logger.info("[Supervisor] %s → END (flujo completo)", claim_id)
    return END


# ── Construcción del grafo ─────────────────────────────────────────────────

def build_orchestrator():
    from app.agents.document_validator   import document_validator_node
    from app.agents.fraud_compliance     import fraud_compliance_node
    from app.agents.multimodal_extractor import multimodal_extractor_node
    from app.agents.coverage_checker     import coverage_checker_node
    from app.agents.claim_resolver       import claim_resolver_node

    graph = StateGraph(ClaimState)

    # ── Nodos ──────────────────────────────────────────────────────────────
    graph.add_node("triage",               triage_node)
    graph.add_node("hitl",                 hitl_node)
    graph.add_node("document_validator",   document_validator_node)
    graph.add_node("fraud_compliance",     fraud_compliance_node)
    graph.add_node("multimodal_extractor", multimodal_extractor_node)
    graph.add_node("coverage_checker",     coverage_checker_node)
    graph.add_node("claim_resolver",       claim_resolver_node)

    # ── Punto de entrada ──────────────────────────────────────────────────
    graph.set_entry_point("triage")

    # ── Tras triage → supervisor decide ────────────────────────────────────
    graph.add_conditional_edges("triage", supervisor_router, {
        "document_validator":   "document_validator",
        "fraud_compliance":     "fraud_compliance",
        "multimodal_extractor": "multimodal_extractor",
        "coverage_checker":     "coverage_checker",
        "claim_resolver":       "claim_resolver",
        "hitl":                 "hitl",
        END:                    END,
    })

    # ── Cada agente vuelve al supervisor ──────────────────────────────────
    spoke_destinations = {
        "document_validator":   "document_validator",
        "fraud_compliance":     "fraud_compliance",
        "multimodal_extractor": "multimodal_extractor",
        "coverage_checker":     "coverage_checker",
        "claim_resolver":       "claim_resolver",
        "hitl":                 "hitl",
        END:                    END,
    }
    for agent in ["document_validator", "fraud_compliance",
                  "multimodal_extractor", "coverage_checker",
                  "claim_resolver"]:
        graph.add_conditional_edges(agent, supervisor_router, spoke_destinations)

    # ── hitl es terminal ──────────────────────────────────────────────────
    graph.add_edge("hitl", END)

    return graph.compile()


# ── API pública ────────────────────────────────────────────────────────────

orchestrator = build_orchestrator()


async def process_claim(
    claim_id:         str,
    claim_text:       str,
    client_id:        str        = "UNKNOWN",
    client_email:     str        = "cliente@example.com",
    claim_type:       str        = "default",
    amount_requested: float      = 0.0,
    documents:        list[str] | None = None,
) -> ClaimState:
    """
    Punto de entrada público del sistema.

    Args:
        claim_id:         Identificador único del expediente.
        claim_text:       Texto bruto de la reclamación (correo, formulario).
        client_id:        ID del cliente para cribado OFAC.
        client_email:     Email del cliente para notificaciones.
        claim_type:       Tipo de siniestro si ya viene clasificado.
        amount_requested: Importe reclamado si ya está estructurado.
        documents:        Lista de documentos aportados.

    Returns:
        Estado final del expediente con la decisión y la traza CoT.
    """
    initial_state: ClaimState = {
        "claim_id":           claim_id,
        "client_id":          client_id,
        "client_email":       client_email,
        "messages":           [HumanMessage(content=claim_text)],
        "claim_type":         claim_type,
        "amount_requested":   amount_requested,
        "documents":          documents or [],
        "validation_result":  None,
        "fraud_result":       None,
        "extraction_result":  None,
        "coverage_result":    None,
        "resolution":         None,
        "status":             ClaimStatus.OPEN,
        "hitl_required":      False,
        "terminate":          False,
        "termination_reason": None,
    }
    return await orchestrator.ainvoke(initial_state)
