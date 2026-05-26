"""
Lee winemag-data-130k-v2.csv y lo sube a PocketBase en lotes.
"""

import sys
import math
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from config import (
    POCKETBASE_URL, POCKETBASE_COLLECTION, CSV_PATH, ETL_BATCH_SIZE,
    POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD,
)

ENDPOINT = f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records"

AUTH_ENDPOINTS = [
    f"{POCKETBASE_URL}/api/collections/_superusers/auth-with-password",
    f"{POCKETBASE_URL}/api/_superusers/auth-with-password",
    f"{POCKETBASE_URL}/api/admins/auth-with-password",
]


def _make_session(token: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=1, pool_maxsize=1)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


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


def _safe(val, default=""):
    if val is None:
        return default
    try:
        import math as _m
        if isinstance(val, float) and _m.isnan(val):
            return default
    except Exception:
        pass
    return val


def _to_pb_record(row: dict) -> dict:
    return {
        "country":               str(_safe(row.get("country"), "")),
        "description":           str(_safe(row.get("description"), ""))[:2000],
        "designation":           str(_safe(row.get("designation"), "")),
        "points":                int(_safe(row.get("points"), 0)),
        "price":                 float(_safe(row.get("price"), 0.0)),
        "province":              str(_safe(row.get("province"), "")),
        "region_1":              str(_safe(row.get("region_1"), "")),
        "region_2":              str(_safe(row.get("region_2"), "")),
        "taster_name":           str(_safe(row.get("taster_name"), "")),
        "taster_twitter_handle": str(_safe(row.get("taster_twitter_handle"), "")),
        "title":                 str(_safe(row.get("title"), "")),
        "variety":               str(_safe(row.get("variety"), "")),
        "winery":                str(_safe(row.get("winery"), "")),
    }


def upload(csv_path: str = CSV_PATH, batch_size: int = ETL_BATCH_SIZE,
           skip_rows: int = 0) -> int:
    print(f"Verificando PocketBase ({POCKETBASE_URL}) ...")
    try:
        r = requests.get(f"{POCKETBASE_URL}/api/health", timeout=5)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"No se puede conectar a PocketBase en {POCKETBASE_URL}")
    print("  [OK] PocketBase accesible")

    print("  Autenticando ...")
    token   = _get_auth_token()
    session = _make_session(token)
    print("  [OK] Token obtenido\n")

    print(f"Leyendo {csv_path} ...")
    df = pd.read_csv(csv_path)
    # Eliminar columna índice si existe
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    total = len(df)

    if skip_rows > 0:
        df = df.iloc[skip_rows:]

    total_batches = math.ceil(len(df) / batch_size)
    print(f"  {total:,} filas totales  |  {total_batches} lotes de {batch_size}\n")

    inserted = 0
    errors   = 0

    for batch_num, batch_start in enumerate(range(0, len(df), batch_size)):
        batch_rows = df.iloc[batch_start : batch_start + batch_size].to_dict(orient="records")
        batch_errors = 0

        for row in batch_rows:
            try:
                resp = session.post(ENDPOINT, json=_to_pb_record(row), timeout=15)
                if resp.status_code in (200, 201):
                    inserted += 1
                else:
                    errors += 1
                    batch_errors += 1
                    if batch_errors <= 2:
                        print(f"    [WARN] HTTP {resp.status_code} -- {resp.text[:80]}")
            except requests.exceptions.ConnectionError as exc:
                session.close()
                print(f"\n[FATAL] Conexión perdida: {exc}")
                print(f"  Para reanudar: --skip {batch_start + skip_rows}")
                sys.exit(1)

        pct = (batch_num + 1) / total_batches * 100
        print(f"  Lote {batch_num+1:>3}/{total_batches}  ({pct:5.1f}%)  "
              f"insertados={inserted:,}  errores={errors}")

    session.close()
    print(f"\nCarga completa: {inserted:,} insertados, {errors} errores.")
    return inserted


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip", type=int, default=0)
    args = parser.parse_args()
    upload(skip_rows=args.skip)
