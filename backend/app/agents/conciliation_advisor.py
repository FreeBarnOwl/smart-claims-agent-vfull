"""
Conciliation Advisor — Agente F del sistema Smart-Claims de Seguros Pepin.

Demostrador SECUNDARIO, independiente del flujo principal A->B->C->G->D->E.
No es un nodo del grafo LangGraph: el PoC principal (danys_propis) no tiene
fase de negociacion, asi que F no se integra en supervisor_router. Actua
sobre expedientes DPA (danys propios) o RC (responsabilidad civil) que ya
estan en proceso de conciliacion.

Origen del rediseño: la premisa original de Entrega 1 justificaba F como
"prediccion de judicializacion" sobre un supuesto de ~1.000 casos/año. El
cliente (Gerencia de Reclamaciones) corrigio ese dato a ~10 casos/año, sin
historico suficiente para entrenar un modelo. F se rediseña como asistente
de conciliacion por reglas, explicable y sin aprendizaje automatico.

Responsabilidad unica: recomendar la siguiente accion de conciliacion y
sus alertas de riesgo. advise_conciliation() es una funcion PURA y
DETERMINISTA — misma entrada, misma salida. El LLM (helper reason(), con
el mismo patron de fallback determinista que el resto de agentes) solo
enriquece el texto de `reasoning`; nunca decide recommendation, offer_amount,
alerts ni priority.

Frontera HITL: F solo recomienda. No ejecuta pagos, no cambia el estado
del expediente, no persiste decisiones de negocio — eso lo hace un gestor
humano. Cada recomendacion lo deja explicito en su propio texto.
"""
from __future__ import annotations

from app.agents.reasoning import reason

# ── Constantes de negociacion ──────────────────────────────────────────────

INITIAL_OFFER_PCT = 0.65

# % ya ofrecido en cada tramo de negociacion (negotiation_stage).
STAGE_OFFER_PCT = {1: 0.65, 2: 0.75, 3: 0.90}

# Tramo siguiente al que escalar si la oferta del stage actual fue rechazada.
ESCALATION_PCT = {1: 0.75, 2: 0.90}

DAYS_ABANDONMENT_RISK = 30
DAYS_STALLED = 45

HUMAN_EXECUTION_NOTE = "El Agente F solo recomienda: la ejecuta un gestor humano."

_ALERT_ABANDONMENT = "riesgo de cierre por abandono"
_ALERT_STALLED = "expediente estancado — priorizar"
_ALERT_RC_COVERAGE = "riesgo de escalada judicial — revisar con legal"


def _recommend_offer(case: dict) -> tuple[str, float | None]:
    """Determina el texto base de la recomendacion y, si aplica, el
    importe de oferta a formular. No incluye la nota de ejecucion humana
    (se añade una sola vez para todos los casos en advise_conciliation)."""
    stage = case["negotiation_stage"]
    amount = case["amount_claimed"]
    rejected = case.get("last_offer_rejected", False)

    if stage == 0:
        offer_amount = round(amount * INITIAL_OFFER_PCT, 2)
        core = (
            f"Formular oferta inicial ({INITIAL_OFFER_PCT:.0%} = "
            f"{offer_amount:,.2f} EUR)."
        )
        return core, offer_amount

    if stage in ESCALATION_PCT and rejected:
        next_pct = ESCALATION_PCT[stage]
        offer_amount = round(amount * next_pct, 2)
        core = (
            f"Subir al siguiente tramo ({next_pct:.0%} = "
            f"{offer_amount:,.2f} EUR)."
        )
        return core, offer_amount

    if stage == 3 and rejected:
        core = (
            "Decision humana requerida: transar una ultima vez, cierre por "
            "abandono, o derivacion a via judicial externa. El Agente F no "
            "elige entre estas tres opciones: las presenta con los datos "
            "del expediente para que decida un gestor humano."
        )
        return core, None

    current_pct = STAGE_OFFER_PCT.get(stage)
    if current_pct is not None:
        core = (
            f"Esperar respuesta del cliente a la oferta vigente "
            f"({current_pct:.0%})."
        )
    else:
        core = (
            f"Tramo de negociacion no reconocido ({stage!r}); revisar el "
            f"expediente manualmente."
        )
    return core, None


def _collect_alerts(case: dict) -> list[str]:
    alerts = []
    if case.get("days_since_last_client_response", 0) > DAYS_ABANDONMENT_RISK:
        alerts.append(_ALERT_ABANDONMENT)
    if case.get("days_in_current_stage", 0) > DAYS_STALLED:
        alerts.append(_ALERT_STALLED)
    if case["claim_type"] == "rc" and case.get("coverage_sufficient") is False:
        alerts.append(_ALERT_RC_COVERAGE)
    return alerts


def _priority_from_alerts(alerts: list[str]) -> str:
    if len(alerts) >= 2:
        return "alta"
    if len(alerts) == 1:
        return "media"
    return "baja"


def advise_conciliation(case: dict) -> dict:
    """
    Recomienda la siguiente accion de conciliacion para un expediente DPA
    o RC en negociacion.

    Lee de `case`: claim_id, claim_type ('dpa'|'rc'), amount_claimed,
    negotiation_stage (0-3), last_offer_rejected, days_in_current_stage,
    days_since_last_client_response, coverage_sufficient.

    Devuelve: {recommendation, offer_amount, alerts, priority, reasoning}.
    No modifica ningun estado ni ejecuta ninguna accion de negocio.
    """
    claim_id = case["claim_id"]
    claim_type = case["claim_type"]
    stage = case["negotiation_stage"]

    core_recommendation, offer_amount = _recommend_offer(case)
    recommendation = f"{core_recommendation} {HUMAN_EXECUTION_NOTE}"

    alerts = _collect_alerts(case)
    priority = _priority_from_alerts(alerts)

    fallback = (
        f"Agente F: expediente {claim_id} ({claim_type}, tramo {stage}). "
        f"{recommendation} Prioridad: {priority}."
        + (f" Alertas activas: {', '.join(alerts)}." if alerts else " Sin alertas activas.")
    )

    reasoning = reason(
        system=(
            "Eres el Agente F (Conciliation Advisor) del sistema Smart-Claims "
            "de Seguros Pepin. Asistes la conciliacion de expedientes DPA/RC "
            "con recomendaciones explicables basadas en reglas, nunca en "
            "aprendizaje automatico. No decides ni ejecutas: un gestor humano "
            "lo hace siempre. Responde siempre en castellano."
        ),
        prompt=(
            f"Recomendacion de conciliacion:\n"
            f"- Expediente: {claim_id}\n"
            f"- Tipo: {claim_type}\n"
            f"- Tramo de negociacion: {stage}\n"
            f"- Ultima oferta rechazada: {case.get('last_offer_rejected', False)}\n"
            f"- Dias en el tramo actual: {case.get('days_in_current_stage', 0)}\n"
            f"- Dias sin respuesta del cliente: {case.get('days_since_last_client_response', 0)}\n"
            f"- Recomendacion: {recommendation}\n"
            f"- Alertas: {alerts}\n"
            f"- Prioridad: {priority}\n\n"
            f"Redacta el razonamiento para el gestor humano que revisara este expediente."
        ),
        fallback=fallback,
    )

    return {
        "recommendation": recommendation,
        "offer_amount":   offer_amount,
        "alerts":         alerts,
        "priority":       priority,
        "reasoning":      reasoning,
    }
