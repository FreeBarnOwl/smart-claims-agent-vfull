"""
Tests del flujo de orquestacion completo.

Cubre los 4 escenarios principales del sistema:
- Pago automatico (cobertura + importe bajo + docs completos)
- HITL (cobertura + importe alto)
- Rechazo por no cobertura
- Solicitud de informacion por documentos incompletos

Los tests usan SQLite en memoria para evitar dependencia de MariaDB.
"""
import os
import random

import httpx
import pytest

import app.agents.orchestrator as orchestrator_module
from app.agents.orchestrator import process_claim


# Sin LLM externo: tests rapidos y deterministas
os.environ.pop("ANTHROPIC_API_KEY", None)

# Semilla fija para que check_fraud (mock random) sea reproducible.
random.seed(7)


FULL_DOCS = ["foto_danys", "factura", "denuncia_companyia"]


@pytest.mark.asyncio
async def test_flow_automatic_payment(test_db):
    """Cobertura OK + importe bajo + docs completos → PAGO automatico."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-PAY",
        client_id        = "C-A",
        claim_type       = "danys_propis",
        amount_requested = 3200.0,
        documents        = FULL_DOCS,
    )

    assert result["status"]                  == "resolved"
    assert result["decision"]                == "PAGO"
    assert result["resolution"]["amount_paid"] is not None
    assert result["resolution"]["amount_paid"] > 0


@pytest.mark.asyncio
async def test_flow_hitl_high_amount(test_db):
    """Cobertura OK + importe alto → REVISION HUMANA."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-HITL",
        client_id        = "C-B",
        claim_type       = "responsabilitat",
        amount_requested = 9500.0,
        documents        = ["foto_danys", "acta_policial", "dades_tercer"],
    )

    assert result["status"]        == "pending_review"
    assert result["decision"]      == "REVISION_HUMANA"
    assert result["hitl_required"] is True


@pytest.mark.asyncio
async def test_flow_rejection_no_coverage(test_db):
    """Tipo no cubierto → RECHAZO justificado."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-REJ",
        client_id        = "C-C",
        claim_type       = "danys_mecanics",
        amount_requested = 1500.0,
        documents        = ["informe_taller", "factura"],
    )

    assert result["status"]   == "rejected"
    assert result["decision"] == "RECHAZO"


@pytest.mark.asyncio
async def test_flow_request_info_missing_docs(test_db):
    """Documentos incompletos → cliente notificado, flujo cortado."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-INFO",
        client_id        = "C-D",
        claim_type       = "danys_propis",
        amount_requested = 2500.0,
        documents        = ["foto_danys"],   # faltan factura y denuncia
    )

    assert result["validation_result"]["is_valid"] is False
    assert "factura" in result["validation_result"]["missing_docs"]
    # El flujo no llega al claim_resolver
    assert result.get("resolution") is None


@pytest.mark.asyncio
async def test_process_claim_handles_internal_error_gracefully(test_db, monkeypatch):
    """Una excepcion no controlada dentro del grafo NO debe propagarse: debe
    derivar a REVISION_HUMANA con motivo legible (blindaje A2)."""
    random.seed(7)

    class _FailingGraph:
        async def ainvoke(self, *args, **kwargs):
            raise RuntimeError("fallo interno simulado")

    monkeypatch.setattr(orchestrator_module, "orchestrator", _FailingGraph())

    result = await process_claim(
        claim_id         = "CLM-ERR",
        client_id        = "C-ERR",
        claim_type       = "danys_propis",
        amount_requested = 1000.0,
        documents        = FULL_DOCS,
    )

    assert result["status"]             == "pending_review"
    assert result["decision"]           == "REVISION_HUMANA"
    assert result["hitl_required"]      is True
    assert result["termination_reason"] == "error_interno_controlado"

    agents_invoked = [d["agent"] for d in result["decisions_log"]]
    assert "agent_a_orchestrator" in agents_invoked
    # El mensaje interno de la excepcion NUNCA debe filtrarse al reasoning/UI.
    for entry in result["decisions_log"]:
        assert "fallo interno simulado" not in (entry.get("reasoning") or "")


