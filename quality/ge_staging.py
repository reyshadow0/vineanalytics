"""
Great Expectations — suite PREVIA (staging Parquet) · CU-O04.

Valida los datasets aterrizados en stage/ ANTES de que el ETL/DBT los promueva
al Data Warehouse. Implementa el principio V de la constitución (calidad primero)
con estrategia fail-fast: si una expectativa crítica falla, run_quality.py corta
el pipeline (exit != 0) y no se ejecuta la transformación.

Usa la API PandasDataset de Great Expectations (estable y explícita).
"""

import sys
from pathlib import Path

import pandas as pd
from great_expectations.dataset import PandasDataset

ROOT      = Path(__file__).resolve().parents[1]
STAGE_DIR = ROOT / "stage"


def _validar(df: pd.DataFrame, expectativas) -> dict:
    """Aplica una lista de expectativas a un PandasDataset y agrega el resultado."""
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


def validar_staging() -> dict:
    """Valida los Parquet de staging. Devuelve un reporte agregado."""
    informe = {"suite": "staging", "datasets": {}, "exito": True}

    # ── wine_raw.parquet (ingesta cruda PocketBase → Parquet) ──────────────────
    raw_path = STAGE_DIR / "wine_raw.parquet"
    if raw_path.exists():
        df = pd.read_parquet(raw_path)
        df["points_num"] = pd.to_numeric(df.get("points"), errors="coerce")
        df["price_num"]  = pd.to_numeric(df.get("price"),  errors="coerce")
        exp = [
            lambda d: d.expect_table_row_count_to_be_between(min_value=1),
            lambda d: d.expect_column_to_exist("country"),
            lambda d: d.expect_column_to_exist("variety"),
            lambda d: d.expect_column_to_exist("winery"),
            lambda d: d.expect_column_to_exist("description"),
            # dominio tolerante en crudo (sentinela 0 admitido): mayoría 80..100
            lambda d: d.expect_column_values_to_be_between(
                "points_num", min_value=0, max_value=100, mostly=0.99),
            lambda d: d.expect_column_values_to_be_between(
                "price_num", min_value=0, max_value=100000, mostly=0.99),
        ]
        informe["datasets"]["wine_raw.parquet"] = _validar(df, exp)
    else:
        informe["datasets"]["wine_raw.parquet"] = {
            "exito": False, "evaluadas": 0,
            "fallidas": [{"expectativa": "archivo_existe", "columna": None}],
        }

    # ── fact_resenas.parquet (salida del Transform) ────────────────────────────
    fact_path = STAGE_DIR / "fact_resenas.parquet"
    if fact_path.exists():
        df = pd.read_parquet(fact_path)
        exp = [
            lambda d: d.expect_table_row_count_to_be_between(min_value=1),
            lambda d: d.expect_column_values_to_not_be_null("id_resena"),
            lambda d: d.expect_column_values_to_be_unique("id_resena"),
            lambda d: d.expect_column_values_to_not_be_null("id_pais"),
            lambda d: d.expect_column_values_to_not_be_null("id_variedad"),
            lambda d: d.expect_column_values_to_be_between(
                "points", min_value=0, max_value=100),
            lambda d: d.expect_column_values_to_be_between(
                "price", min_value=0, max_value=100000),
        ]
        informe["datasets"]["fact_resenas.parquet"] = _validar(df, exp)
    else:
        informe["datasets"]["fact_resenas.parquet"] = {
            "exito": False, "evaluadas": 0,
            "fallidas": [{"expectativa": "archivo_existe", "columna": None}],
        }

    informe["exito"] = all(d["exito"] for d in informe["datasets"].values())
    return informe


if __name__ == "__main__":
    import json
    rep = validar_staging()
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    sys.exit(0 if rep["exito"] else 1)
