"""
Schemas Pydantic para la API de reclamaciones.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Request ───────────────────────────────────────────────────────────────

class ClaimCreateRequest(BaseModel):
    """Cuerpo del POST /api/v1/claims/"""
    client_id:        str
    client_email:     str
    claim_type:       str        = Field(default="default",
        description="danys_propis | responsabilitat | robatori | danys_mecanics | default")
    amount_requested: float      = Field(default=0.0, ge=0)
    documents:        list[str]  = Field(
        default_factory=list,
        description="Documentos aportados: foto_danys, factura, acta_policial, etc."
    )
    text:             str        = Field(default="",
        description="Texto libre de la reclamación (email, formulario web).")


# ── Responses ─────────────────────────────────────────────────────────────

class ClaimResponse(BaseModel):
    """Respuesta del POST /api/v1/claims/ y de GET /{id}"""
    model_config = ConfigDict(from_attributes=True)

    claim_id:           str
    status:             str
    decision:           str | None   = None     # approved | rejected | pending_review
    amount_paid:        float | None = None
    amount_requested:   float | None = None
    hitl_required:      bool         = False
    termination_reason: str | None   = None


class AgentDecisionItem(BaseModel):
    """Un paso del Chain of Thought."""
    model_config = ConfigDict(from_attributes=True)

    id:         int
    agent:      str
    action:     str
    reasoning:  str
    created_at: datetime


class ClaimTraceResponse(BaseModel):
    """Respuesta del GET /{id}/trace"""
    claim_id:  str
    decisions: list[AgentDecisionItem]


class ClaimListItem(BaseModel):
    """Item del listado de reclamaciones."""
    model_config = ConfigDict(from_attributes=True)

    id:               str
    client_id:        str
    claim_type:       str
    status:           str
    amount_requested: float | None
    amount_approved:  float | None
    created_at:       datetime
