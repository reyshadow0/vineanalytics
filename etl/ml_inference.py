"""
etl/ml_inference.py — CU-O12 «Ejecutar modelo de ML programado» (OP8), tarea del DAG.

Ejecuta la INFERENCIA programada (no el entrenamiento, RN-906) de los modelos
vigentes —churn y precios dinámicos— leyendo features del DW StarRocks ya validado
por calidad (RN-901), persiste las predicciones con su VERSIÓN de modelo, features
y score (RF-805/RN-902) y emite señales a `alertas` (CU-O13) cuando un churn supera
el umbral (RN-903) o un precio recomendado queda fuera de rango (RN-904).

Capas: features ← StarRocks (DW); predicciones → PocketBase (traza operacional,
patrón "eventos a PocketBase"); a dashboards se sirven SOLO vía ClickHouse (RN-905,
fuera de este módulo). Reutiliza los modelos explicables de `etl.ml_models`.

Estados (spec §9): PROGRAMADA → CARGANDO_FEATURES → INFIRIENDO → PERSISTIENDO →
COMPLETADA; errores: BLOQUEADA_POR_CALIDAD (sin sello CU-O04), FALLIDA.

Idempotencia (RNF-802): la corrida es determinista `modelo-version-id_tiempo`; las
predicciones se hacen upsert por (corrida, id_entidad) → reejecutar no duplica.

Ejecución (tarea del DAG, tras el gate de calidad del DW):
    docker exec vinanalytics-runner python -m etl.ml_inference
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Versiones de modelo vigente (RF-805 / RN-902) ─────────────────────────────
VERSION_CHURN  = "churn-ponderado-v1.0"
VERSION_PRECIO = "precio-dinamico-v1.0"

# ── Umbrales de disparo de alerta ─────────────────────────────────────────────
UMBRAL_CHURN       = 0.42    # score ≥ 0.42 → nivel "Alto" (RN-903)
UMBRAL_PRECIO_PCT  = 15.0    # |ajuste recomendado| ≥ 15% → precio fuera de rango (RN-904)

# ── Estados de la corrida (spec §9) ───────────────────────────────────────────
COMPLETADA            = "COMPLETADA"
BLOQUEADA_POR_CALIDAD = "BLOQUEADA_POR_CALIDAD"
FALLIDA               = "FALLIDA"

COL_PRED = "predicciones_ml"


def _periodo_actual() -> tuple[int, str]:
    """Período más reciente del DW (alinea predicciones y señales con Dim_Tiempo)."""
    from etl.ml_models import _latest
    idt = _latest()
    if idt is None:
        return 0, ""
    return idt, f"{idt // 100:04d}-{idt % 100:02d}"


# ── Gate de calidad (RN-901): solo se infiere sobre un DW validado por CU-O04 ──
def _gate_default(client, ventana_horas: float):
    import models_dashboards as md
    return md.calidad_vigente(client, ventana_horas)


# ── Persistencia de predicciones (idempotente por corrida+entidad) ────────────
def _persistir_predicciones(modelo: str, version: str, corrida: str,
                            predicciones: list[dict], id_tiempo: int, periodo: str,
                            client) -> int:
    from pb_client import get_client
    client = client or get_client()
    hoy = date.today().isoformat()
    n = 0
    for p in predicciones:
        data = {
            "corrida": corrida, "modelo": modelo, "version_modelo": version,
            "entidad": p["entidad"], "id_entidad": p["id_entidad"],
            "nombre": p.get("nombre", p["id_entidad"]),
            "score": float(p["score"]), "nivel": p.get("nivel", ""),
            "umbral": float(p["umbral"]), "supera_umbral": bool(p["supera_umbral"]),
            "features": json.dumps(p.get("features", {}), ensure_ascii=False),
            "periodo": periodo, "id_tiempo": id_tiempo, "fecha": hoy,
        }
        existente = client.find_one(COL_PRED, corrida=corrida, id_entidad=p["id_entidad"])
        if existente:
            client.update(COL_PRED, existente["id"], data)
        else:
            client.create(COL_PRED, data)
        n += 1
    return n


# ── Normalización de la salida de los modelos a "predicciones" + señales ──────
def churn_predicciones(churn_res: dict, id_tiempo: int) -> tuple[list[dict], list[dict]]:
    """Convierte predecir_churn() en filas de predicción + señales de churn alto."""
    preds, senales = [], []
    for c in churn_res.get("cuentas_riesgo", []):
        supera = float(c["score"]) >= UMBRAL_CHURN or c.get("nivel") == "Alto"
        preds.append({
            "entidad": "cliente", "id_entidad": str(c["cliente"]),
            "nombre": c["cliente"], "score": float(c["score"]), "nivel": c.get("nivel"),
            "umbral": UMBRAL_CHURN, "supera_umbral": supera,
            "features": {"plan": c.get("plan"), "pais": c.get("pais"),
                         "adopcion": c.get("adopcion"), "factor": c.get("factor"),
                         "ltv": c.get("ltv")},
        })
        if supera:  # RN-903: churn sobre umbral → señal (alerta critical a CS)
            senales.append({
                "tipo": "churn", "severidad": "critical",
                "clave": f"churn:{c['cliente']}:{id_tiempo}",
                "entidad": c["cliente"], "valor": float(c["score"]),
                "umbral": UMBRAL_CHURN, "id_tiempo": id_tiempo,
                "causa": (f"Churn alto ({c.get('probabilidad')}%) en {c['cliente']} "
                          f"· {c.get('factor')} · plan {c.get('plan')}"),
                "payload": {"nivel": c.get("nivel"), "ltv": c.get("ltv"),
                            "accion": c.get("accion")},
            })
    return preds, senales


def precio_predicciones(precio_res: dict, id_tiempo: int) -> tuple[list[dict], list[dict]]:
    """Convierte precios_dinamicos() en filas de predicción + señales de precio anómalo."""
    preds, senales = [], []
    for r in precio_res.get("recomendaciones", []):
        ajuste = abs(float(r.get("ajuste_pct", 0)))
        anomalo = ajuste >= UMBRAL_PRECIO_PCT
        preds.append({
            "entidad": "variedad", "id_entidad": str(r["variedad"]),
            "nombre": r["variedad"], "score": float(r.get("ajuste_pct", 0)),
            "nivel": r.get("accion", ""), "umbral": UMBRAL_PRECIO_PCT,
            "supera_umbral": anomalo,
            "features": {"demanda": r.get("demanda"), "precio_actual": r.get("precio_actual"),
                         "precio_recomendado": r.get("precio_recomendado"),
                         "puntos": r.get("puntos")},
        })
        if anomalo:  # RN-904: precio fuera de rango → señal de anomalía
            senales.append({
                "tipo": "precio", "severidad": "warning",
                "clave": f"precio:{r['variedad']}:{id_tiempo}",
                "entidad": r["variedad"], "valor": float(r.get("precio_recomendado", 0)),
                "umbral": float(r.get("precio_actual", 0)), "id_tiempo": id_tiempo,
                "causa": (f"Precio recomendado {r.get('precio_recomendado')} para "
                          f"{r['variedad']} se desvía {r.get('ajuste_pct')}% "
                          f"(actual {r.get('precio_actual')})"),
                "payload": {"ajuste_pct": r.get("ajuste_pct"), "accion": r.get("accion")},
            })
    return preds, senales


# ── Orquestación de la corrida ────────────────────────────────────────────────
def inferir(*, churn_fn=None, precios_fn=None, gate=None, client=None,
            persistir=True, ventana_horas: float = 24, periodo_fn=None) -> dict:
    """Ejecuta la inferencia programada de churn y precios. Devuelve el reporte de
    la corrida con métricas (RF-807). Todo inyectable para pruebas sin DW."""
    t0 = time.perf_counter()
    id_tiempo, periodo = (periodo_fn or _periodo_actual)()

    # ── RN-901: gate de calidad — sin DW validado (CU-O04) NO se infiere ──
    gate = gate or (lambda: _gate_default(client, ventana_horas))
    cal = gate()
    if not cal.get("ok"):
        return {"estado": BLOQUEADA_POR_CALIDAD, "motivo": cal.get("motivo"),
                "id_tiempo": id_tiempo, "periodo": periodo,
                "sello": (cal.get("sello") or {}).get("id", "")}

    # ── CARGANDO_FEATURES + INFIRIENDO (lee features de StarRocks) ──
    churn_fn = churn_fn or _churn_default
    precios_fn = precios_fn or _precios_default
    try:
        churn_res = churn_fn() or {}
        precio_res = precios_fn() or {}
    except Exception as exc:
        return {"estado": FALLIDA, "motivo": f"Error de inferencia: {exc}",
                "id_tiempo": id_tiempo, "periodo": periodo}

    preds_churn, sen_churn = churn_predicciones(churn_res, id_tiempo)
    preds_precio, sen_precio = precio_predicciones(precio_res, id_tiempo)

    # ── PERSISTIENDO: predicciones con versión + features (idempotente) ──
    corrida_churn = f"churn-{VERSION_CHURN}-{id_tiempo}"
    corrida_precio = f"precio-{VERSION_PRECIO}-{id_tiempo}"
    persistidas = senales_emitidas = 0
    if persistir:
        persistidas += _persistir_predicciones("churn", VERSION_CHURN, corrida_churn,
                                               preds_churn, id_tiempo, periodo, client)
        persistidas += _persistir_predicciones("precio", VERSION_PRECIO, corrida_precio,
                                               preds_precio, id_tiempo, periodo, client)
        senales_emitidas = _emitir(sen_churn + sen_precio, client)

    duracion_s = round(time.perf_counter() - t0, 3)
    return {
        "estado": COMPLETADA, "id_tiempo": id_tiempo, "periodo": periodo,
        "sello": (cal.get("sello") or {}).get("id", ""),
        "modelos": {"churn": VERSION_CHURN, "precio": VERSION_PRECIO},
        # ── métricas de la corrida (RF-807) ──
        "metricas": {
            "duracion_s": duracion_s,
            "predicciones_churn": len(preds_churn),
            "predicciones_precio": len(preds_precio),
            "distribucion_churn": churn_res.get("distribucion", {}),
            "alertas_churn": len(sen_churn),
            "alertas_precio": len(sen_precio),
        },
        "predicciones_persistidas": persistidas,
        "senales_emitidas": senales_emitidas,
        "senales_detalle": sen_churn + sen_precio,
    }


def _churn_default():
    from etl.ml_models import predecir_churn
    return predecir_churn()


def _precios_default():
    from etl.ml_models import precios_dinamicos
    return precios_dinamicos()


def _emitir(senales: list[dict], client) -> int:
    import models_alertas as ma
    n = 0
    for s in senales:
        ma.emitir_senal(origen="machine-learning", tipo=s["tipo"], clave=s["clave"],
                        causa=s["causa"], severidad=s["severidad"],
                        entidad=s["entidad"], valor=s["valor"], umbral=s["umbral"],
                        id_tiempo=s["id_tiempo"], payload=s.get("payload"),
                        client=client)
        n += 1
    return n


def main() -> int:
    res = inferir()
    print("\n" + "=" * 56)
    print("INFERENCIA ML PROGRAMADA (CU-O12)")
    print("=" * 56)
    print(f"  Estado:   {res['estado']}")
    if res["estado"] != COMPLETADA:
        print(f"  Motivo:   {res.get('motivo')}")
        # BLOQUEADA/FALLIDA → fail-fast de la tarea (como reporte_diario).
        return 1
    m = res["metricas"]
    print(f"  Período:  {res['id_tiempo']} ({res['periodo']})  ·  modelos: {res['modelos']}")
    print(f"  Churn:    {m['predicciones_churn']} predicciones · dist {m['distribucion_churn']}")
    print(f"  Precio:   {m['predicciones_precio']} recomendaciones")
    print(f"  Persistidas: {res['predicciones_persistidas']} (versión+features, idempotente)")
    print(f"  Señales a alertas: {res['senales_emitidas']} "
          f"(churn {m['alertas_churn']} · precio {m['alertas_precio']})")
    print(f"  Duración: {m['duracion_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
