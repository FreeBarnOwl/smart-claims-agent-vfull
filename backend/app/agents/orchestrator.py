"""
Orchestrator — Agente A del sistema Smart-Claims de Seguros Pepin.

Implementa el patron Supervisor (Hub-and-Spoke) sobre LangGraph. El
supervisor es el UNICO componente que decide el flujo: lee el estado
acumulado y enruta al siguiente agente. Los agentes son nodos puros que
hacen su trabajo y devuelven el control al supervisor.

Mapa de agentes (referencia memoria TFM):
    Agente A → orchestrator.py          (este fichero, supervisor)
    Agente B → document_validator.py
    Agente C → multimodal_extractor.py
    Agente D → coverage_checker.py
    Agente E → claim_resolver.py
    Agente G → fraud_compliance.py

La persistencia de decisiones es centralizada: cada agente acumula su
contribucion en decisions_log durante la ejecucion del grafo, y al
finalizar process_claim persiste todo en MariaDB en una unica transaccion.
Si la BD no esta disponible, la persistencia falla silenciosamente y el
flujo devuelve igualmente el resultado (resiliencia para la demo).
"""
from __future__ import annotations

import logging
import math

from langgraph.graph import END, StateGraph

from app.agents.claim_resolver       import claim_resolver_node
from app.agents.coverage_checker     import coverage_checker_node
from app.agents.document_validator   import document_validator_node
from app.agents.fraud_compliance     import fraud_compliance_node
from app.agents.multimodal_extractor import multimodal_extractor_node
from app.agents.reasoning            import reason, claim_type_label
from app.agents.state                import ClaimState
from app.db.models                   import ClaimStatus
from app.db.repository               import log_agent_decision, save_claim
from app.tools.claim_tools           import REQUIRED_DOCS_BY_TYPE

logger = logging.getLogger(__name__)

MAX_AMOUNT_REQUESTED  = 10_000_000
MAX_CLIENT_NAME_LEN   = 200
CLAIM_TYPE_CATALOG    = frozenset(REQUIRED_DOCS_BY_TYPE) - {"default"}


# ── Validacion de entrada (blindaje A1) ───────────────────────────────────

def validate_claim_input(claim_type, amount_requested, client_name, documents) -> dict:
    """
    Valida y normaliza los datos de entrada de un expediente ANTES de
    iniciar el flujo de agentes.

    Devuelve un dict:
    - Si los datos son invalidos: {"valid": False, "decision", "status",
      "hitl_required", "termination_reason"} — el expediente debe cortarse
      de inmediato (terminate=True) sin invocar a ningun agente especialista.
    - Si son validos: {"valid": True, "client_name" (normalizado),
      "documents" (deduplicados, preservando el orden de aparicion)}.
    """
    # 1. Importe: numerico, finito, > 0 y < 10.000.000
    if (
        isinstance(amount_requested, bool)
        or not isinstance(amount_requested, (int, float))
        or not math.isfinite(amount_requested)
        or amount_requested <= 0
        or amount_requested >= MAX_AMOUNT_REQUESTED
    ):
        return {
            "valid":              False,
            "status":             ClaimStatus.REJECTED.value,
            "decision":           "RECHAZO",
            "hitl_required":      False,
            "termination_reason": f"importe reclamado invalido: {amount_requested!r}",
        }

    # 2. Tipo de siniestro: debe pertenecer al catalogo conocido
    if claim_type not in CLAIM_TYPE_CATALOG:
        return {
            "valid":              False,
            "status":             ClaimStatus.PENDING_REVIEW.value,
            "decision":           "REVISION_HUMANA",
            "hitl_required":      True,
            "termination_reason": f"tipo de siniestro no reconocido: {claim_type!r}",
        }

    # 3. Nombre del asegurado: no vacio, <= 200 caracteres, normalizado
    normalized_name = (client_name or "").strip()
    if not normalized_name or len(normalized_name) > MAX_CLIENT_NAME_LEN:
        return {
            "valid":              False,
            "status":             ClaimStatus.PENDING_REVIEW.value,
            "decision":           "REVISION_HUMANA",
            "hitl_required":      True,
            "termination_reason": "nombre del asegurado invalido (vacio o excesivamente largo)",
        }

    # 4. Documentos: deduplicar antes de que el Agente B cuente completitud
    deduped_documents = list(dict.fromkeys(documents or []))

    return {
        "valid":       True,
        "client_name": normalized_name,
        "documents":   deduped_documents,
    }


