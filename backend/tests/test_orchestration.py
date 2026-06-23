import pytest

from app.agents.orchestrator import process_claim

FULL_DOCS = ["foto_danys", "factura", "acta_policial"]


@pytest.fixture
def no_fraud(monkeypatch):
    # Força risc baix → check_fraud no marca frau (determinista).
    monkeypatch.setattr("app.tools.claim_tools.random.uniform", lambda a, b: 0.05)


@pytest.fixture
def fraud_flagged(monkeypatch):
    # Força risc alt → check_fraud marca frau.
    monkeypatch.setattr("app.tools.claim_tools.random.uniform", lambda a, b: 0.5)


@pytest.mark.asyncio
async def test_flow_auto_payment(test_db, no_fraud):
    res = await process_claim("CLM-001", "C-A", "danys_propis", 3200.0, "email", FULL_DOCS)
    assert res["decision"] == "PAGO"
    assert res["hitl_required"] is False


@pytest.mark.asyncio
async def test_flow_hitl_over_threshold(test_db, no_fraud):
    res = await process_claim("CLM-002", "C-B", "responsabilitat", 8500.0, "web", FULL_DOCS)
    assert res["hitl_required"] is True
    assert res["decision"] == "REVISIÓN_HUMANA"


@pytest.mark.asyncio
async def test_flow_rejection_no_coverage(test_db, no_fraud):
    res = await process_claim("CLM-9", "C-Z", "danys_mecànics", 1000.0, "email", FULL_DOCS)
    assert res["decision"] == "RECHAZO"


@pytest.mark.asyncio
async def test_flow_request_info_when_docs_missing(test_db, no_fraud):
    res = await process_claim("CLM-3", "C-D", "danys_propis", 1000.0, "email", ["factura"])
    assert res["decision"] == "SOLICITUD_INFO"


@pytest.mark.asyncio
async def test_flow_fraud_routes_to_hitl(test_db, fraud_flagged):
    res = await process_claim("CLM-F", "C-F", "danys_propis", 1000.0, "email", FULL_DOCS)
    assert res["hitl_required"] is True


@pytest.mark.asyncio
async def test_decisions_are_persisted(test_db, no_fraud):
    from app.db.repository import get_claim_with_decisions
    await process_claim("CLM-P", "C-P", "danys_propis", 3200.0, "email", FULL_DOCS)
    claim = await get_claim_with_decisions("CLM-P")
    assert claim is not None
    assert len(claim["decisions"]) >= 5  # triage, fraud, validate, extract, policy, resolve
