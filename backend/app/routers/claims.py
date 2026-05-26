from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class ClaimRequest(BaseModel):
    claim_id: str
    client_id: str
    claim_type: str
    channel: str = "email"
    text: str
    amount_requested: float | None = None


class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str


@router.post("/", response_model=ClaimResponse)
async def create_claim(claim: ClaimRequest):
    # TODO: invocar l'orquestrador (Agent A) — Entrega 2 S2
    return ClaimResponse(
        claim_id=claim.claim_id,
        status="open",
        message="Reclamació rebuda correctament. Processament pendent.",
    )


@router.get("/{claim_id}")
async def get_claim(claim_id: str):
    # TODO: consultar MariaDB — Entrega 2 S2
    return {"claim_id": claim_id, "status": "open"}
