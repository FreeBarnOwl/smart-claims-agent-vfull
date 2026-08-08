"""
Fixtures de demo para la vista 'Conciliación (Agente F)'.

Demostrador SECUNDARIO e independiente del flujo principal A->B->C->G->D->E
(el PoC principal, danys_propis, no tiene fase de negociación). Cada caso
es un expediente DPA o RC ya en negociación; advise_conciliation() (Agente
F) los procesa en vivo al renderizar la vista — mismo patrón que
streamlit_fixtures.py (Bandeja): los datos del caso vienen preparados aquí,
el agente sí se ejecuta de verdad sobre ellos.
"""
from __future__ import annotations

CONCILIACION_CASES = [
    {
        "id": "CLM-CONC-0001",
        "situacion": "Oferta pendiente de subir de tramo",
        "case": {
            "claim_id":                        "CLM-CONC-0001",
            "claim_type":                       "dpa",
            "amount_claimed":                   8000.0,
            "negotiation_stage":                1,
            "last_offer_rejected":              True,
            "days_in_current_stage":            10,
            "days_since_last_client_response":  5,
            "coverage_sufficient":              True,
        },
    },
    {
        "id": "CLM-CONC-0002",
        "situacion": "Riesgo de cierre por abandono",
        "case": {
            "claim_id":                        "CLM-CONC-0002",
            "claim_type":                       "dpa",
            "amount_claimed":                   4500.0,
            "negotiation_stage":                1,
            "last_offer_rejected":              False,
            "days_in_current_stage":            20,
            "days_since_last_client_response":  40,
            "coverage_sufficient":              True,
        },
    },
    {
        "id": "CLM-CONC-0003",
        "situacion": "RC con cobertura insuficiente",
        "case": {
            "claim_id":                        "CLM-CONC-0003",
            "claim_type":                       "rc",
            "amount_claimed":                   15000.0,
            "negotiation_stage":                0,
            "last_offer_rejected":              False,
            "days_in_current_stage":            5,
            "days_since_last_client_response":  5,
            "coverage_sufficient":              False,
        },
    },
]
