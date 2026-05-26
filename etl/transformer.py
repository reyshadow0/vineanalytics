"""
ETL — Transform (T).

Lee stage/wine_raw.parquet y produce el modelo estrella para VinAnalytics:
  dim_pais, dim_variedad, dim_bodega, dim_provincia, dim_region, dim_catador
  fact_resenas (con claves foráneas resueltas)
"""

import sys
from pathlib import Path
from typing import Callable

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import STAGE_DIR

RAW_FILE  = Path(STAGE_DIR) / "wine_raw.parquet"
CLEAN_FILE = Path(STAGE_DIR) / "wine_clean.parquet"

_DIM_SPECS = [
    # (nombre_dim, columna_src, col_id)
    ("dim_pais",      "country",     "id_pais"),
    ("dim_variedad",  "variety",     "id_variedad"),
    ("dim_bodega",    "winery",      "id_bodega"),
    ("dim_provincia", "province",    "id_provincia"),
    ("dim_region",    "region_1",    "id_region"),
]


def _log(msg: str, cb: Callable | None = None) -> None:
    print(msg)
    if cb:
        cb(msg)


def _build_dim(series: pd.Series, id_col: str) -> pd.DataFrame:
    unique_vals = (
        series.fillna("Desconocido")
              .astype(str).str.strip()
              .replace("", "Desconocido")
              .unique()
    )
    return pd.DataFrame({id_col: range(1, len(unique_vals) + 1), "nombre": unique_vals})


def transform(
    raw_path: Path = RAW_FILE,
    out_path: Path = CLEAN_FILE,
    log_cb: Callable | None = None,
) -> dict[str, pd.DataFrame]:

    _log(f"[T] Leyendo {raw_path} ...", log_cb)
    df = pd.read_parquet(raw_path)
    _log(f"    {len(df):,} filas, {len(df.columns)} columnas en bruto", log_cb)

    # ── 1. Limpiar columnas ────────────────────────────────────────────────
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]

    required = ["country", "description", "designation", "points", "price",
                "province", "region_1", "region_2", "taster_name",
                "taster_twitter_handle", "title", "variety", "winery"]
    for col in required:
        if col not in df.columns:
            df[col] = None

    # ── 2. Limpiar tipos ───────────────────────────────────────────────────
    _log("[T] Limpiando tipos ...", log_cb)
    df["points"] = pd.to_numeric(df["points"], errors="coerce").fillna(0).astype(int)
    df["price"]  = pd.to_numeric(df["price"],  errors="coerce").fillna(0.0).round(2)

    for col in ["country", "variety", "winery", "province",
                "region_1", "region_2", "designation", "title",
                "taster_name", "taster_twitter_handle", "description"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    df.to_parquet(out_path, index=False)
    _log(f"[T] wine_clean.parquet guardado: {len(df):,} filas", log_cb)

    result: dict[str, pd.DataFrame] = {}

    # ── 3. Dimensiones simples ─────────────────────────────────────────────
    _log("\n[T] Construyendo dimensiones:", log_cb)
    for dim_name, src_col, id_col in _DIM_SPECS:
        dim_df = _build_dim(df[src_col], id_col)
        result[dim_name] = dim_df
        dim_df.to_parquet(Path(STAGE_DIR) / f"{dim_name}.parquet", index=False)
        _log(f"    {dim_name:25s}  {len(dim_df):>5,} valores únicos", log_cb)

    # ── 4. dim_catador (nombre + twitter) ─────────────────────────────────
    catadores = (
        df[["taster_name", "taster_twitter_handle"]]
        .copy()
        .fillna("")
        .replace("", "Anónimo")
        .drop_duplicates(subset=["taster_name"])
        .reset_index(drop=True)
    )
    catadores.insert(0, "id_catador", range(1, len(catadores) + 1))
    catadores = catadores.rename(columns={
        "taster_name":           "nombre",
        "taster_twitter_handle": "twitter",
    })
    result["dim_catador"] = catadores
    catadores.to_parquet(Path(STAGE_DIR) / "dim_catador.parquet", index=False)
    _log(f"    {'dim_catador':25s}  {len(catadores):>5,} catadores únicos", log_cb)

    # ── 5. Resolver FKs ────────────────────────────────────────────────────
    _log("\n[T] Resolviendo claves foráneas ...", log_cb)
    for dim_name, src_col, id_col in _DIM_SPECS:
        dim_df = result[dim_name]
        lookup = dict(zip(dim_df["nombre"], dim_df[id_col]))
        df[id_col] = df[src_col].fillna("Desconocido").astype(str).str.strip().map(lookup)

    catador_lookup = dict(zip(catadores["nombre"], catadores["id_catador"]))
    df["id_catador"] = df["taster_name"].fillna("Anónimo").replace("", "Anónimo").map(catador_lookup)

    # ── 6. fact_resenas ────────────────────────────────────────────────────
    _log("[T] Construyendo fact_resenas ...", log_cb)
    fact_cols = [
        "points", "price", "title", "designation", "description", "region_2",
        "id_pais", "id_variedad", "id_bodega", "id_provincia", "id_region", "id_catador",
    ]
    df_fact = df[fact_cols].copy().reset_index(drop=True)
    df_fact.insert(0, "id_resena", range(1, len(df_fact) + 1))
    df_fact["description"] = df_fact["description"].str[:1000]

    fk_cols = ["id_pais", "id_variedad", "id_bodega", "id_provincia", "id_region", "id_catador"]
    antes = len(df_fact)
    df_fact = df_fact.dropna(subset=fk_cols).reset_index(drop=True)
    if antes - len(df_fact):
        _log(f"    {antes - len(df_fact):,} filas descartadas por FK nula", log_cb)

    result["fact_resenas"] = df_fact
    df_fact.to_parquet(Path(STAGE_DIR) / "fact_resenas.parquet", index=False)

    _log("\n" + "=" * 56, log_cb)
    _log("RESUMEN ETL — TRANSFORM", log_cb)
    _log("=" * 56, log_cb)
    for name, tbl in result.items():
        _log(f"  {name:30s}  {len(tbl):>8,} filas", log_cb)
    _log("=" * 56, log_cb)

    return result


if __name__ == "__main__":
    transform()