@pytest.mark.asyncio
async def test_invalid_amount_is_rejected_without_calling_specialist_agents(test_db):
    """Importe invalido (negativo) → RECHAZO inmediato en el triaje, sin
    invocar a los agentes especialistas (blindaje A1)."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-BADAMOUNT",
        client_id        = "C-BADAMOUNT",
        claim_type       = "danys_propis",
        amount_requested = -500.0,
        documents        = FULL_DOCS,
    )

    assert result["status"]   == "rejected"
    assert result["decision"] == "RECHAZO"
    agents_invoked = [d["agent"] for d in result["decisions_log"]]
    assert agents_invoked == ["agent_a_orchestrator"]


@pytest.mark.asyncio
async def test_unknown_claim_type_routes_to_human_review_without_specialists(test_db):
    """Tipo de siniestro fuera de catalogo → REVISION_HUMANA inmediata en el
    triaje, sin invocar a los agentes especialistas (blindaje A1)."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-BADTYPE",
        client_id        = "C-BADTYPE",
        claim_type       = "tipo_inventado",
        amount_requested = 1000.0,
        documents        = FULL_DOCS,
    )

    assert result["status"]        == "pending_review"
    assert result["decision"]      == "REVISION_HUMANA"
    assert result["hitl_required"] is True
    agents_invoked = [d["agent"] for d in result["decisions_log"]]
    assert agents_invoked == ["agent_a_orchestrator"]


@pytest.mark.asyncio
async def test_duplicate_documents_are_deduplicated_before_validation(test_db):
    """Documentos duplicados no deben contarse dos veces: tras deduplicar
    siguen faltando documentos reales (blindaje A1)."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-DUPDOCS",
        client_id        = "C-DUPDOCS",
        claim_type       = "danys_propis",
        amount_requested = 2500.0,
        documents        = ["foto_danys", "foto_danys", "foto_danys"],
    )

    assert result["validation_result"]["is_valid"] is False
    assert result["validation_result"]["provided_docs"] == ["foto_danys"]


@pytest.mark.asyncio
async def test_flow_completes_with_decision_when_llm_times_out_for_real(test_db, monkeypatch):
    """Blindaje A4 end-to-end: si el LLM agota el timeout con la excepcion
    real del SDK (anthropic.APITimeoutError) en CADA llamada de reasoning,
    el flujo completo debe seguir produciendo una decision (via fallback
    determinista en cada agente), no bloquearse ni propagar el error."""
    import anthropic

    class _FakeChatAnthropic:
        def __init__(self, **kwargs):
            pass

        def invoke(self, messages):
            request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
            raise anthropic.APITimeoutError(request=request)

    import langchain_anthropic
    monkeypatch.setattr(langchain_anthropic, "ChatAnthropic", _FakeChatAnthropic)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key-times-out")

    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-REALTIMEOUT",
        client_id        = "C-REALTIMEOUT",
        claim_type       = "danys_propis",
        amount_requested = 3200.0,
        documents        = FULL_DOCS,
    )

    assert result["status"]                    == "resolved"
    assert result["decision"]                  == "PAGO"
    assert result["resolution"]["amount_paid"] is not None


@pytest.mark.asyncio
async def test_decisions_log_accumulates(test_db):
    """El decisions_log debe contener una entrada por agente invocado."""
    random.seed(7)
    result = await process_claim(
        claim_id         = "CLM-LOG",
        client_id        = "C-E",
        claim_type       = "danys_propis",
        amount_requested = 2500.0,
        documents        = FULL_DOCS,
    )

    # Triage + Fraude + Docs + Extraccion + Cobertura + Resolucion = 6 entradas
    agents_invoked = [d["agent"] for d in result["decisions_log"]]
    assert "agent_a_orchestrator"           in agents_invoked
    assert "agent_b_document_validator"     in agents_invoked
    assert "agent_g_fraud_compliance"       in agents_invoked
    assert "agent_c_multimodal_extractor"   in agents_invoked
    assert "agent_d_coverage_checker"       in agents_invoked
    assert "agent_e_claim_resolver"         in agents_invoked