# ── Nodo de triaje (entrada al grafo) ─────────────────────────────────────

async def triage_node(state: dict) -> dict:
    """
    Agente A — triaje inicial del expediente.

    No decide enrutamiento (de eso se ocupa el supervisor); su rol es
    validar los datos de entrada, enriquecer el estado con el razonamiento
    de bienvenida y dejar el expediente listo para el primer agente
    especialista.
    """
    claim_id = state["claim_id"]
    logger.info("[Agente A — Orchestrator] Triaje iniciado — expediente %s", claim_id)

    validation = validate_claim_input(
        claim_type=state.get("claim_type"),
        amount_requested=state.get("amount_requested"),
        client_name=state.get("client_name"),
        documents=state.get("documents"),
    )

    if not validation["valid"]:
        logger.warning(
            "[Agente A] Validacion de entrada fallida — expediente %s: %s",
            claim_id, validation["termination_reason"],
        )
        reasoning = (
            f"Agente A: el expediente {claim_id} no supera la validacion de "
            f"entrada ({validation['termination_reason']}). Se corta el flujo "
            f"sin invocar a los agentes especialistas."
        )
        return {
            "status":             validation["status"],
            "decision":           validation["decision"],
            "hitl_required":      validation["hitl_required"],
            "terminate":          True,
            "termination_reason": validation["termination_reason"],
            "reasoning_trace":    [reasoning],
            "decisions_log":      [{
                "agent":         "agent_a_orchestrator",
                "action":        "validacion_entrada_fallida",
                "reasoning":     reasoning,
                "confidence":    None,
                "hitl_required": validation["hitl_required"],
            }],
        }

    claim_type_es = claim_type_label(state.get("claim_type"))

    fallback = (
        f"Agente A: expediente {claim_id} de tipo '{claim_type_es}' "
        f"por importe {state.get('amount_requested') or 0} EUR. Se inicia el "
        f"flujo de procesamiento con cribado antifraude como filtro de entrada."
    )

    reasoning = reason(
        system=(
            "Eres el Agente A (Orchestrator) del sistema Smart-Claims de "
            "Seguros Pepin. Tu rol es analizar el expediente entrante y "
            "razonar el triaje. Responde siempre en castellano."
        ),
        prompt=(
            f"Reclamacion recibida:\n"
            f"- ID: {state.get('claim_id')}\n"
            f"- Cliente: {state.get('client_id')}\n"
            f"- Tipo: {claim_type_es}\n"
            f"- Importe: {state.get('amount_requested')}\n"
            f"- Canal: {state.get('channel')}\n"
            f"- Documentos aportados: {state.get('documents')}\n\n"
            f"Razona el triaje paso a paso."
        ),
        fallback=fallback,
    )

    return {
        "status":          ClaimStatus.OPEN.value,
        "client_name":     validation["client_name"],
        "documents":       validation["documents"],
        "reasoning_trace": [reasoning],
        "decisions_log":   [{
            "agent":         "agent_a_orchestrator",
            "action":        "triage",
            "reasoning":     reasoning,
            "confidence":    None,
            "hitl_required": False,
        }],
    }


# ── SUPERVISOR — el cerebro del enrutamiento ──────────────────────────────

