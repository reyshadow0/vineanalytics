"""
etl/extractor.py — Punto de entrada de ingesta de reseñas (CU-O02, OP1).

Conserva el contrato histórico del DAG (`python -m etl.extractor` →
stage/wine_raw.parquet), pero ahora delega en el catálogo de fuentes (CU-O01,
`etl/source_catalog.py`) y el motor de ingesta (`etl/ingesta.py`):

  1. Garantiza que la fuente `wine_reviews` esté registrada y HABILITADA (RN-201).
  2. Lee el incremento desde PocketBase.
  3. Valida esquema, deduplica por clave natural, desvía rechazos a `rejects/` y
     escribe Parquet snappy (particionado + vista plana wine_raw.parquet).
  4. Emite el reporte de ingesta (filas leídas/cargadas/rechazadas/duplicadas).

No transforma a Fact-Dim ni toca StarRocks (RN-206): eso es OP2 (CU-O03).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import POCKETBASE_COLLECTION, STAGE_DIR
from pb_client import get_client
from etl import ingesta, source_catalog

OUT_FILE = Path(STAGE_DIR) / "wine_raw.parquet"
PAGE_SIZE = 500


def extract(page_size: int = PAGE_SIZE) -> Path:
    """Ingiere la fuente de reseñas de PocketBase a staging. Devuelve el Parquet
    plano (wine_raw.parquet) para compatibilidad con el ETL/GE posterior."""
    Path(STAGE_DIR).mkdir(exist_ok=True)

    client = get_client()
    if not client.health():
        print("[ERROR] PocketBase no está accesible; no se puede ingerir.")
        sys.exit(1)

    # CU-O01: la fuente debe existir y estar HABILITADA antes de ingerir (RN-201).
    print("Verificando catálogo de fuentes (CU-O01) ...")
    fuente = source_catalog.ensure_fuente_wine_reviews(POCKETBASE_COLLECTION, client)
    print(f"  [OK] Fuente '{fuente['nombre']}' — estado {fuente['estado']}\n")

    print(f"Ingestando '{POCKETBASE_COLLECTION}' (CU-O02) ...")
    reporte = ingesta.ingestar_fuente(fuente, client=client, escribir_plano=True)

    # ── Reporte de ingesta (RF-110) ───────────────────────────────────────────
    print("\n" + "=" * 56)
    print("REPORTE DE INGESTA")
    print("=" * 56)
    for k in ("estado", "filas_leidas", "filas_validas", "filas_duplicadas",
              "filas_rechazadas", "filas_cargadas", "pct_rechazo"):
        if k in reporte:
            print(f"  {k:18s}: {reporte[k]}")
    print(f"  staging           : {reporte.get('ruta_staging')}")
    print(f"  rechazos          : {reporte.get('ruta_rechazos')}")
    print("=" * 56)

    if reporte["estado"] == "FALLIDA":
        print("\n[ALERTA] Lote FALLIDA: el staging NO fue actualizado.")
        sys.exit(1)

    print(f"\nArchivo de staging: {OUT_FILE}")
    return OUT_FILE


if __name__ == "__main__":
    extract()
