"""
campaigns_runner.py — Orquestador de ejecución automatizada de campañas de
captación (CU-O09 · OP6 · paquete `captacion-conversion`), tarea del DAG.

Ejecuta sin intervención manual (RF-602, RNF-601) todas las campañas PROGRAMADAS
cuya programación ya venció: registra sus métricas (impresiones/clics/gasto/leads)
en `eventos_campana` (PocketBase), que el ETL (OP2) proyecta a `Fact_Campana`.
También evalúa la caída de conversión y, si procede, emite señal al bus de alertas
(RN-706, CU-O13).

Capas: toda la persistencia es operacional en PocketBase (RNF-603); este módulo NO
escribe en StarRocks/ClickHouse. La lógica vive en `models_captacion.py`.

Idempotencia (RNF-601): la ejecución de un período hace upsert de la fila de
`eventos_campana` por (campaña, id_tiempo); reejecutar la tarea no duplica métricas.

Ejecución (tarea del DAG, en el runner):
    docker exec vinanalytics-runner python -m campaigns_runner
"""

from __future__ import annotations

import sys

import models_captacion as cap


def main() -> int:
    try:
        res = cap.ejecutar_pendientes()
    except Exception as exc:   # PocketBase no accesible u otro fallo de capa operacional
        print("\n" + "=" * 56)
        print("EJECUCIÓN DE CAMPAÑAS (CU-O09) — FALLIDA")
        print("=" * 56)
        print(f"  Motivo: {exc}")
        return 1

    print("\n" + "=" * 56)
    print("EJECUCIÓN AUTOMATIZADA DE CAMPAÑAS (CU-O09)")
    print("=" * 56)
    print(f"  Campañas ejecutadas: {res['ejecutadas']}")
    for d in res["detalle"]:
        print(f"   · {d['nombre']} (campaña={d['campana']}) "
              f"→ evento={d['evento']} corrida={d['corrida']}")
    if not res["detalle"]:
        print("  (sin campañas PROGRAMADAS vencidas en este ciclo)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