def supervisor_router(state: dict) -> str:
    """
    Nucleo del patron Hub-and-Spoke.

    Lee el estado acumulado y decide DETERMINISTICAMENTE el proximo agente.
    Ningun agente tiene su propio router: todos retornan aqui.

    Orden de evaluacion:
    1.  Flujo terminado          → END
    2.  Validacion pendiente     → document_validator (Agente B)
    3.  Documentos incompletos   → END (cliente notificado)
    4.  Extraccion pendiente     → multimodal_extractor (Agente C)
    5.  Cribado fraude pendiente → fraud_compliance (Agente G)
    6.  Cliente flagged          → END (caso bloqueado)
    7.  Cobertura pendiente      → coverage_checker (Agente D)
    8.  Resolucion pendiente     → claim_resolver (Agente E)
    9.  Todo completo            → END
    """
    claim_id = state.get("claim_id", "?")

    # 1. Terminacion explicita (rechazo, pago aprobado, HITL activado)
    if state.get("terminate"):
        reason_term = state.get("termination_reason", "completado")
        logger.info("[Supervisor] %s → END (%s)", claim_id, reason_term)
        return END

    # 2. Recepción: validación documental
    if state.get("validation_result") is None:
        logger.info("[Supervisor] %s → document_validator", claim_id)
        return "document_validator"

    if not state["validation_result"].get("is_valid"):
        logger.info("[Supervisor] %s → END (documentacion incompleta)", claim_id)
        return END

    # 3. Extracción multimodal (necesita documentación válida)
    if state.get("extraction_result") is None:
        logger.info("[Supervisor] %s → multimodal_extractor", claim_id)
        return "multimodal_extractor"

    # 4. Cribado de fraude/cumplimiento — gate previo a la resolución.
    #    Se ejecuta tras la recepción documental para que los 4 detectores
    #    (incluida la coherencia documental) dispongan de los datos extraídos.
    if state.get("fraud_result") is None:
        logger.info("[Supervisor] %s → fraud_compliance", claim_id)
        return "fraud_compliance"

    if state["fraud_result"].get("is_flagged"):
        logger.info("[Supervisor] %s → END (bloqueado por fraude/OFAC)", claim_id)
        return END

    # 5. Verificacion de cobertura
    if state.get("coverage_result") is None:
        logger.info("[Supervisor] %s → coverage_checker", claim_id)
        return "coverage_checker"

    # 6. Resolucion final
    if state.get("resolution") is None:
        logger.info("[Supervisor] %s → claim_resolver", claim_id)
        return "claim_resolver"

    # 7. Nada pendiente
    logger.info("[Supervisor] %s → END (flujo completo)", claim_id)
    return END


# ── Construccion del grafo ────────────────────────────────────────────────

def build_orchestrator():
    graph = StateGraph(ClaimState)

    # Nodos: 1 hub + 5 agentes especialistas
    graph.add_node("triage",               triage_node)
    graph.add_node("fraud_compliance",     fraud_compliance_node)
    graph.add_node("document_validator",   document_validator_node)
    graph.add_node("multimodal_extractor", multimodal_extractor_node)
    graph.add_node("coverage_checker",     coverage_checker_node)
    graph.add_node("claim_resolver",       claim_resolver_node)

    # Entrada
    graph.set_entry_point("triage")

    # Tras triaje: el supervisor decide
    spoke_destinations = {
        "fraud_compliance":     "fraud_compliance",
        "document_validator":   "document_validator",
        "multimodal_extractor": "multimodal_extractor",
        "coverage_checker":     "coverage_checker",
        "claim_resolver":       "claim_resolver",
        END:                    END,
    }
    graph.add_conditional_edges("triage", supervisor_router, spoke_destinations)

    # Cada agente vuelve al supervisor (Hub-and-Spoke)
    for agent in ["fraud_compliance", "document_validator", "multimodal_extractor",
                  "coverage_checker", "claim_resolver"]:
        graph.add_conditional_edges(agent, supervisor_router, spoke_destinations)

    return graph.compile()


orchestrator = build_orchestrator()


# ── Normalizacion del estado final ────────────────────────────────────────

def _normalize_final_state(final: dict) -> dict:
    """
    Garantiza que el estado final tiene un `status` y un `decision`
    coherentes con el resultado del flujo.

    Hay tres casos en los que el flujo se corta sin que un agente actualice
    explicitamente el status (que se quedaria en "open" tras el triaje):

    1. El cribado de fraude marca el caso como flagged.
    2. La validacion documental detecta documentos incompletos.
    3. Cualquier otra ruta que termine en END sin pasar por claim_resolver.

    Esta funcion deduce el status correcto a partir de los resultados
    parciales acumulados en el estado.
    """
    current_status = final.get("status")

    # Si el resolver ya ha establecido un status final, no lo tocamos
    if current_status not in (None, "", ClaimStatus.OPEN.value):
        return final

    # Caso 1: caso marcado por el cribado de fraude (Agente G)
    fraud_result = final.get("fraud_result") or {}
    if fraud_result.get("is_flagged"):
        if fraud_result.get("verdict") == "BLOCKED":
            # Coincidencia OFAC confirmada → rechazo automatico
            final["status"]             = ClaimStatus.REJECTED.value
            final["decision"]           = "RECHAZO_FRAUDE"
            final["termination_reason"] = final.get("termination_reason") or "caso bloqueado por fraude/OFAC"
        else:
            # HIGH_RISK: score probabilistico → ninguna decision adversa sin
            # supervision humana (memoria §5.3/§5.4, EU AI Act)
            final["status"]             = ClaimStatus.PENDING_REVIEW.value
            final["decision"]           = "REVISION_HUMANA"
            final["hitl_required"]      = True
            final["termination_reason"] = (
                final.get("termination_reason")
                or "derivado a revision humana por alto riesgo de fraude"
            )
        return final

    # Caso 2: documentacion incompleta
    validation = final.get("validation_result") or {}
    if validation and not validation.get("is_valid"):
        final["status"]             = ClaimStatus.VALIDATING.value
        final["decision"]           = "INFO_REQUERIDA"
        final["termination_reason"] = (
            final.get("termination_reason")
            or f"documentacion incompleta: faltan {', '.join(validation.get('missing_docs', []))}"
        )
        return final

    # Caso 3: el resolver ya habra escrito su status; si no, queda en open
    return final


