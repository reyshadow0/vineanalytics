"""
Great Expectations — suite POSTERIOR (Data Warehouse StarRocks) · CU-O04.

Valida los marts Fact-Dim producidos por DBT (fct_resena, fct_puntuacion,
fct_precio_mercado) DESPUÉS del Transform y ANTES de promover a agregaciones
(ClickHouse). Es el segundo gate fail-fast del pipeline (Princ. V · RT-07/RT-15):
si falla, run_quality.py corta y la promoción a ClickHouse no ocurre.

Lee las tablas vía protocolo MySQL (mismas credenciales que config.py).
"""

import sys
from pathlib import Path

import pandas as pd
import mysql.connector
from great_expectations.dataset import PandasDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS,
)


def _conn():
    return mysql.connector.connect(
        host=STARROCKS_HOST, port=STARROCKS_PORT, database=STARROCKS_DB,
        user=STARROCKS_USER, password=STARROCKS_PASS, connection_timeout=20,
    )


def _read(sql: str) -> pd.DataFrame:
    conn = _conn()
    try:
        return pd.read_sql(sql, conn)
    finally:
        conn.close()


def _validar(df: pd.DataFrame, expectativas) -> dict:
    ds = PandasDataset(df)
    for fn in expectativas:
        fn(ds)
    res = ds.validate(result_format="SUMMARY")
    fallidas = [r for r in res["results"] if not r["success"]]
    return {
        "exito": bool(res["success"]),
        "evaluadas": len(res["results"]),
        "fallidas": [
            {
                "expectativa": r["expectation_config"]["expectation_type"],
                "columna": r["expectation_config"]["kwargs"].get("column"),
            }
            for r in fallidas
        ],
    }


def validar_dw() -> dict:
    """Valida los marts Fact-Dim en StarRocks. Devuelve un reporte agregado."""
    informe = {"suite": "dw", "datasets": {}, "exito": True}

    try:
        # ── fct_resena ─────────────────────────────────────────────────────────
        df = _read("SELECT id_resena, id_vino, id_mercado, puntos, precio FROM fct_resena")
        informe["datasets"]["fct_resena"] = _validar(df, [
            lambda d: d.expect_table_row_count_to_be_between(min_value=1),
            lambda d: d.expect_column_values_to_not_be_null("id_resena"),
            lambda d: d.expect_column_values_to_be_unique("id_resena"),
            lambda d: d.expect_column_values_to_not_be_null("id_vino"),
            lambda d: d.expect_column_values_to_not_be_null("id_mercado"),
        ])

        # ── fct_puntuacion (dominio estricto 80..100) ───────────────────────────
        df = _read("SELECT id_puntuacion, puntaje FROM fct_puntuacion")
        informe["datasets"]["fct_puntuacion"] = _validar(df, [
            lambda d: d.expect_column_values_to_not_be_null("id_puntuacion"),
            lambda d: d.expect_column_values_to_be_unique("id_puntuacion"),
            lambda d: d.expect_column_values_to_be_between(
                "puntaje", min_value=80, max_value=100),
        ])

        # ── fct_precio_mercado (precio > 0, moneda USD) ─────────────────────────
        df = _read("SELECT id_precio, precio, moneda FROM fct_precio_mercado")
        informe["datasets"]["fct_precio_mercado"] = _validar(df, [
            lambda d: d.expect_column_values_to_not_be_null("id_precio"),
            lambda d: d.expect_column_values_to_be_unique("id_precio"),
            lambda d: d.expect_column_values_to_be_between(
                "precio", min_value=0.01, max_value=100000),
            lambda d: d.expect_column_values_to_be_in_set("moneda", ["USD"]),
        ])

    except mysql.connector.Error as exc:
        informe["datasets"]["_conexion"] = {
            "exito": False, "evaluadas": 0,
            "fallidas": [{"expectativa": "conexion_starrocks", "columna": str(exc)[:120]}],
        }

    informe["exito"] = bool(informe["datasets"]) and all(
        d["exito"] for d in informe["datasets"].values()
    )
    return informe


if __name__ == "__main__":
    import json
    rep = validar_dw()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    sys.exit(0 if rep["exito"] else 1)
