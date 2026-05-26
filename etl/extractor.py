"""
Extrae todos los registros de la coleccion retail_data en PocketBase
paginando de 500 en 500 y guarda el resultado en stage/retail_raw.parquet.
"""

import sys
from pathlib import Path
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    POCKETBASE_URL, POCKETBASE_COLLECTION, STAGE_DIR,
    POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD,
)

ENDPOINT  = f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records"
OUT_FILE  = Path(STAGE_DIR) / "wine_raw.parquet"
PAGE_SIZE = 500

AUTH_ENDPOINTS = [
    f"{POCKETBASE_URL}/api/collections/_superusers/auth-with-password",
    f"{POCKETBASE_URL}/api/_superusers/auth-with-password",
    f"{POCKETBASE_URL}/api/admins/auth-with-password",
]


def _get_auth_token() -> str:
    payload = {"identity": POCKETBASE_ADMIN_EMAIL, "password": POCKETBASE_ADMIN_PASSWORD}
    for url in AUTH_ENDPOINTS:
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                token = r.json().get("token", "")
                if token:
                    return token
        except requests.RequestException:
            continue
    raise RuntimeError("No se pudo obtener token de PocketBase.")


def extract(page_size: int = PAGE_SIZE) -> Path:
    print("Autenticando en PocketBase ...")
    token = _get_auth_token()
    print("  [OK] Token obtenido\n")
    auth_headers = {"Authorization": f"Bearer {token}"}

    Path(STAGE_DIR).mkdir(exist_ok=True)

    records: list[dict] = []
    page = 1
    total_pages = None

    print(f"Extrayendo de PocketBase -> {ENDPOINT}")
    print(f"Tamano de pagina: {page_size} registros\n")

    while True:
        try:
            resp = requests.get(
                ENDPOINT,
                params={"page": page, "perPage": page_size},
                headers=auth_headers,
                timeout=30,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            print(f"\n[ERROR] No se puede conectar a PocketBase en {POCKETBASE_URL}")
            print("  Verifique que PocketBase este corriendo y vuelva a intentarlo.")
            sys.exit(1)
        except requests.exceptions.HTTPError as exc:
            print(f"\n[ERROR] HTTP {exc.response.status_code}: {exc.response.text[:200]}")
            sys.exit(1)

        data = resp.json()

        if total_pages is None:
            total_pages = data.get("totalPages", 1)
            total_items = data.get("totalItems", "?")
            print(f"Total de registros en PocketBase: {total_items:,}")
            print(f"Total de paginas: {total_pages}\n")

        items = data.get("items", [])
        if not items:
            break

        # Quitar campos meta de PocketBase antes de acumular
        meta = {"id", "collectionId", "collectionName", "created", "updated", "expand"}
        clean_items = [{k: v for k, v in item.items() if k not in meta} for item in items]
        records.extend(clean_items)

        pct = page / total_pages * 100
        print(f"  Pagina {page:>4}/{total_pages}  |  {len(records):>8,} registros acumulados  |  {pct:5.1f}%")

        if page >= total_pages:
            break
        page += 1

    print(f"\nCombinando {len(records):,} registros en DataFrame ...")
    df = pd.DataFrame(records)

    df.to_parquet(OUT_FILE, index=False)

    size_bytes = OUT_FILE.stat().st_size
    if size_bytes >= 1_048_576:
        size_str = f"{size_bytes / 1_048_576:.2f} MB"
    else:
        size_str = f"{size_bytes / 1_024:.1f} KB"

    print(f"\nArchivo guardado: {OUT_FILE}")
    print(f"  Filas:   {len(df):,}")
    print(f"  Columnas:{len(df.columns)}")
    print(f"  Tamano:  {size_str}")

    return OUT_FILE


if __name__ == "__main__":
    extract()
