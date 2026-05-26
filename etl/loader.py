"""
ETL — Load (L).

Carga los DataFrames ya transformados (producidos por etl/transformer.py)
directamente en las tablas de StarRocks.

Flujo:
  1. Ejecuta transform() → dict de DataFrames {tabla: df}
  2. Para cada tabla: TRUNCATE + INSERT en lotes (ETL_BATCH_SIZE filas).

StarRocks usa protocolo MySQL → mysql-connector-python.
"""

import sys
import time
from pathlib import Path
from typing import Callable

import pandas as pd
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS, ETL_BATCH_SIZE,
)

LOAD_ORDER = [
    "dim_pais",
    "dim_variedad",
    "dim_bodega",
    "dim_provincia",
    "dim_region",
    "dim_catador",
    "fact_resenas",
]


def _connect() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        database=STARROCKS_DB,
        user=STARROCKS_USER,
        password=STARROCKS_PASS,
        connection_timeout=15,
    )


def _log(msg: str, cb: Callable[[str], None] | None = None) -> None:
    print(msg)
    if cb:
        cb(msg)


def _insert_table(
    conn: mysql.connector.MySQLConnection,
    table: str,
    df: pd.DataFrame,
    batch_size: int,
    log_cb: Callable[[str], None] | None,
) -> int:
    """TRUNCATE la tabla y carga el DataFrame en lotes con executemany."""
    cur = conn.cursor()

    cur.execute(f"TRUNCATE TABLE `{table}`")
    conn.commit()

    if df.empty:
        cur.close()
        return 0

    cols   = list(df.columns)
    ph     = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(f"`{c}`" for c in cols)
    sql    = f"INSERT INTO `{table}` ({col_list}) VALUES ({ph})"

    total   = len(df)
    loaded  = 0
    batches = (total + batch_size - 1) // batch_size

    for i in range(batches):
        chunk = df.iloc[i * batch_size : (i + 1) * batch_size]
        rows  = [
            tuple(
                None if pd.isna(v) else (bool(v) if isinstance(v, (bool,)) else v)
                for v in row
            )
            for row in chunk.itertuples(index=False, name=None)
        ]
        cur.executemany(sql, rows)
        conn.commit()
        loaded += len(rows)
        pct = loaded / total * 100
        _log(
            f"    [{table}]  {loaded:>8,}/{total:,}  ({pct:.1f}%)",
            log_cb,
        )

    cur.close()
    return loaded


def load(
    tables: dict[str, pd.DataFrame] | None = None,
    limit: int | None = None,
    log_cb: Callable[[str], None] | None = None,
) -> dict[str, int]:
    """
    Carga las tablas en StarRocks.

    Si `tables` es None, invoca transform() para obtenerlas.
    Si `limit` se indica, recorta fact_interacciones a ese número de filas.
    """
    t0 = time.time()

    if tables is None:
        _log("[L] Ejecutando fase Transform primero ...", log_cb)
        from etl.transformer import transform
        tables = transform(log_cb=log_cb)

    if limit is not None and "fact_resenas" in tables:
        original = len(tables["fact_resenas"])
        tables["fact_resenas"] = tables["fact_resenas"].head(limit)
        _log(f"[L] fact_resenas limitada: {limit:,} de {original:,} filas", log_cb)

    _log("\n[L] Conectando a StarRocks ...", log_cb)
    conn = _connect()
    _log(f"    {STARROCKS_HOST}:{STARROCKS_PORT} / {STARROCKS_DB}", log_cb)

    counts: dict[str, int] = {}

    for table in LOAD_ORDER:
        if table not in tables:
            _log(f"  [SKIP]  {table} (no está en el resultado del Transform)", log_cb)
            continue

        df = tables[table]

        # Convertir columnas datetime/date a string para mysql-connector
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df = df.copy()
                df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
            elif df[col].dtype == object and len(df) > 0:
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                import datetime as _dt
                if isinstance(sample, _dt.date) and not isinstance(sample, _dt.datetime):
                    df = df.copy()
                    df[col] = df[col].apply(
                        lambda v: v.isoformat() if isinstance(v, _dt.date) else v
                    )

        _log(f"\n[L] Cargando {table} ({len(df):,} filas) ...", log_cb)
        n = _insert_table(conn, table, df, ETL_BATCH_SIZE, log_cb)
        counts[table] = n

    conn.close()

    elapsed = time.time() - t0
    _log("\n" + "=" * 56, log_cb)
    _log("RESUMEN ETL — LOAD (StarRocks)", log_cb)
    _log("=" * 56, log_cb)
    for t, n in counts.items():
        _log(f"  {t:30s}  {n:>8,} filas", log_cb)
    _log(f"\n  Tiempo total: {elapsed:.1f} s", log_cb)
    _log("=" * 56, log_cb)

    return counts


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ETL Loader → StarRocks")
    parser.add_argument("--limit", type=int, default=None, metavar="N")
    args = parser.parse_args()
    load(limit=args.limit)
