"""
Pruebas de la cadena observabilidad (CU-O11) → ML (CU-O12) → alertas (CU-O13).

Verifican las reglas SIN Docker ni DW: las sondas, la lectura de StarRocks, el gate
de calidad y la persistencia se inyectan (FakePB en memoria + conexión SR falsa).
Cubren los escenarios de los tres specs:

  CU-O13 alertas:
    - Esc-1001 churn sobre umbral → alerta `critical` a Customer Success, registrada.
    - Esc-1002 precio fuera de rango → alerta de anomalía a Ingeniería de datos.
    - Esc-1005 señales equivalentes → dedup/agrupación (NO duplica).
    - Esc-1006/§9 ciclo de vida abierta→reconocida→resuelta.
  CU-O11 observabilidad:
    - Esc-701 medición nominal: uptime/latencia consolidados + filas Fact_Disponibilidad.
    - Esc-702/703 SLO incumplido → señal a alertas (por región).
    - Esc-704 servicio caído → incidente con duración y región.
  CU-O12 ML:
    - Esc-803 sin sello CU-O04 → BLOQUEADA_POR_CALIDAD.
    - Esc-804/805 churn alto y precio anómalo emiten señal.
    - Esc-806 reejecución idempotente (no duplica predicciones).
  Cadena E2E:
    - una predicción de churn alto + una anomalía de precio generan alerta;
      una condición repetida NO duplica.

Ejecutar:
    python -m pytest tests/test_alertas.py -q
    python tests/test_alertas.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_alertas as ma
import models_dashboards as md
from etl import ml_inference as mli
from observabilidad import monitor as obs
from alertas import alert_engine as eng
from tests.test_suscripciones import FakePB


# ── Conexión StarRocks falsa para persistir_disponibilidad (sin DW) ───────────
class FakeSR:
    """Captura el DELETE+INSERT de fact_disponibilidad sin tocar StarRocks."""
    def __init__(self):
        self.borrados, self.insertados = [], []

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        if sql.strip().upper().startswith("DELETE"):
            self.borrados.append(params)

    def executemany(self, sql, seq):
        self.insertados.extend(seq)

    def commit(self):
        pass

    def close(self):
        pass


def _gate_ok(pb):
    md.registrar_sello("pipeline", exito=True, evaluadas=20, fallidas=0,
                       fecha=datetime.now().isoformat(), client=pb)
    return lambda: md.calidad_vigente(client=pb)


# ── Fixtures de salida de los modelos ──────────────────────────────────────────
def _churn_alto():
    return {
        "distribucion": {"Alto": 1, "Medio": 0, "Bajo": 1},
        "cuentas_riesgo": [
            {"cliente": "Bodega Andina", "plan": "Trial", "pais": "Chile",
             "score": 0.71, "probabilidad": 71.0, "nivel": "Alto", "adopcion": 31.0,
             "factor": "baja adopción", "ltv": 1800.0, "accion": "Retención CS"},
            {"cliente": "Viña Sur", "plan": "Enterprise", "pais": "Argentina",
             "score": 0.12, "probabilidad": 12.0, "nivel": "Bajo", "adopcion": 92.0,
             "factor": "señal histórica", "ltv": 9000.0, "accion": "Upsell"},
        ],
    }


def _precio_anomalo():
    return {"recomendaciones": [
        {"variedad": "Malbec", "demanda": 1500, "precio_actual": 20.0, "puntos": 90.0,
         "precio_recomendado": 24.4, "ajuste_pct": 22.0, "accion": "Subir precio"},
        {"variedad": "Merlot", "demanda": 800, "precio_actual": 15.0, "puntos": 88.0,
         "precio_recomendado": 15.3, "ajuste_pct": 2.0, "accion": "Mantener"},
    ]}


# ══════════════════════════════════════════════════════════════════════════════
# CU-O13 · alertas
# ══════════════════════════════════════════════════════════════════════════════
def test_churn_sobre_umbral_genera_critical_a_cs():
    pb = FakePB()
    alerta, creada = ma.generar_alerta(
        tipo="churn", clave="churn:Bodega Andina:202606", causa="Churn alto",
        origen="machine-learning", entidad="Bodega Andina", valor=0.71,
        umbral=0.42, id_tiempo=202606, client=pb)
    assert creada is True
    assert alerta["severidad"] == ma.CRITICAL          # RN-1002
    assert alerta["responsable"] == "Customer Success"  # RF-905
    assert alerta["estado"] == ma.ABIERTA
    assert alerta["tipo"] == "churn"


def test_precio_fuera_de_rango_va_a_ingenieria():
    pb = FakePB()
    alerta, _ = ma.generar_alerta(
        tipo="precio", clave="precio:Malbec:202606",
        causa="Precio anómalo", origen="machine-learning", client=pb)
    assert alerta["severidad"] == ma.WARNING
    assert alerta["responsable"] == "Ingeniería de datos"   # RN-1003


def test_condicion_repetida_no_duplica():
    """Esc-1005 / RN-1004: misma condición sostenida → se agrupa, NO se duplica."""
    pb = FakePB()
    clave = "churn:Bodega Andina:202606"
    a1, creada1 = ma.generar_alerta(tipo="churn", clave=clave, causa="c", client=pb)
    a2, creada2 = ma.generar_alerta(tipo="churn", clave=clave, causa="c", client=pb)
    assert creada1 is True and creada2 is False
    assert a1["id"] == a2["id"]
    assert int(a2["ocurrencias"]) == 2                  # agrupada
    assert len(pb.find(ma.COL_ALERTAS)) == 1            # una sola alerta


def test_ciclo_de_vida():
    """RF-907: abierta → reconocida → resuelta."""
    pb = FakePB()
    alerta, _ = ma.generar_alerta(tipo="uptime", clave="slo:uptime:1:202606",
                                  causa="caída", client=pb)
    assert ma.reconocer(alerta["id"], client=pb)["estado"] == ma.RECONOCIDA
    assert ma.resolver(alerta["id"], client=pb)["estado"] == ma.RESUELTA
    # Resuelta: una nueva señal con la misma clave abre una alerta nueva (no agrupa).
    _, creada = ma.generar_alerta(tipo="uptime", clave="slo:uptime:1:202606",
                                  causa="caída", client=pb)
    assert creada is True


# ══════════════════════════════════════════════════════════════════════════════
# CU-O11 · observabilidad
# ══════════════════════════════════════════════════════════════════════════════
_REGIONES = [(1, "Chile"), (2, "Argentina")]


def test_consolidar_uptime_latencia():
    """RF-702: uptime = operativo/total × 100; latencia = promedio."""
    mediciones = [
        {"servicio": "starrocks", "intentos": 3, "exitosos": 3, "latencias": [10, 12, 14]},
        {"servicio": "clickhouse", "intentos": 3, "exitosos": 3, "latencias": [20, 20, 20]},
    ]
    c = obs.consolidar(mediciones)
    assert c["uptime"] == 100.0
    assert c["latencia_ms"] == 16.0
    assert c["incidentes"] == 0


def test_medicion_nominal_persiste_filas(monkeypatch=None):
    """Esc-701: medición nominal → una fila de Fact_Disponibilidad por región."""
    pb = FakePB()
    sr = FakeSR()
    mediciones = [{"servicio": "starrocks", "intentos": 3, "exitosos": 3, "latencias": [30, 30, 30]}]
    res = obs.monitorear(mediciones=mediciones, regiones=_REGIONES, id_tiempo=202606,
                         conn_factory=lambda: sr, client=pb)
    assert res["ok"] and res["estado_slo"] == "EN_CUMPLIMIENTO"
    assert res["filas_persistidas"] == 2                 # una por región
    assert len(sr.insertados) == 2
    assert sr.borrados == [(202606,)]                    # idempotente por período
    assert res["senales_emitidas"] == 0                  # sin incumplimiento, sin señal


def test_slo_incumplido_emite_senal():
    """Esc-702/703: uptime bajo o latencia alta → señal por región a alertas."""
    pb = FakePB()
    sr = FakeSR()
    # 1 de 3 sondas caídas → uptime 33% (< 99.9) y servicio caído.
    mediciones = [{"servicio": "clickhouse", "intentos": 3, "exitosos": 1, "latencias": [350.0]}]
    res = obs.monitorear(mediciones=mediciones, regiones=_REGIONES, id_tiempo=202606,
                         conn_factory=lambda: sr, client=pb)
    assert res["estado_slo"] == "INCUMPLIDO"
    senales = pb.find(ma.COL_SENALES)
    tipos = {s["tipo"] for s in senales}
    assert "uptime" in tipos and "latencia" in tipos     # ambos SLO incumplidos
    assert all(s["origen"] == "observabilidad" for s in senales)


def test_incidente_con_duracion_y_region():
    """Esc-704 / RF-706: servicio caído → incidente con duración y región."""
    mediciones = [{"servicio": "starrocks", "intentos": 4, "exitosos": 0, "latencias": []}]
    incs = obs.incidentes_de(mediciones, id_tiempo=202606, region="Chile")
    assert len(incs) == 1
    inc = incs[0]
    assert inc["servicio"] == "starrocks" and inc["region"] == "Chile"
    assert inc["estado"] == "ABIERTO" and inc["severidad"] == "critical"
    assert inc["duracion_min"] == 30.0                   # 4/4 de la ventana


# ══════════════════════════════════════════════════════════════════════════════
# CU-O12 · machine-learning (inferencia programada)
# ══════════════════════════════════════════════════════════════════════════════
def _periodo():
    return (202606, "2026-06")


def test_sin_sello_calidad_bloquea_inferencia():
    """Esc-803 / RN-901: DW sin sello CU-O04 → corrida BLOQUEADA_POR_CALIDAD."""
    pb = FakePB()  # sin sello
    res = mli.inferir(churn_fn=_churn_alto, precios_fn=_precio_anomalo,
                      gate=lambda: md.calidad_vigente(client=pb),
                      client=pb, periodo_fn=_periodo)
    assert res["estado"] == mli.BLOQUEADA_POR_CALIDAD
    assert pb.find(mli.COL_PRED) == []                   # no persiste predicciones


def test_inferencia_persiste_con_version_y_emite_senales():
    """Esc-801/804/805: churn + precio → predicciones con versión + señales."""
    pb = FakePB()
    res = mli.inferir(churn_fn=_churn_alto, precios_fn=_precio_anomalo,
                      gate=_gate_ok(pb), client=pb, periodo_fn=_periodo)
    assert res["estado"] == mli.COMPLETADA
    preds = pb.find(mli.COL_PRED)
    assert len(preds) == 4                                # 2 churn + 2 precio
    assert all(p["version_modelo"] for p in preds)        # RF-805/RN-902
    # un churn Alto + un precio anómalo → 2 señales
    senales = pb.find(ma.COL_SENALES)
    tipos = sorted(s["tipo"] for s in senales)
    assert tipos == ["churn", "precio"]
    assert res["senales_emitidas"] == 2


def test_reejecucion_idempotente_no_duplica_predicciones():
    """Esc-806 / RNF-802: reejecutar la corrida no duplica predicciones ni señales."""
    pb = FakePB()
    gate = _gate_ok(pb)
    mli.inferir(churn_fn=_churn_alto, precios_fn=_precio_anomalo, gate=gate,
                client=pb, periodo_fn=_periodo)
    mli.inferir(churn_fn=_churn_alto, precios_fn=_precio_anomalo, gate=gate,
                client=pb, periodo_fn=_periodo)
    assert len(pb.find(mli.COL_PRED)) == 4                # upsert, no se duplica
    assert len(pb.find(ma.COL_SENALES)) == 2


# ══════════════════════════════════════════════════════════════════════════════
# Cadena E2E · ML → alertas (deliverable de la sesión)
# ══════════════════════════════════════════════════════════════════════════════
def test_cadena_churn_y_precio_generan_alerta_y_no_duplican():
    pb = FakePB()
    gate = _gate_ok(pb)

    # 1) CU-O12 corre y emite señales (churn alto + precio anómalo).
    mli.inferir(churn_fn=_churn_alto, precios_fn=_precio_anomalo, gate=gate,
                client=pb, periodo_fn=_periodo)

    # 2) CU-O13 drena el bus → genera alertas (sin detección de DW en la prueba).
    r1 = eng.ejecutar(client=pb, con_deteccion=False)
    assert r1["creadas"] == 2
    alertas = pb.find(ma.COL_ALERTAS)
    porseveridad = {a["tipo"]: a["severidad"] for a in alertas}
    assert porseveridad["churn"] == ma.CRITICAL
    assert porseveridad["precio"] == ma.WARNING

    # 3) Reejecución de la cadena (condición sostenida) → NO duplica alertas.
    mli.inferir(churn_fn=_churn_alto, precios_fn=_precio_anomalo, gate=gate,
                client=pb, periodo_fn=_periodo)
    r2 = eng.ejecutar(client=pb, con_deteccion=False)
    assert r2["creadas"] == 0                             # nada nuevo
    assert len(pb.find(ma.COL_ALERTAS)) == 2              # siguen siendo 2

    # 4) Reporte de alertas para OP11.
    rep = ma.reporte_alertas(client=pb)
    assert rep["total"] == 2 and rep["abiertas"] == 2


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [OK] {fn.__name__}")
    print(f"\n{len(fns)} pruebas pasaron.")
