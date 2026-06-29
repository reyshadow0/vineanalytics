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
    evaluadas = 0
    fallidas = 0
    detalle: dict = {}
    if correr_stage:
        from quality.ge_staging import validar_staging
        rep = validar_staging()
        _imprimir(rep)
        ok = ok and rep["exito"]
        for nombre, d in rep["datasets"].items():
            evaluadas += d["evaluadas"]
            fallidas += len(d["fallidas"])
            if d["fallidas"]:
                detalle.setdefault("stage", {})[nombre] = d["fallidas"]

    if correr_dw:
        from quality.ge_dw import validar_dw
        rep = validar_dw()
        _imprimir(rep)
        ok = ok and rep["exito"]
        for nombre, d in rep["datasets"].items():
            evaluadas += d["evaluadas"]
            fallidas += len(d["fallidas"])
            if d["fallidas"]:
                detalle.setdefault("dw", {})[nombre] = d["fallidas"]

    suite = "pipeline" if (correr_stage and correr_dw) else ("stage" if correr_stage else "dw")
    _registrar_sello(suite, ok, evaluadas, fallidas, detalle)

    print("\n" + ("CALIDAD OK — pipeline puede continuar."
                  if ok else "CALIDAD FALLIDA — pipeline DETENIDO (fail-fast)."))
    return 0 if ok else 1


def _registrar_sello(suite: str, exito: bool, evaluadas: int, fallidas: int,
                     detalle: dict) -> None:
    """Persiste el resultado como 'sello de calidad' en PocketBase (CU-O04 → CU-O06).
    Es best-effort: si PocketBase no está accesible, NO altera el exit code del gate
    (la regla fail-fast sigue gobernada por el código de salida)."""
    try:
        import models_dashboards as md
        sello = md.registrar_sello(suite=suite, exito=exito, evaluadas=evaluadas,
                                   fallidas=fallidas, detalle=detalle)
        print(f"[OK] Sello de calidad registrado (suite={suite}, exito={exito}, "
              f"id={sello.get('id')}).")
    except Exception as exc:
        print(f"[WARN] No se pudo registrar el sello de calidad: {exc}")


if __name__ == "__main__":
    # Permite ejecutar como módulo (python -m quality.run_quality) o script directo.
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.exit(main())
