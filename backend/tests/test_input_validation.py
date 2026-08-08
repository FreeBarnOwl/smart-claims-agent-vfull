"""
Tests de validate_claim_input() — blindaje A1: valida y normaliza los datos
de entrada de un expediente antes de iniciar el flujo de agentes.
"""
import math

from app.agents.orchestrator import validate_claim_input


VALID_TYPE = "danys_propis"
VALID_NAME = "Juan Garcia"
VALID_DOCS = ["foto_danys", "factura"]


def _validate(**overrides):
    kwargs = {
        "claim_type":       VALID_TYPE,
        "amount_requested": 1000.0,
        "client_name":      VALID_NAME,
        "documents":        VALID_DOCS,
    }
    kwargs.update(overrides)
    return validate_claim_input(**kwargs)


def test_valid_input_is_accepted():
    result = _validate()
    assert result["valid"] is True
    assert result["client_name"] == VALID_NAME
    assert result["documents"]   == VALID_DOCS


def test_rejects_nan_amount():
    result = _validate(amount_requested=math.nan)
    assert result["valid"]    is False
    assert result["decision"] == "RECHAZO"


def test_rejects_infinite_amount():
    result = _validate(amount_requested=math.inf)
    assert result["valid"]    is False
    assert result["decision"] == "RECHAZO"


def test_rejects_negative_amount():
    result = _validate(amount_requested=-100.0)
    assert result["valid"]    is False
    assert result["decision"] == "RECHAZO"


def test_rejects_zero_amount():
    result = _validate(amount_requested=0.0)
    assert result["valid"]    is False
    assert result["decision"] == "RECHAZO"


def test_rejects_amount_over_ten_million():
    result = _validate(amount_requested=10_000_001.0)
    assert result["valid"]    is False
    assert result["decision"] == "RECHAZO"


def test_rejects_non_numeric_amount():
    result = _validate(amount_requested=None)
    assert result["valid"]    is False
    assert result["decision"] == "RECHAZO"


def test_unknown_claim_type_routes_to_human_review():
    result = _validate(claim_type="tipo_inventado")
    assert result["valid"]         is False
    assert result["decision"]      == "REVISION_HUMANA"
    assert result["hitl_required"] is True


def test_rejects_empty_client_name():
    result = _validate(client_name="")
    assert result["valid"]    is False
    assert result["decision"] == "REVISION_HUMANA"


def test_rejects_whitespace_only_client_name():
    result = _validate(client_name="   ")
    assert result["valid"]    is False
    assert result["decision"] == "REVISION_HUMANA"


def test_rejects_client_name_over_200_chars():
    result = _validate(client_name="A" * 201)
    assert result["valid"]    is False
    assert result["decision"] == "REVISION_HUMANA"


def test_normalizes_client_name_whitespace():
    result = _validate(client_name="  Juan Garcia  ")
    assert result["valid"]     is True
    assert result["client_name"] == "Juan Garcia"


def test_deduplicates_documents():
    result = _validate(documents=["factura", "foto_danys", "factura"])
    assert result["valid"]     is True
    assert result["documents"] == ["factura", "foto_danys"]
