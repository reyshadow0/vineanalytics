"""
reportes/reporte_diario.py — CU-O16 «Generar reporte operativo diario» (OP11).

Cierre del flujo operativo: tras la fase de agregaciones del `dag_pipeline_diario`
(`poblar_clickhouse`), este módulo consolida el día —ingesta, consumo de API, uso
de plataforma e incidentes— en un reporte diario, lo archiva por fecha y lo deja
como insumo para la consolidación mensual/estratégica.

Reglas (spec reportes-operativos):
  - RF-1101  Consolida ingesta / API / uso / incidentes por `Dim_Tiempo`.
  - RF-1102 / RN-1202  Lee **solo** agregaciones de **ClickHouse** (sin fallback a
             StarRocks/PocketBase): las cifras llegan por `lectura()`
             (= serving.reporte_diario_fuentes, que solo consulta ClickHouse).
  - RF-1103 / RN-1203  Se genera automáticamente al cierre del DAG (último paso).
  - RF-1104 / RN-1201  Gate de calidad: verifica el **sello CU-O04** del día; si la
             calidad no está vigente, el reporte NO se publica → BLOQUEADO_SIN_CALIDAD.
  - RF-1105 / RN-1205  Archiva por fecha; reproducible (mismas cifras al regenerar).
  - RN-1204  Cada cifra es trazable a su Fact/agregación de origen (`trazabilidad`).

Estados (spec §9): PENDIENTE → ESPERANDO_CALIDAD → GENERANDO → PUBLICADO;
errores: BLOQUEADO_SIN_CALIDAD (sin sello vigente), FALLIDO (error de generación).

Uso (último paso del DAG):
    docker exec vinanalytics-runner python -m reportes.reporte_diario
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Carpeta de archivo por fecha (auditoría/reproducibilidad, RN-1205).
ARCHIVO_DIR = Path(__file__).resolve().parent / "archivo"

# ── Estados del reporte (spec §9) ─────────────────────────────────────────────
PUBLICADO             = "PUBLICADO"
BLOQUEADO_SIN_CALIDAD = "BLOQUEADO_SIN_CALIDAD"
FALLIDO               = "FALLIDO"

REPORTE_VERSION = 1

# Trazabilidad de cada sección a su Fact/agregación de origen (RN-1204, RNF-1104).
TRAZABILIDAD = {
    "ingesta":    "clickhouse.agg_kpis_vino (filas) + agg_bsc_kpis.calidad ← Fact_Resena",
    "api":        "clickhouse.agg_reporte_diario ← Fact_Consumo_API",
    "uso":        "clickhouse.agg_reporte_diario ← Fact_Uso_Plataforma",
    "incidentes": "clickhouse.agg_reporte_diario ← Fact_Disponibilidad",
}


# ── Consolidación (función pura, determinista → reproducible RN-1205) ──────────
def consolidar(fecha: str, fuentes: dict, sello_id: str = "") -> dict:
    """Arma el reporte operativo diario a partir de las cifras de ClickHouse.

    Es determinista: dadas la misma `fecha` y las mismas `fuentes`, produce el
    mismo reporte (sin timestamps en las cifras) → reproducibilidad (RN-1205).
    """
    return {
        "fecha": fecha,
        "periodo": fuentes.get("periodo"),
        "id_tiempo": fuentes.get("id_tiempo"),
        "version": REPORTE_VERSION,
        "estado": PUBLICADO,
        "calidad_ok": True,
        "sello": sello_id or "",
        "secciones": {
            "ingesta":    fuentes.get("ingesta", {}),
            "api":        fuentes.get("api", {}),
            "uso":        fuentes.get("uso", {}),
            "incidentes": fuentes.get("incidentes", {}),
        },
        "trazabilidad": TRAZABILIDAD,
        "fuente_lectura": "clickhouse",
    }


# ── Gate de calidad del día (CU-O04 · RF-1104 / RN-1201) ──────────────────────
def _gate_calidad(client, ventana_horas: float):
    """Verifica el sello de calidad vigente del día (puente con CU-O04)."""
    from models_dashboards import calidad_vigente
    return calidad_vigente(client, ventana_horas)


def _lectura_clickhouse():
    """Lectura por defecto: SOLO ClickHouse (RN-1202)."""
    import serving
    return serving.reporte_diario_fuentes()


# ── Archivo por fecha (RF-1105 / RN-1205) ─────────────────────────────────────
def archivar(reporte: dict, base_dir: Path = ARCHIVO_DIR) -> Path:
    """Persiste el reporte como JSON por fecha. Idempotente (sobrescribe)."""
    base_dir.mkdir(parents=True, exist_ok=True)
    out = base_dir / f"reporte_diario_{reporte['fecha']}.json"
    out.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ── Evento de generación para observabilidad/alertas (salidas §8 · T-15) ──────
def _emitir_evento(reporte: dict) -> None:
    nivel = "INFO" if reporte["estado"] == PUBLICADO else "ALERTA"
    evento = {"cu": "CU-O16", "fecha": reporte.get("fecha"),
              "estado": reporte.get("estado"), "periodo": reporte.get("periodo"),
              "motivo": reporte.get("motivo")}
    print(f"[{nivel}] reporte_diario {json.dumps(evento, ensure_ascii=False)}")


def _persistir_pb(reporte: dict, client) -> None:
    """Registra el reporte en PocketBase (auditoría, best-effort). No altera el
    resultado si PocketBase no está accesible."""
    try:
        import models_reportes
        models_reportes.registrar_reporte(reporte, client=client)
    except Exception as exc:  # best-effort: la generación no depende de PocketBase
        print(f"[WARN] No se pudo registrar el reporte en PocketBase: {exc}")


# ── Orquestación (RF-1103: se invoca como último paso del DAG) ────────────────
def generar(fecha: str | None = None, *, lectura=None, gate=None, client=None,
            archivar_fn=None, persistir=True, ventana_horas: float = 24) -> dict:
    """Genera el reporte operativo diario.

    Orden: gate de calidad (RF-1104) → lectura ClickHouse (RN-1202) → consolidación
    (RF-1101) → archivo por fecha (RF-1105) → evento (§8).
    `lectura`/`gate` son inyectables para pruebas sin Docker.
    """
    fecha = fecha or date.today().isoformat()
    gate = gate or (lambda: _gate_calidad(client, ventana_horas))
    archivar_fn = archivar_fn or archivar
    generado_en = datetime.now().isoformat(timespec="seconds")

    # ── RF-1104 / RN-1201: sin calidad vigente del día NO hay reporte definitivo ──
    cal = gate()
    if not cal.get("ok"):
        reporte = {
            "fecha": fecha, "estado": BLOQUEADO_SIN_CALIDAD, "calidad_ok": False,
            "motivo": cal.get("motivo"), "sello": (cal.get("sello") or {}).get("id", ""),
            "version": REPORTE_VERSION, "generado_en": generado_en,
        }
        archivar_fn(reporte)
        _emitir_evento(reporte)
        if persistir:
            _persistir_pb(reporte, client)
        return reporte

    # ── RF-1102 / RN-1202: las cifras vienen SOLO de ClickHouse ───────────────────
    lectura = lectura or _lectura_clickhouse
    fuentes = lectura()
    if not fuentes:
        reporte = {
            "fecha": fecha, "estado": FALLIDO, "calidad_ok": True,
            "motivo": "ClickHouse sin agregaciones del período (RN-1202): no se "
                      "puede construir el reporte sin leer otra capa.",
            "sello": (cal.get("sello") or {}).get("id", ""),
            "version": REPORTE_VERSION, "generado_en": generado_en,
        }
        _emitir_evento(reporte)
        if persistir:
            _persistir_pb(reporte, client)
        return reporte

    # ── RF-1101: consolidación determinista + archivo ────────────────────────────
    reporte = consolidar(fecha, fuentes, (cal.get("sello") or {}).get("id", ""))
    reporte["generado_en"] = generado_en
    archivar_fn(reporte)
    _emitir_evento(reporte)
    if persistir:
        _persistir_pb(reporte, client)
    return reporte


def main() -> int:
    reporte = generar()
    print("\n" + "=" * 56)
    print("REPORTE OPERATIVO DIARIO (CU-O16)")
    print("=" * 56)
    print(json.dumps({k: v for k, v in reporte.items() if k != "trazabilidad"},
                     ensure_ascii=False, indent=2))
    # El DAG trata BLOQUEADO/FALLIDO como fallo de la tarea (fail-fast del reporte).
    return 0 if reporte["estado"] == PUBLICADO else 1


if __name__ == "__main__":
    sys.exit(main())
