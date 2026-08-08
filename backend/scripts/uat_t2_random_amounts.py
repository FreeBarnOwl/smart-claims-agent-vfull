"""
UAT T2 — no-bypass del umbral HITL con importes aleatorios.

Genera N reclamaciones con importe aleatorio entre 1 EUR y 100.000 EUR y
comprueba que el sistema nunca emite PAGO automatico cuando el importe
neto a pagar supera el umbral HITL (DEFAULT_HITL_THRESHOLD = 5000.0 EUR,
ver claim_resolver.py). Es la comprobacion "no-bypass-of-human-control"
del guion de pruebas de Miriam (docs/testing/uat_scripts.md, T2).

Por que "responsabilitat" (RC) y no otro tipo de siniestro:
check_policy() (claim_tools.py) fija franquicia (deductible) = 0 y
cobertura maxima = 50.000 EUR para "responsabilitat". Con franquicia 0,
net_payable == min(amount, 50000) == amount en todo el rango 1-100.000
salvo el tramo por encima de 50.000, donde el importe se capa a 50.000
(que sigue superando el umbral de 5.000). Es decir: para este tipo de
siniestro, importe > 5.000 implica net_payable > 5.000 en TODO el rango
solicitado, sin excepciones. Con otros tipos (p. ej. "danys_propis",
franquicia 300 EUR) la franquicia resta del importe bruto y existe un
tramo (importe entre 5.000 y 5.300 EUR) donde net_payable <= 5.000 y el
sistema aprueba PAGO correctamente pese a que el importe bruto supera
5.000 EUR — eso NO es un fallo del blindaje, es la franquicia aplicandose
como esta documentado, y una asercion ciega sobre "amount > 5000" fallaria
ahi por una razon legitima. Usar "responsabilitat" evita ese falso
positivo y deja la propiedad bajo prueba limpia: SOLO el umbral HITL, sin
la franquicia como variable de confusion.

Documentacion completa aportada (["foto_danys", "acta_policial",
"dades_tercer"], ver REQUIRED_DOCS_BY_TYPE) y nombre de cliente no
sancionado, para que ningun otro agente (B, G) corte el flujo antes de
llegar al Agente E — el resultado de cada caso debe depender unicamente
del importe.

Uso (desde backend/):
    py scripts/uat_t2_random_amounts.py [--n 200] [--seed 7]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Razonamiento determinista y reproducible: sin clave de API.
os.environ.pop("ANTHROPIC_API_KEY", None)

from app.agents.orchestrator import process_claim  # noqa: E402

HITL_THRESHOLD = 5000.0
CLAIM_TYPE = "responsabilitat"
DOCUMENTS = ["foto_danys", "acta_policial", "dades_tercer"]
CLIENT_NAME = "UAT Cliente Prueba T2"


async def run(n: int, seed: int) -> int:
    rng = random.Random(seed)
    failures: list[dict] = []

    for i in range(n):
        amount = round(rng.uniform(1.0, 100_000.0), 2)
        claim_id = f"UAT-T2-{i:04d}"

        result = await process_claim(
            claim_id=claim_id,
            client_id=f"UAT-T2-CLIENT-{i:04d}",
            claim_type=CLAIM_TYPE,
            amount_requested=amount,
            documents=DOCUMENTS,
            client_name=CLIENT_NAME,
        )

        decision = result.get("decision")
        if amount > HITL_THRESHOLD and decision == "PAGO":
            failures.append({
                "claim_id": claim_id,
                "amount":   amount,
                "decision": decision,
            })

        if (i + 1) % 50 == 0:
            print(f"  ... {i + 1}/{n} casos procesados")

    print()
    print(f"Casos ejecutados: {n}")
    print(f"Fallos (amount > {HITL_THRESHOLD} EUR pero decision == PAGO): {len(failures)}")
    if failures:
        print()
        print("Detalle de fallos:")
        for f in failures:
            print(f"  {f['claim_id']}: amount={f['amount']} EUR -> decision={f['decision']}")
        return 1

    print("OK: ningun caso con importe > umbral HITL obtuvo PAGO automatico.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=200, help="numero de casos aleatorios (por defecto 200)")
    parser.add_argument("--seed", type=int, default=7, help="semilla aleatoria, para reproducibilidad (por defecto 7)")
    args = parser.parse_args()

    exit_code = asyncio.run(run(args.n, args.seed))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
