"""
Mock APIs simulades per al prototip Smart-Claims.

Cada funció simula una crida a un sistema extern real (core assegurador,
passarel·la de pagament, sistema de notificacions). En Fase II es
substituiran per integracions reals.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ── Tools que pot cridar l'orquestrador ───────────────────────────────────

@tool
def validate_documents(claim_id: str, doc_types: list[str]) -> dict:
    """
    Valida que la reclamació conté tots els documents requerits.

    Args:
        claim_id: ID de l'expedient.
        doc_types: Tipus de documents adjuntats (ex: ['foto_danys', 'factura']).

    Returns:
        Diccionari amb is_valid, missing_docs i contract_active.
    """
    required = {"foto_danys", "factura", "acta_policial"}
    provided = set(doc_types)
    missing = required - provided
    return {
        "claim_id": claim_id,
        "is_valid": len(missing) == 0,
        "missing_docs": list(missing),
        "contract_active": True,  # Mock: sempre actiu
        "checked_at": datetime.utcnow().isoformat(),
    }


@tool
def extract_multimodal(claim_id: str, file_url: str, doc_type: str) -> dict:
    """
    Extreu dades estructurades d'un document o imatge via VLM.

    Args:
        claim_id: ID de l'expedient.
        file_url: URL o path de l'arxiu.
        doc_type: Tipus de document ('factura' | 'foto_danys' | 'acta').

    Returns:
        Dades extretes: import, data, tipus_dany, confiança.
    """
    # Simulació: en producció crida Claude claude-sonnet-4-20250514 amb visió
    mock_data = {
        "factura":     {"amount": round(random.uniform(500, 8000), 2), "date": "2025-05-10", "vendor": "Taller Martínez"},
        "foto_danys":  {"damage_type": "colisió frontal", "severity": "moderat", "estimated_repair": 3200},
        "acta":        {"incident_date": "2025-05-08", "parties": 2, "fault_party": "tercer"},
    }
    data = mock_data.get(doc_type, {})
    return {
        "claim_id": claim_id,
        "doc_type": doc_type,
        "extracted": data,
        "confidence": round(random.uniform(0.82, 0.98), 3),
        "model": "claude-sonnet-4-20250514 (mock)",
    }


@tool
def check_policy(claim_id: str, claim_type: str, amount: float) -> dict:
    """
    Consulta la base de coneixement (RAG) per verificar cobertura i límits.

    Args:
        claim_id: ID de l'expedient.
        claim_type: Tipus de sinistre (ex: 'danys_propis', 'responsabilitat').
        amount: Import reclamat en €.

    Returns:
        coverage (bool), max_amount, deductible, policy_section.
    """
    coverage_rules = {
        "danys_propis":      {"covered": True,  "max": 10000, "deductible": 300},
        "responsabilitat":   {"covered": True,  "max": 50000, "deductible": 0},
        "robatori":          {"covered": True,  "max": 8000,  "deductible": 500},
        "danys_mecànics":    {"covered": False, "max": 0,     "deductible": 0},
    }
    rule = coverage_rules.get(claim_type, {"covered": False, "max": 0, "deductible": 0})
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "amount_requested": amount,
        "covered": rule["covered"],
        "max_coverage": rule["max"],
        "deductible": rule["deductible"],
        "net_payable": max(0, min(amount, rule["max"]) - rule["deductible"]) if rule["covered"] else 0,
        "policy_section": "SP-PCS-009 § 3.2",
    }


@tool
def approve_payment(claim_id: str, amount: float, iban: str) -> dict:
    """
    Simula l'emissió d'una transferència de pagament.

    Args:
        claim_id: ID de l'expedient.
        amount: Import a pagar en €.
        iban: IBAN del beneficiari.

    Returns:
        transaction_id, status, scheduled_date.
    """
    logger.info("MOCK PAYMENT — Expedient %s: %.2f€ → %s", claim_id, amount, iban[-4:])
    return {
        "claim_id": claim_id,
        "transaction_id": f"TXN-{claim_id}-{random.randint(10000,99999)}",
        "amount": amount,
        "iban_last4": iban[-4:],
        "status": "scheduled",
        "scheduled_date": "2025-05-15",
    }


@tool
def send_rejection(claim_id: str, reason: str, client_email: str) -> dict:
    """
    Simula l'enviament d'un email de rebuig justificat al client.

    Args:
        claim_id: ID de l'expedient.
        reason: Motiu del rebuig (ha de ser clar i justificat).
        client_email: Email de contacte del client.

    Returns:
        email_id, sent_at, reason_summary.
    """
    logger.info("MOCK REJECTION — Expedient %s → %s", claim_id, client_email)
    return {
        "claim_id": claim_id,
        "email_id": f"EMAIL-{claim_id}-REJ",
        "sent_to": client_email,
        "reason_summary": reason[:200],
        "sent_at": datetime.utcnow().isoformat(),
    }


@tool
def request_more_info(claim_id: str, missing_fields: list[str], client_email: str) -> dict:
    """
    Sol·licita informació addicional al client per continuar el tràmit.

    Args:
        claim_id: ID de l'expedient.
        missing_fields: Llista de camps o documents que manquen.
        client_email: Email de contacte del client.

    Returns:
        request_id, fields_requested, deadline_days.
    """
    logger.info("MOCK INFO REQUEST — Expedient %s: %s", claim_id, missing_fields)
    return {
        "claim_id": claim_id,
        "request_id": f"INFO-{claim_id}-{random.randint(100,999)}",
        "fields_requested": missing_fields,
        "sent_to": client_email,
        "deadline_days": 10,
    }


@tool
def check_fraud(claim_id: str, client_id: str, amount: float) -> dict:
    """
    Verifica el client contra llistes OFAC/ONU i detecta patrons de frau.

    Args:
        claim_id: ID de l'expedient.
        client_id: Identificador del client (DNI/passaport anonimitzat).
        amount: Import reclamat.

    Returns:
        is_flagged, risk_score, ofac_match, fraud_indicators.
    """
    # Mock: 5% de probabilitat de flag per testing
    risk_score = round(random.uniform(0.01, 0.35), 3)
    return {
        "claim_id": claim_id,
        "client_id_hash": hash(client_id) % 100000,
        "is_flagged": risk_score > 0.30,
        "risk_score": risk_score,
        "ofac_match": False,
        "fraud_indicators": [] if risk_score < 0.25 else ["import_inusual"],
    }


@tool
def log_decision(claim_id: str, agent: str, reasoning: str, action: str) -> dict:
    """
    Registra la decisió d'un agent a la base de dades (MariaDB).

    Args:
        claim_id: ID de l'expedient.
        agent: Identificador de l'agent (ex: 'agent_e').
        reasoning: Raonament CoT de la decisió.
        action: Acció executada.

    Returns:
        log_id, stored_at.
    """
    logger.info("LOG — Agent %s | Expedient %s | Acció: %s", agent, claim_id, action)
    return {
        "log_id": f"LOG-{claim_id}-{agent}",
        "claim_id": claim_id,
        "agent": agent,
        "action": action,
        "stored_at": datetime.utcnow().isoformat(),
    }


# ── Exporta el conjunt de tools per als agents ────────────────────────────

AGENT_TOOLS = [
    validate_documents,
    extract_multimodal,
    check_policy,
    approve_payment,
    send_rejection,
    request_more_info,
    check_fraud,
    log_decision,
]
