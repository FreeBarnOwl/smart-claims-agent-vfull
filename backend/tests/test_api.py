import pytest


@pytest.fixture
def no_fraud(monkeypatch):
    monkeypatch.setattr("app.tools.claim_tools.random.uniform", lambda a, b: 0.05)


@pytest.mark.asyncio
async def test_create_claim_returns_payment_decision(test_db, no_fraud):
    from app.routers.claims import create_claim, ClaimRequest
    req = ClaimRequest(claim_id="CLM-API", client_id="C-1", claim_type="danys_propis",
                       channel="email", text="Reclamació de prova",
                       amount_requested=3200.0,
                       doc_types=["foto_danys", "factura", "acta_policial"])
    resp = await create_claim(req)
    assert resp.decision == "PAGO"
    assert resp.hitl_required is False
    assert len(resp.reasoning_trace) >= 1


@pytest.mark.asyncio
async def test_get_unknown_claim_404(test_db):
    from fastapi import HTTPException
    from app.routers.claims import get_claim
    with pytest.raises(HTTPException) as exc:
        await get_claim("NOPE")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_then_get_claim(test_db, no_fraud):
    from app.routers.claims import create_claim, get_claim, ClaimRequest
    req = ClaimRequest(claim_id="CLM-RT", client_id="C-2", claim_type="danys_propis",
                       channel="email", text="x", amount_requested=3200.0,
                       doc_types=["foto_danys", "factura", "acta_policial"])
    await create_claim(req)
    got = await get_claim("CLM-RT")
    assert got["claim_id"] == "CLM-RT"
    assert len(got["decisions"]) >= 5
