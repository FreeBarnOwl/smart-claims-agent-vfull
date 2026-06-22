"""
Endpoints REST para la gestión de reclamaciones.

Endpoints:
    POST  /api/v1/claims/                — crea y procesa una reclamación
    GET   /api/v1/claims/                — lista de reclamaciones
    GET   /api/v1/claims/{claim_id}      — detalle de una reclamación
    GET   /api/v1/claims/{claim_id}/trace — Chain of Thought completo
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import process_claim
from app.db.models           import AgentDecision, Claim, ClaimStatus
from app.db.session          import get_db
from app.schemas.claims      import (
    AgentDecisionItem,
    ClaimCreateRequest,
    ClaimListItem,
    ClaimResponse,
    ClaimTraceResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── POST /api/v1/claims/ ──────────────────────────────────────────────────

@router.post("/", response_model=ClaimResponse, status_code=201)
async def create_and_process_claim(
    request: ClaimCreateRequest,
    db:      AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """
    Crea una nueva reclamación y la procesa a través del sistema agéntico.

    El orquestrador (Agente A) coordina la ejecución de los agentes
    especializados (B, G, C, D, E) hasta llegar a una decisión final.
    """
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    logger.info("[API] Nueva reclamación %s | cliente: %s | tipo: %s",
                claim_id, request.client_id, request.claim_type)

    # ── 1. Crear el registro en BD ─────────────────────────────────────────
    claim = Claim(
        id               = claim_id,
        client_id        = request.client_id,
        claim_type       = request.claim_type,
        amount_requested = request.amount_requested,
        status           = ClaimStatus.OPEN,
    )
    db.add(claim)
    await db.commit()
    await db.refresh(claim)

    # ── 2. Ejecutar el grafo de agentes ────────────────────────────────────
    try:
        final_state = await process_claim(
            claim_id         = claim_id,
            claim_text       = request.text,
            client_id        = request.client_id,
            client_email     = request.client_email,
            claim_type       = request.claim_type,
            amount_requested = request.amount_requested,
            documents        = request.documents,
        )
    except Exception as e:
        logger.exception("[API] Error en el orquestador para %s", claim_id)
        claim.status = ClaimStatus.OPEN
        await db.commit()
        raise HTTPException(
            status_code = 500,
            detail      = f"Error procesando la reclamación: {e}",
        )

    # ── 3. Actualizar el registro con el resultado final ───────────────────
    resolution     = final_state.get("resolution") or {}
    amount_paid    = resolution.get("amount_paid")
    final_status   = final_state.get("status", ClaimStatus.OPEN)
    hitl_required  = final_state.get("hitl_required", False)
    decision       = resolution.get("decision")
    term_reason    = final_state.get("termination_reason")

    claim.status = final_status
    if amount_paid is not None:
        claim.amount_approved = amount_paid
    await db.commit()

    logger.info(
        "[API] Reclamación %s procesada — status=%s | decision=%s | HITL=%s",
        claim_id, final_status, decision, hitl_required,
    )

    return ClaimResponse(
        claim_id           = claim_id,
        status             = final_status.value if hasattr(final_status, "value") else str(final_status),
        decision           = decision,
        amount_paid        = amount_paid,
        amount_requested   = request.amount_requested,
        hitl_required      = hitl_required,
        termination_reason = term_reason,
    )


# ── GET /api/v1/claims/{claim_id} ─────────────────────────────────────────

@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: str,
    db:       AsyncSession = Depends(get_db),
) -> ClaimResponse:
    """Devuelve el estado actual de una reclamación."""
    result = await db.execute(select(Claim).where(Claim.id == claim_id))
    claim  = result.scalar_one_or_none()

    if claim is None:
        raise HTTPException(status_code=404, detail=f"Reclamación {claim_id} no encontrada")

    return ClaimResponse(
        claim_id         = claim.id,
        status           = claim.status.value if hasattr(claim.status, "value") else str(claim.status),
        amount_requested = claim.amount_requested,
        amount_paid      = claim.amount_approved,
    )


# ── GET /api/v1/claims/ ───────────────────────────────────────────────────

@router.get("/", response_model=list[ClaimListItem])
async def list_claims(
    status: str | None = Query(default=None, description="Filtrar por estado"),
    limit:  int        = Query(default=20, ge=1, le=100),
    offset: int        = Query(default=0, ge=0),
    db:     AsyncSession = Depends(get_db),
) -> list[ClaimListItem]:
    """Lista las reclamaciones con paginación y filtro opcional por estado."""
    query = select(Claim).order_by(Claim.created_at.desc()).limit(limit).offset(offset)

    if status:
        try:
            status_enum = ClaimStatus(status)
            query = query.where(Claim.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code = 400,
                detail      = f"Estado inválido: {status}. Valores válidos: {[s.value for s in ClaimStatus]}",
            )

    result = await db.execute(query)
    claims = result.scalars().all()

    return [
        ClaimListItem(
            id               = c.id,
            client_id        = c.client_id,
            claim_type       = c.claim_type,
            status           = c.status.value if hasattr(c.status, "value") else str(c.status),
            amount_requested = c.amount_requested,
            amount_approved  = c.amount_approved,
            created_at       = c.created_at,
        )
        for c in claims
    ]


# ── GET /api/v1/claims/{claim_id}/trace ───────────────────────────────────

@router.get("/{claim_id}/trace", response_model=ClaimTraceResponse)
async def get_claim_trace(
    claim_id: str,
    db:       AsyncSession = Depends(get_db),
) -> ClaimTraceResponse:
    """
    Devuelve el Chain of Thought completo de una reclamación:
    todas las decisiones de los agentes en orden cronológico.
    """
    # Verifica que existe
    result = await db.execute(select(Claim).where(Claim.id == claim_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Reclamación {claim_id} no encontrada")

    # Recupera las decisiones
    result    = await db.execute(
        select(AgentDecision)
        .where(AgentDecision.claim_id == claim_id)
        .order_by(AgentDecision.created_at.asc())
    )
    decisions = result.scalars().all()

    return ClaimTraceResponse(
        claim_id  = claim_id,
        decisions = [
            AgentDecisionItem(
                id         = d.id,
                agent      = d.agent,
                action     = d.action,
                reasoning  = d.reasoning,
                created_at = d.created_at,
            )
            for d in decisions
        ],
    )
