from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import process_claim
from app.db.repository import get_claim_with_decisions

router = APIRouter()


class ClaimRequest(BaseModel):
    claim_id: str
    client_id: str
    claim_type: str
    channel: str = "email"
    text: str
    amount_requested: float | None = None
    doc_types: list[str] = []


class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str
    decision: str | None = None
    hitl_required: bool = False
    reasoning_trace: list[str] = []


@router.post("/", response_model=ClaimResponse)
async def create_claim(claim: ClaimRequest):
    result = await process_claim(
        claim.claim_id,
        claim.client_id,
        claim.claim_type,
        claim.amount_requested,
        claim.channel,
        claim.doc_types,
    )
    return ClaimResponse(
        claim_id=claim.claim_id,
        status=result.get("status", "open"),
        message="Reclamació processada.",
        decision=result.get("decision"),
        hitl_required=result.get("hitl_required", False),
        reasoning_trace=result.get("reasoning_trace", []),
    )


@router.get("/{claim_id}")
async def get_claim(claim_id: str):
    claim = await get_claim_with_decisions(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Expedient no trobat")
    return claim
