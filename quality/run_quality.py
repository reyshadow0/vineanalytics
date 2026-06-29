"""
Gate de calidad fail-fast (CU-O04 · Princ. V / RT-07).

Orquesta las suites Great Expectations y devuelve un código de salida:
  exit 0  → todas las expectativas pasan (el pipeline puede continuar).
  exit 1  → alguna expectativa crítica falla (DETIENE el pipeline; no se carga
            a StarRocks ni se promueve a ClickHouse).

Uso:
  python quality/run_quality.py --stage    # gate previo (staging Parquet)
  python quality/run_quality.py --dw        # gate posterior (DW StarRocks)
  python quality/run_quality.py             # ambos

Airflow (fase posterior) invoca este script como tarea de calidad; su exit code
no-cero corta el DAG.
"""

import argparse
import json
import sys


def _imprimir(rep: dict) -> None:
    estado = "OK" if rep["exito"] else "FALLA"
    print(f"\n=== Suite '{rep['suite']}': {estado} ===")
    for nombre, d in rep["datasets"].items():
        marca = "[OK]  " if d["exito"] else "[FAIL]"
        print(f"  {marca} {nombre}: {d['evaluadas']} expectativas evaluadas")
        for f in d["fallidas"]:
            col = f" col={f['columna']}" if f.get("columna") else ""
            print(f"         ↳ FALLÓ: {f['expectativa']}{col}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Gate de calidad Great Expectations (fail-fast)")
    ap.add_argument("--stage", action="store_true", help="Validar staging Parquet")
    ap.add_argument("--dw", action="store_true", help="Validar DW StarRocks (marts)")
    args = ap.parse_args()

    # Sin flags → ambos.
    correr_stage = args.stage or not (args.stage or args.dw)
    correr_dw    = args.dw    or not (args.stage or args.dw)

    ok = True
    if correr_stage:
        from quality.ge_staging import validar_staging
        rep = validar_staging()
        _imprimir(rep)
        ok = ok and rep["exito"]

    if correr_dw:
        from quality.ge_dw import validar_dw
        rep = validar_dw()
        _imprimir(rep)
        ok = ok and rep["exito"]

    print("\n" + ("CALIDAD OK — pipeline puede continuar."
                  if ok else "CALIDAD FALLIDA — pipeline DETENIDO (fail-fast)."))
    return 0 if ok else 1


if __name__ == "__main__":
    # Permite ejecutar como módulo (python -m quality.run_quality) o script directo.
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
