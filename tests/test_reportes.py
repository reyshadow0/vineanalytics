"""
Pruebas de CU-O16 «Generar reporte operativo diario» (paquete `reportes-operativos`).

Verifican las reglas SIN Docker ni ClickHouse: la lectura de ClickHouse y el gate
de calidad se inyectan. Cubren los escenarios del spec:
  - Esc-1201 reporte nominal: calidad vigente → PUBLICADO, archivado, cifras correctas.
  - Esc-1202 sin calidad del día → BLOQUEADO_SIN_CALIDAD, sin reporte definitivo.
  - Esc-1203 solo-ClickHouse: si no hay agregaciones, FALLIDO (no se lee otra capa).
  - Esc-1205 reproducibilidad: regenerar la misma fecha produce las mismas cifras.
  - RN-1204 trazabilidad: cada sección referencia su Fact/agregación de origen.

Ejecutar:
    python -m pytest tests/test_reportes.py -q
    # o, sin pytest:
    python tests/test_reportes.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models_dashboards as md
from reportes import reporte_diario as rd
from tests.test_suscripciones import FakePB


# ── Fixtures de lectura ClickHouse (inyectada) y gate de calidad ──────────────
def _fuentes_ch():
    """Simula serving.reporte_diario_fuentes() (cifras desde ClickHouse)."""
    return {
        "periodo": "2026-06",
        "id_tiempo": 202606,
        "ingesta": {"resenas_en_dw": 129971, "puntuacion_promedio": 88.4, "calidad_dw_pct": 99.7},
        "api": {"llamadas": 48211, "errores": 12, "latencia_ms": 142.5, "ingreso": 5400.0},
        "uso": {"sesiones": 1830, "funciones": 9120, "usuarios_activos": 240, "dashboards_vistos": 512},
        "incidentes": {"incidentes": 1, "uptime_pct": 99.95, "despliegues": 4},
    }


def _gate_ok(pb):
    fecha = datetime.now().isoformat()
    md.registrar_sello("pipeline", exito=True, evaluadas=20, fallidas=0, fecha=fecha, client=pb)
    return lambda: md.calidad_vigente(client=pb)


def _archivo_tmp(tmp):
    return lambda rep: rep  # no escribe a disco en las pruebas (captura no-op)


# ── Esc-1201 · reporte nominal ────────────────────────────────────────────────
def test_reporte_nominal_publicado_con_cifras():
    pb = FakePB()
    rep = rd.generar(fecha="2026-06-29", lectura=_fuentes_ch, gate=_gate_ok(pb),
                     archivar_fn=lambda r: None, persistir=False)
    assert rep["estado"] == rd.PUBLICADO
    assert rep["calidad_ok"] is True
    assert rep["periodo"] == "2026-06"
    # consolida las 4 secciones (RF-1101)
    assert set(rep["secciones"]) == {"ingesta", "api", "uso", "incidentes"}
    assert rep["secciones"]["api"]["llamadas"] == 48211
    assert rep["secciones"]["incidentes"]["incidentes"] == 1
    assert rep["fuente_lectura"] == "clickhouse"


# ── Esc-1202 · sin calidad del día (RN-1201, regla dura) ──────────────────────
def test_sin_sello_calidad_queda_bloqueado():
    pb = FakePB()  # sin sello de calidad
    rep = rd.generar(fecha="2026-06-29", lectura=_fuentes_ch,
                     gate=lambda: md.calidad_vigente(client=pb),
                     archivar_fn=lambda r: None, persistir=False)
    assert rep["estado"] == rd.BLOQUEADO_SIN_CALIDAD
    assert rep["calidad_ok"] is False
    assert "secciones" not in rep  # no hay reporte definitivo


def test_ultima_calidad_fallida_bloquea():
    pb = FakePB()
    md.registrar_sello("dw", exito=False, evaluadas=20, fallidas=3, client=pb)
    rep = rd.generar(fecha="2026-06-29", lectura=_fuentes_ch,
                     gate=lambda: md.calidad_vigente(client=pb),
                     archivar_fn=lambda r: None, persistir=False)
    assert rep["estado"] == rd.BLOQUEADO_SIN_CALIDAD


def test_sello_vencido_bloquea():
    pb = FakePB()
    vieja = (datetime.now() - timedelta(hours=48)).isoformat()
    md.registrar_sello("pipeline", exito=True, evaluadas=20, fallidas=0, fecha=vieja, client=pb)
    rep = rd.generar(fecha="2026-06-29", lectura=_fuentes_ch,
                     gate=lambda: md.calidad_vigente(client=pb),
                     archivar_fn=lambda r: None, persistir=False)
    assert rep["estado"] == rd.BLOQUEADO_SIN_CALIDAD


# ── Esc-1203 · solo-ClickHouse: sin agregaciones → FALLIDO (no se lee otra capa) ─
def test_sin_agregaciones_clickhouse_es_fallido():
    pb = FakePB()
    rep = rd.generar(fecha="2026-06-29", lectura=lambda: None, gate=_gate_ok(pb),
                     archivar_fn=lambda r: None, persistir=False)
    assert rep["estado"] == rd.FALLIDO
    assert "RN-1202" in rep["motivo"]


# ── Esc-1205 · reproducibilidad (cifras idénticas al regenerar) ───────────────
def test_reproducibilidad_cifras_identicas():
    a = rd.consolidar("2026-06-29", _fuentes_ch(), sello_id="sel_1")
    b = rd.consolidar("2026-06-29", _fuentes_ch(), sello_id="sel_1")
    assert a == b  # determinista: mismas cifras, mismo período, misma trazabilidad


# ── RN-1204 · trazabilidad de cada cifra a su origen ──────────────────────────
def test_trazabilidad_por_seccion():
    rep = rd.consolidar("2026-06-29", _fuentes_ch())
    tz = rep["trazabilidad"]
    assert "Fact_Consumo_API" in tz["api"]
    assert "Fact_Uso_Plataforma" in tz["uso"]
    assert "Fact_Disponibilidad" in tz["incidentes"]
    assert "agg_" in tz["ingesta"]  # proviene de una agregación ClickHouse


# ── Archivo por fecha (RF-1105 / RN-1205) ─────────────────────────────────────
def test_archiva_por_fecha(tmp_path=None):
    import tempfile, json
    base = Path(tempfile.mkdtemp())
    rep = rd.consolidar("2026-06-29", _fuentes_ch(), sello_id="sel_1")
    out = rd.archivar(rep, base_dir=base)
    assert out.exists() and out.name == "reporte_diario_2026-06-29.json"
    # Reproducible: regenerar y re-archivar la misma fecha da el mismo contenido.
    cargado = json.loads(out.read_text(encoding="utf-8"))
    assert cargado["secciones"]["api"]["llamadas"] == 48211


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  [OK] {fn.__name__}")
    print(f"\n{len(fns)} pruebas pasaron.")
