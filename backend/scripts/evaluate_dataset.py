"""
Evaluador del sistema Smart-Claims sobre el dataset sintetico.

Procesa los 30 casos generados por generate_dataset.py contra el endpoint
REST del backend, clasifica las respuestas y genera un informe de metricas
para la memoria del TFM (seccion 6 — Evaluacion y Resultados).

Metricas calculadas:
- Precision por escenario esperado
- Matriz de confusion escenario_esperado vs resultado_obtenido
- Tasa de Resolucion Autonoma (TRA)
- Tasa de HITL
- Tiempo medio de procesamiento
- Distribucion de decisiones por agente

Salida:
- data/synthetic/evaluation_report.json   (informe estructurado)
- data/synthetic/evaluation_summary.csv   (resumen por caso)
- data/synthetic/evaluation_confusion.csv (matriz de confusion)

Uso:
    docker exec -it sca-backend python scripts/evaluate_dataset.py
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import httpx


DATA_DIR    = Path("/app/data/synthetic")
DATASET_IN  = DATA_DIR / "claims_dataset.json"

JSON_OUT      = DATA_DIR / "evaluation_report.json"
CSV_OUT       = DATA_DIR / "evaluation_summary.csv"
CONFUSION_OUT = DATA_DIR / "evaluation_confusion.csv"

API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000") + "/api/v1/claims"

# Mapeo escenario_esperado -> conjunto de resultados aceptables
# Define que estado/decision deberia producir cada escenario del dataset.
EXPECTED_OUTCOMES = {
    "pago_automatico": {
        "status":   {"resolved"},
        "decision": {"approved"},
        "hitl":     False,
    },
    "hitl": {
        "status":   {"pending_review"},
        "decision": {None},
        "hitl":     True,
    },
    "rechazo_no_cobertura": {
        "status":   {"rejected"},
        "decision": {"rejected"},
        "hitl":     False,
    },
    "info_incompleta": {
        "status":   {"validating"},
        "decision": {None},
        "hitl":     False,
    },
    "potencial_fraude": {
        # Aceptamos cualquier resultado salvo pago automatico:
        # G podria flaggear y bloquear, o E podria llevar a HITL por importe.
        "status":   {"rejected", "pending_review", "validating"},
        "decision": {None, "rejected"},
        "hitl":     None,  # no se evalua estrictamente
    },
}


def load_dataset() -> list[dict]:
    """Carga el dataset sintetico."""
    if not DATASET_IN.exists():
        print(f"ERROR: dataset no encontrado en {DATASET_IN}")
        print("Ejecuta primero: python scripts/generate_dataset.py")
        sys.exit(1)
    with DATASET_IN.open() as f:
        return json.load(f)


def classify_result(scenario: str, status: str, decision, hitl: bool) -> str:
    """
    Compara el resultado obtenido contra el escenario esperado.
    Devuelve: 'correct' | 'incorrect' | 'partial' | 'unexpected_scenario'
    """
    expected = EXPECTED_OUTCOMES.get(scenario)
    if expected is None:
        return "unexpected_scenario"

    status_ok = status in expected["status"]
    decision_ok = decision in expected["decision"]
    hitl_ok = (expected["hitl"] is None) or (hitl == expected["hitl"])

    if status_ok and decision_ok and hitl_ok:
        return "correct"
    if status_ok or decision_ok:
        return "partial"
    return "incorrect"


def process_claim(case: dict) -> dict:
    """
    Envia un caso al endpoint y captura el resultado y el tiempo.
    """
    payload = {
        "client_id":        case["client_id"],
        "client_email":     case["client_email"],
        "claim_type":       case["claim_type"],
        "amount_requested": case["amount_requested"],
        "documents":        case["documents"],
        "text":             case["text"],
    }

    start = time.time()
    error = None
    response_data = {}

    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(f"{API_BASE}/", json=payload)
            r.raise_for_status()
            response_data = r.json()
    except httpx.HTTPStatusError as e:
        error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    elapsed = time.time() - start
    return {
        "elapsed_seconds": round(elapsed, 2),
        "response":        response_data,
        "error":           error,
    }


def get_trace(claim_id: str) -> list[dict]:
    """Recupera la traza CoT del expediente procesado."""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{API_BASE}/{claim_id}/trace")
            r.raise_for_status()
            return r.json().get("decisions", [])
    except Exception:
        return []


def evaluate_dataset(cases: list[dict]) -> tuple[list[dict], dict]:
    """
    Procesa todos los casos y construye los registros de evaluacion.
    Devuelve (registros, agregados).
    """
    records: list[dict] = []
    n_total = len(cases)

    print(f"Procesando {n_total} casos contra {API_BASE}...")
    print()

    for i, case in enumerate(cases, 1):
        scenario = case["scenario"]
        print(f"  [{i:2d}/{n_total}] {case['claim_id']} ({scenario}) ... ", end="", flush=True)

        result = process_claim(case)

        if result["error"]:
            print(f"ERROR: {result['error']}")
            records.append({
                "case_id":            case["claim_id"],
                "scenario_expected":  scenario,
                "claim_type":         case["claim_type"],
                "amount_requested":   case["amount_requested"],
                "status_obtained":    None,
                "decision_obtained":  None,
                "amount_paid":        None,
                "hitl_required":      None,
                "classification":     "error",
                "elapsed_seconds":    result["elapsed_seconds"],
                "n_decisions":        0,
                "agents_invoked":     [],
                "error":              result["error"],
                "processed_claim_id": None,
            })
            continue

        resp = result["response"]
        processed_id   = resp.get("claim_id")
        status         = resp.get("status")
        decision       = resp.get("decision")
        amount_paid    = resp.get("amount_paid")
        hitl_required  = bool(resp.get("hitl_required"))

        # Recupera traza para contabilizar agentes invocados
        trace = get_trace(processed_id) if processed_id else []
        agents_invoked = sorted({d["agent"] for d in trace})

        classification = classify_result(scenario, status, decision, hitl_required)

        print(
            f"status={status:15s} decision={str(decision):10s} "
            f"hitl={str(hitl_required):5s} -> {classification}"
        )

        records.append({
            "case_id":            case["claim_id"],
            "scenario_expected":  scenario,
            "claim_type":         case["claim_type"],
            "amount_requested":   case["amount_requested"],
            "status_obtained":    status,
            "decision_obtained":  decision,
            "amount_paid":        amount_paid,
            "hitl_required":      hitl_required,
            "classification":     classification,
            "elapsed_seconds":    result["elapsed_seconds"],
            "n_decisions":        len(trace),
            "agents_invoked":     agents_invoked,
            "error":              None,
            "processed_claim_id": processed_id,
        })

    aggregates = compute_aggregates(records)
    return records, aggregates


def compute_aggregates(records: list[dict]) -> dict:
    """Calcula las metricas agregadas del dataset."""
    n_total = len(records)

    # Filtra casos sin error para los calculos de precision
    valid = [r for r in records if r["classification"] != "error"]
    n_valid = len(valid)
    n_errors = n_total - n_valid

    classification_counts = Counter(r["classification"] for r in valid)
    n_correct  = classification_counts.get("correct", 0)
    n_partial  = classification_counts.get("partial", 0)
    n_incorrect = classification_counts.get("incorrect", 0)

    # Precision por escenario
    by_scenario_correct: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    for r in valid:
        scenario = r["scenario_expected"]
        by_scenario_correct[scenario]["total"] += 1
        if r["classification"] == "correct":
            by_scenario_correct[scenario]["correct"] += 1

    precision_by_scenario = {
        scenario: {
            "correct":   v["correct"],
            "total":     v["total"],
            "precision": round(v["correct"] / v["total"], 3) if v["total"] else 0.0,
        }
        for scenario, v in by_scenario_correct.items()
    }

    # Tasa de Resolucion Autonoma (TRA): casos resueltos sin HITL
    n_autonomous = sum(
        1 for r in valid
        if r["status_obtained"] in {"resolved", "rejected"}
        and not r["hitl_required"]
    )
    tra = round(n_autonomous / n_valid, 3) if n_valid else 0.0

    n_hitl = sum(1 for r in valid if r["hitl_required"])
    hitl_rate = round(n_hitl / n_valid, 3) if n_valid else 0.0

    elapsed_values = [r["elapsed_seconds"] for r in valid]
    elapsed_stats = {
        "min":    round(min(elapsed_values), 2)    if elapsed_values else 0.0,
        "max":    round(max(elapsed_values), 2)    if elapsed_values else 0.0,
        "mean":   round(statistics.mean(elapsed_values), 2)   if elapsed_values else 0.0,
        "median": round(statistics.median(elapsed_values), 2) if elapsed_values else 0.0,
    }

    # Distribucion de agentes invocados
    agent_invocations: Counter[str] = Counter()
    for r in valid:
        for agent in r["agents_invoked"]:
            agent_invocations[agent] += 1

    return {
        "n_total_cases":         n_total,
        "n_valid":               n_valid,
        "n_errors":              n_errors,
        "n_correct":             n_correct,
        "n_partial":             n_partial,
        "n_incorrect":           n_incorrect,
        "overall_accuracy":      round(n_correct / n_valid, 3) if n_valid else 0.0,
        "precision_by_scenario": precision_by_scenario,
        "tra":                   tra,
        "hitl_rate":             hitl_rate,
        "elapsed_stats":         elapsed_stats,
        "agent_invocations":     dict(agent_invocations.most_common()),
        "evaluated_at":          datetime.utcnow().isoformat(),
    }


def build_confusion_matrix(records: list[dict]) -> list[list[str]]:
    """Construye una matriz escenario_esperado x resultado_obtenido."""
    scenarios = sorted({r["scenario_expected"] for r in records})
    statuses  = sorted({r["status_obtained"] or "error" for r in records})

    header = ["scenario_expected \\ status_obtained"] + statuses
    matrix = [header]
    for scenario in scenarios:
        row = [scenario]
        for status in statuses:
            n = sum(
                1 for r in records
                if r["scenario_expected"] == scenario
                and (r["status_obtained"] or "error") == status
            )
            row.append(str(n))
        matrix.append(row)
    return matrix


def write_outputs(records: list[dict], aggregates: dict) -> None:
    """Escribe los tres ficheros de salida."""
    # JSON completo
    report = {
        "aggregates":  aggregates,
        "records":     records,
    }
    with JSON_OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  JSON:      {JSON_OUT}")

    # CSV resumen por caso
    with CSV_OUT.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "case_id", "scenario_expected", "classification",
            "claim_type", "amount_requested",
            "status_obtained", "decision_obtained",
            "amount_paid", "hitl_required",
            "elapsed_seconds", "n_decisions", "agents_invoked",
        ]
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = r.copy()
            row["agents_invoked"] = ",".join(r.get("agents_invoked") or [])
            writer.writerow(row)
    print(f"  CSV:       {CSV_OUT}")

    # Matriz de confusion
    matrix = build_confusion_matrix(records)
    with CONFUSION_OUT.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(matrix)
    print(f"  Confusion: {CONFUSION_OUT}")


def print_summary(aggregates: dict) -> None:
    """Imprime el resumen ejecutivo de la evaluacion."""
    print()
    print("=" * 60)
    print("RESUMEN EJECUTIVO")
    print("=" * 60)
    print()
    print(f"  Casos totales:      {aggregates['n_total_cases']}")
    print(f"  Casos validos:      {aggregates['n_valid']}")
    print(f"  Errores:            {aggregates['n_errors']}")
    print()
    print("  Clasificacion:")
    print(f"    Correctos:        {aggregates['n_correct']}")
    print(f"    Parciales:        {aggregates['n_partial']}")
    print(f"    Incorrectos:      {aggregates['n_incorrect']}")
    print()
    print(f"  Precision global:   {aggregates['overall_accuracy']:.1%}")
    print(f"  TRA (autonomia):    {aggregates['tra']:.1%}")
    print(f"  Tasa HITL:          {aggregates['hitl_rate']:.1%}")
    print()
    print("  Precision por escenario:")
    for scenario, m in aggregates["precision_by_scenario"].items():
        print(f"    {scenario:25s} {m['correct']:2d}/{m['total']:2d}  ({m['precision']:.1%})")
    print()
    print("  Tiempo de procesamiento (segundos):")
    e = aggregates["elapsed_stats"]
    print(f"    min={e['min']}  max={e['max']}  mean={e['mean']}  median={e['median']}")
    print()
    print("  Invocaciones por agente:")
    for agent, n in aggregates["agent_invocations"].items():
        print(f"    {agent:35s} {n}")
    print()


def main() -> int:
    print("Smart-Claims Agent — Evaluacion sobre dataset sintetico")
    print()

    cases = load_dataset()
    print(f"Dataset cargado: {len(cases)} casos desde {DATASET_IN}")
    print()

    records, aggregates = evaluate_dataset(cases)

    print()
    print("Escribiendo resultados...")
    write_outputs(records, aggregates)

    print_summary(aggregates)
    print("Evaluacion completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
