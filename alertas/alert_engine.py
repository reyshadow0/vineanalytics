"""
alertas/alert_engine.py — CU-O13 «Generar alerta» (OP9), tarea del DAG.

Cierra la cadena observabilidad (CU-O11) → ML (CU-O12) → alertas (CU-O13):

  1. DETECTA (RF-901): corre la detección de anomalías por z-score sobre el DW
     (churn de Fact_Retencion, errores/latencia, MRR) reutilizando
     `etl.ml_models.detectar_anomalias()` y emite una señal por anomalía.
  2. CONSUME (RF-902): drena el bus `senales_alerta` —donde observabilidad dejó las
     caídas de SLO (CU-O11) y machine-learning las predicciones de churn alto /
     precio anómalo (CU-O12)— y genera/agrupa la alerta correspondiente.

La clasificación (tipo/severidad/causa), el enrutamiento al responsable, la
deduplicación anti-tormenta y el ciclo de vida viven en `models_alertas` (capa
operacional PocketBase). Este módulo solo orquesta y es la ENTRADA del DAG:

    docker exec vinanalytics-runner python -m alertas.alert_engine

Idempotencia (RNF-902/RT-11): una señal ya procesada no se reprocesa y una
condición sostenida (misma `clave`) agrupa en la alerta abierta en vez de duplicar.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_alertas as ma

# serie de anomalía (etl.ml_models.detectar_anomalias) → tipo de alerta
_SERIE_TIPO = {
    "Tasa de churn":               "churn",
    "Errores de API":              "api",
    "Latencia global":             "latencia",
    "Ingresos recurrentes (MRR)":  "ingresos",
}


def _id_tiempo(periodo: str | None) -> int | None:
    """'2026-06' → 202606 (alinea la señal con Dim_Tiempo)."""
    if not periodo or "-" not in str(periodo):
        return None
    try:
        y, m = str(periodo).split("-")[:2]
        return int(y) * 100 + int(m)
    except ValueError:
        return None


# ── 1) Detección propia de alertas (RF-901) → emite señales ───────────────────
def emitir_desde_anomalias(detectar=None, client=None) -> int:
    """Ejecuta la detección de anomalías sobre el DW y emite una señal por cada una.

    `detectar` es inyectable (en pruebas no toca StarRocks). La dedup `clave`
    incluye serie+período, de modo que reejecutar no apila señales (idempotencia).
    """
    if detectar is None:
        from etl.ml_models import detectar_anomalias as detectar
    res = detectar() or {}
    if not res.get("disponible"):
        return 0
    emitidas = 0
    for anom in res.get("anomalias", []):
        serie = anom.get("serie", "")
        tipo = _SERIE_TIPO.get(serie, "ingresos")
        periodo = anom.get("periodo")
        clave = f"anomalia:{serie}:{periodo}"
        causa = (f"{anom.get('tipo', 'desvío')} en «{serie}»: {anom.get('valor')} "
                 f"(esperado ~{anom.get('esperado')}, z={anom.get('z')})")
        ma.emitir_senal(
            origen="alertas", tipo=tipo, clave=clave, causa=causa,
            entidad=serie, valor=anom.get("valor"), umbral=anom.get("esperado"),
            id_tiempo=_id_tiempo(periodo),
            payload={"z": anom.get("z"), "direccion": anom.get("tipo")},
            client=client)
        emitidas += 1
    return emitidas


# ── Orquestación de la tarea del DAG ──────────────────────────────────────────
def ejecutar(client=None, detectar=None, con_deteccion: bool = True) -> dict:
    """Emite señales de anomalías (RF-901) y luego drena el bus (RF-902)."""
    detectadas = 0
    if con_deteccion:
        try:
            detectadas = emitir_desde_anomalias(detectar=detectar, client=client)
        except Exception as exc:  # detección best-effort: no debe tumbar la tarea
            print(f"[WARN] Detección de anomalías omitida: {exc}")
    resumen = ma.procesar_pendientes(client=client)
    resumen["anomalias_detectadas"] = detectadas
    return resumen


def main() -> int:
    resumen = ejecutar()
    print("\n" + "=" * 56)
    print("MOTOR DE ALERTAS (CU-O13)")
    print("=" * 56)
    print(f"  Anomalías detectadas (RF-901):     {resumen['anomalias_detectadas']}")
    print(f"  Señales procesadas del bus (RF-902): {resumen['pendientes']}")
    print(f"  Alertas nuevas:                    {resumen['creadas']}")
    print(f"  Agrupadas (dedup RF-906):          {resumen['agrupadas']}")
    for a in resumen["alertas"][:10]:
        print(f"   · [{a.get('severidad'):8s}] {a.get('tipo'):9s} → "
              f"{a.get('responsable')}: {a.get('causa')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