# ── API publica ───────────────────────────────────────────────────────────

async def process_claim(
    claim_id:         str,
    client_id:        str,
    claim_type:       str,
    amount_requested: float | None    = None,
    channel:          str             = "email",
    documents:        list[str] | None = None,
    client_email:     str             = "cliente@example.com",
    client_name:      str | None      = None,
    uploaded_files:   list[dict] | None = None,
) -> dict:
    """
    Procesa un expediente a traves del grafo de agentes y persiste las
    decisiones en MariaDB.

    La persistencia esta envuelta en try/except: si no hay base de datos
    disponible (p. ej. la CLI de demo sin MariaDB), el flujo devuelve
    igualmente su resultado. Es una propiedad clave de resiliencia para
    la demostracion ante tribunal.
    """
    initial: ClaimState = {
        "claim_id":         claim_id,
        "client_id":        client_id,
        "client_name":      client_name or client_id,
        "client_email":     client_email,
        "claim_type":       claim_type,
        "amount_requested": amount_requested,
        "channel":          channel,
        "documents":        documents or [],
        "uploaded_files":   uploaded_files or [],
        "reasoning_trace":  [],
        "decisions_log":    [],
    }

    try:
        final = await orchestrator.ainvoke(initial)
    except Exception:
        # Cualquier fallo no controlado dentro del grafo (bug, timeout no
        # capturado por un nodo, dependencia caida) nunca debe propagarse:
        # el expediente se deriva a revision humana con un motivo legible.
        # El detalle real de la excepcion se registra SOLO en el log del
        # servidor, nunca en el estado devuelto (ni en decisions_log ni en
        # reasoning_trace), para no filtrarlo a la UI ni a la API.
        logger.exception("Fallo interno no controlado procesando %s", claim_id)
        error_reasoning = (
            f"Agente A: se ha producido un error interno no controlado al "
            f"procesar el expediente {claim_id}. Por seguridad, el expediente "
            f"se deriva a revision humana."
        )
        final = {
            **initial,
            "status":             ClaimStatus.PENDING_REVIEW.value,
            "decision":           "REVISION_HUMANA",
            "hitl_required":      True,
            "terminate":          True,
            "termination_reason": "error_interno_controlado",
            "reasoning_trace":    initial["reasoning_trace"] + [error_reasoning],
            "decisions_log":      initial["decisions_log"] + [{
                "agent":         "agent_a_orchestrator",
                "action":        "error_interno_controlado",
                "reasoning":     error_reasoning,
                "confidence":    None,
                "hitl_required": True,
            }],
        }

    # Normaliza status y decision cuando el flujo se ha cortado sin pasar
    # por el claim_resolver (fraude detectado, documentos incompletos, etc.)
    final = _normalize_final_state(final)

    # Persistencia best-effort: si falla, la demo no se rompe
    try:
        await save_claim(
            claim_id         = claim_id,
            client_id        = client_id,
            claim_type       = claim_type,
            channel          = channel,
            amount_requested = amount_requested,
            amount_approved  = (final.get("resolution") or {}).get("amount_paid"),
            status           = ClaimStatus(final.get("status", ClaimStatus.OPEN.value)),
        )
        for d in final.get("decisions_log", []):
            await log_agent_decision(
                claim_id      = claim_id,
                agent         = d["agent"],
                action        = d["action"],
                reasoning     = d["reasoning"],
                confidence    = d.get("confidence"),
                hitl_required = d.get("hitl_required", False),
            )
    except Exception as exc:
        logger.warning("No se han podido persistir las decisiones de %s: %s",
                       claim_id, exc)

    return final
