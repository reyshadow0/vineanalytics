"""
Transporte de agregaciones StarRocks → ClickHouse (OP3 · Fase 2).

Última etapa del flujo de datos (Princ. IX: ... → agregaciones). Tras `dbt run`,
las agregaciones del dashboard/API/reporte viven como VISTAS declarativas en
StarRocks (`dbt_vinanalytics/models/serving/agg_*.sql`, Princ. VI). Este módulo
NO calcula nada: solo TRANSPORTA cada vista `agg_*` a su tabla homónima en
ClickHouse (capa de serving de baja latencia).

  - Respeta el orden de capas: ClickHouse se alimenta SOLO desde StarRocks (RT-02),
    nunca desde PocketBase.
  - Idempotente: TRUNCATE + INSERT por tabla.
  - Sin SQL analítico ni lógica de agregación: eso es ahora exclusivo de DBT
    (regla B de la auditoría / Princ. VI). Antes este archivo embebía el GROUP BY
    y lo duplicaba en app.py; ya no.

Cubre las agregaciones de vino (KPIs, países, variedades, puntuación, bodegas,
regiones), BSC (KPIs + series/rankings) y el reporte operativo diario (CU-O16).

El DAG de Airflow (fase posterior) ejecuta esta etapa SOLO si las suites de
calidad (CU-O04) pasaron (fail-fast).
"""

import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB, STARROCKS_USER, STARROCKS_PASS,
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_DB, CLICKHOUSE_USER, CLICKHOUSE_PASS,
)

DDL_FILE = Path(__file__).resolve().parent / "aggregations.sql"


# ── Especificación del transporte ──────────────────────────────────────────────
# Para cada agregación: (vista_starrocks == tabla_clickhouse, [(columna, tipo)]).
# tipo ∈ {i: int, f: float, s: str} — coacciona el valor de StarRocks (Decimal/None)
# al tipo Python que espera la columna ClickHouse (UInt/Int → i, Float64 → f,
# String → s). El nombre de la vista en StarRocks coincide con el de la tabla
# ClickHouse, así que el transporte es 1:1.
AGGS: list[tuple[str, list[tuple[str, str]]]] = [
    ("agg_kpis_vino", [
        ("total_resenas", "i"), ("puntuacion_promedio", "f"), ("precio_promedio", "f"),
        ("precio_maximo", "f"), ("precio_minimo", "f"), ("total_paises", "i"),
        ("total_variedades", "i"), ("total_bodegas", "i"),
    ]),
    ("agg_pais", [
        ("pais", "s"), ("total", "i"), ("puntuacion_promedio", "f"),
        ("precio_promedio", "f"), ("variedades", "i"),
    ]),
    ("agg_variedad", [
        ("variedad", "s"), ("total", "i"), ("precio_promedio", "f"), ("total_con_precio", "i"),
    ]),
    ("agg_bodega", [
        ("bodega", "s"), ("total", "i"), ("puntuacion_promedio", "f"),
    ]),
    ("agg_region", [
        ("region", "s"), ("total", "i"),
    ]),
    ("agg_puntuacion_hist", [
        ("puntuacion", "i"), ("total", "i"),
    ]),
    ("agg_bsc_kpis", [
        ("periodo", "s"), ("clientes_activos", "i"), ("mrr_actual", "f"), ("mrr_growth", "f"),
        ("api_share", "f"), ("cac", "f"), ("ltv_cac", "f"), ("cloud_cli", "f"),
        ("conversion", "f"), ("churn", "f"), ("nps", "f"), ("adopcion", "f"),
        ("nuevos_trim", "f"), ("uptime", "f"), ("ttm", "f"), ("latencia", "f"),
        ("calidad", "f"), ("horas", "f"), ("ddd", "f"), ("mlmod", "f"),
        ("rotacion", "f"), ("tecno", "f"),
    ]),
    ("agg_bsc_series", [
        ("perspectiva", "s"), ("serie", "s"), ("etiqueta", "s"), ("orden", "i"), ("valor", "f"),
    ]),
    ("agg_reporte_diario", [
        ("id_tiempo", "i"), ("periodo", "s"), ("api_llamadas", "i"), ("api_errores", "i"),
        ("api_latencia_ms", "f"), ("api_ingreso", "f"), ("uso_sesiones", "i"),
        ("uso_funciones", "i"), ("uso_usuarios_activos", "i"), ("uso_dashboards", "i"),
        ("incidentes", "i"), ("uptime", "f"), ("despliegues", "i"),
    ]),
]


# ── Conexiones ────────────────────────────────────────────────────────────────

def _sr() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST, port=STARROCKS_PORT, database=STARROCKS_DB,
        user=STARROCKS_USER, password=STARROCKS_PASS, connection_timeout=20,
    )


def _ch():
    import clickhouse_connect
    # Conecta a 'default' para poder crear la base si no existe.
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER, password=CLICKHOUSE_PASS,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _rows(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    out = cur.fetchall()
    cur.close()
    return out


def _coerce(value, kind: str):
    """Coacciona un valor de StarRocks (Decimal/None/...) al tipo de la columna CH."""
    if kind == "s":
        return "" if value is None else str(value)
    if kind == "i":
        return 0 if value is None else int(value)
    # "f"
    return 0.0 if value is None else float(value)


def _run_ddl(ch):
    sql = DDL_FILE.read_text(encoding="utf-8")
    # El DDL fija el nombre 'vinanalytics'; si CLICKHOUSE_DB difiere, lo alineamos.
    if CLICKHOUSE_DB != "vinanalytics":
        sql = sql.replace("vinanalytics", CLICKHOUSE_DB)
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        ch.command(stmt)


def _reset(ch, table):
    ch.command(f"TRUNCATE TABLE IF EXISTS {CLICKHOUSE_DB}.{table}")


# ── Transporte 1:1 (sin agregación) ──────────────────────────────────────────────

def _transportar(sr, ch, table: str, columns: list[tuple[str, str]]) -> int:
    """Lee la vista `agg_*` de StarRocks y la inserta en ClickHouse tal cual.

    Idempotente (TRUNCATE + INSERT). No hay GROUP BY ni CASE aquí: la lógica de
    agregación vive exclusivamente en los modelos DBT (Princ. VI).
    """
    names = [c for c, _ in columns]
    kinds = [k for _, k in columns]
    col_sql = ", ".join(names)
    rows = _rows(sr, f"SELECT {col_sql} FROM {table}")

    _reset(ch, table)
    if rows:
        data = [[_coerce(v, kinds[i]) for i, v in enumerate(r)] for r in rows]
        ch.insert(f"{CLICKHOUSE_DB}.{table}", data, column_names=names)
    print(f"  [OK] {table:22s} {len(rows):>6,} filas transportadas")
    return len(rows)


def populate() -> dict:
    print("Conectando a StarRocks y ClickHouse ...")
    sr = _sr()
    ch = _ch()
    counts: dict[str, int] = {}
    try:
        _run_ddl(ch)
        print("  [OK] Esquema ClickHouse asegurado\n")
        for table, columns in AGGS:
            counts[table] = _transportar(sr, ch, table, columns)
    finally:
        sr.close()
        ch.close()
    print("\n" + "=" * 56)
    print("AGREGACIONES ClickHouse ACTUALIZADAS (transporte desde DBT)")
    print("=" * 56)
    return {"ok": True, "filas": counts}


if __name__ == "__main__":
    populate()
