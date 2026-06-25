"""Tests del 4º detector del Agente G (coherencia documental).

Verifica que, tras reordenar el flujo (la extracción precede al cribado de
fraude), el detector de coherencia documental recibe las fechas extraídas y
dispara ante inconsistencias.
"""
import os

import pytest

os.environ.pop("ANTHROPIC_API_KEY", None)  # fallback determinista, sin LLM

from app.agents.fraud_compliance import fraud_compliance_node


def _extraction(acta_date: str, factura_date: str) -> dict:
    return {"by_document": {
        "acta_policial": {"doc_type": "acta_policial", "extracted": {"incident_date": acta_date}},
        "factura":       {"doc_type": "factura",       "extracted": {"date": factura_date}},
    }}


@pytest.mark.asyncio
async def test_doc_coherence_flags_invoice_before_incident():
    state = {"claim_id": "CLM-INC", "client_id": "C-X", "claim_type": "danys_propis",
             "amount_requested": 1000.0,
             "extraction_result": _extraction("2026-05-08", "2026-01-01")}
    out = await fraud_compliance_node(state)
    doc = out["fraud_result"]["signals"]["document"]
    assert doc["incoherent"] is True
    assert any("factura_previa" in issue for issue in doc["issues"])


@pytest.mark.asyncio
async def test_doc_coherence_clean_for_consistent_dates():
    state = {"claim_id": "CLM-OK", "client_id": "C-Y", "claim_type": "danys_propis",
             "amount_requested": 1000.0,
             "extraction_result": _extraction("2026-05-08", "2026-05-10")}
    out = await fraud_compliance_node(state)
    assert out["fraud_result"]["signals"]["document"]["incoherent"] is False
