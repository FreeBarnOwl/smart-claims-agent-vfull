"""
Tests del Document Validator — Agente B del sistema Smart-Claims.

El agente ya NO tiene router propio (patrón Supervisor): el supervisor
del Orchestrator decide siempre el siguiente nodo.
"""
from unittest.mock import patch, MagicMock

from app.db.models import ClaimStatus


def _make_state(claim_type: str = "danys_propis",
                documents:  list[str] | None = None) -> dict:
    from langchain_core.messages import HumanMessage
    return {
        "claim_id":           "TEST-001",
        "client_id":          "CLIENT-A",
        "client_email":       "test@test.com",
        "messages":           [HumanMessage(content=f"Reclamación {claim_type}.")],
        "claim_type":         claim_type,
        "amount_requested":   3200.0,
        "documents":          documents if documents is not None else [],
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


# ── Test 1: documentos completos ──────────────────────────────────────────

@patch("app.agents.document_validator.log_decision")
@patch("app.agents.document_validator._build_llm")
def test_docs_completos_estado_extracting(mock_llm_factory, mock_log):
    from app.agents.document_validator import document_validator_node

    mock_response = MagicMock()
    mock_response.tool_calls = []
    mock_response.content    = "Documentación completa."
    mock_llm_factory.return_value.invoke.return_value = mock_response

    docs = ["foto_danys", "factura", "denuncia_companyia"]
    result = document_validator_node(_make_state("danys_propis", docs))

    assert result["status"] == ClaimStatus.EXTRACTING
    assert result["validation_result"]["is_valid"] is True
    assert result["validation_result"]["missing_docs"] == []


# ── Test 2: documentos incompletos ────────────────────────────────────────

@patch("app.agents.document_validator.log_decision")
@patch("app.agents.document_validator.request_more_info")
@patch("app.agents.document_validator._build_llm")
def test_docs_incompletos_notifica_cliente(mock_llm_factory, mock_request, mock_log):
    from app.agents.document_validator import document_validator_node

    mock_response = MagicMock()
    mock_response.tool_calls = []
    mock_response.content    = "Faltan documentos."
    mock_llm_factory.return_value.invoke.return_value = mock_response

    result = document_validator_node(_make_state("danys_propis", ["foto_danys"]))

    assert result["status"] == ClaimStatus.VALIDATING
    assert result["validation_result"]["is_valid"] is False
    assert "factura" in result["validation_result"]["missing_docs"]
    mock_request.invoke.assert_called_once()


# ── Test 3: tipo de siniestro desconocido usa defaults ────────────────────

def test_tipo_desconocido_usa_default():
    from app.agents.document_validator import REQUIRED_DOCS
    required = REQUIRED_DOCS.get("siniestro_inexistente", REQUIRED_DOCS["default"])
    assert required == REQUIRED_DOCS["default"]
    assert len(required) > 0


# ── Test 4: el agente NO decide el siguiente nodo ─────────────────────────

@patch("app.agents.document_validator.log_decision")
@patch("app.agents.document_validator._build_llm")
def test_agente_no_retorna_routing(mock_llm_factory, mock_log):
    """
    Verifica el cumplimiento del patrón Supervisor: el resultado del
    agente NO contiene ninguna decisión de routing.
    """
    from app.agents.document_validator import document_validator_node

    mock_response = MagicMock()
    mock_response.tool_calls = []
    mock_response.content    = "OK"
    mock_llm_factory.return_value.invoke.return_value = mock_response

    result = document_validator_node(_make_state(
        "danys_propis", ["foto_danys", "factura", "denuncia_companyia"]
    ))

    # No debe haber ningún campo de routing/next_node
    assert "b_next"    not in result
    assert "next_node" not in result
    assert "route"     not in result
