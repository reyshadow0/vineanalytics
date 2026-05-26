"""
Borra TODOS los registros de la coleccion retail_data en PocketBase.
1. Autentica como superusuario
2. Pagina de 500 en 500 para obtener todos los IDs
3. Borra cada registro con DELETE /api/collections/retail_data/records/{id}
4. Verifica que la coleccion quede en 0 registros
"""

import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from config import (
    POCKETBASE_URL, POCKETBASE_COLLECTION,
    POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD,
)

LIST_ENDPOINT   = f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records"
DELETE_ENDPOINT = f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records"

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


def _make_session(token: str) -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _fetch_all_ids(session: requests.Session, page_size: int = 500) -> list[str]:
    ids: list[str] = []
    page = 1
    total_pages = None

    print(f"Obteniendo IDs de '{POCKETBASE_COLLECTION}' ...")
    while True:
        resp = session.get(
            LIST_ENDPOINT,
            params={"page": page, "perPage": page_size, "fields": "id"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if total_pages is None:
            total_pages = data.get("totalPages", 1)
            total_items = data.get("totalItems", "?")
            print(f"  Total registros: {total_items:,}  |  Paginas: {total_pages}")

        items = data.get("items", [])
        if not items:
            break

        ids.extend(item["id"] for item in items)
        pct = page / total_pages * 100
        print(f"  Pagina {page:>4}/{total_pages}  ({pct:5.1f}%)  IDs acumulados: {len(ids):,}",
              end="\r", flush=True)

        if page >= total_pages:
            break
        page += 1

    print()
    return ids


def reset() -> None:
    print(f"Verificando PocketBase ({POCKETBASE_URL}) ...")
    try:
        r = requests.get(f"{POCKETBASE_URL}/api/health", timeout=5)
        if r.status_code != 200:
            raise RuntimeError(f"PocketBase HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"No se puede conectar a {POCKETBASE_URL}")
    print("  [OK] PocketBase accesible\n")

    print("Autenticando ...")
    token = _get_auth_token()
    print("  [OK] Token obtenido\n")

    session = _make_session(token)

    # ── 1. Obtener todos los IDs ─────────────────────────────────────────────
    ids = _fetch_all_ids(session)
    total = len(ids)

    if total == 0:
        print("La coleccion ya esta vacia. Nada que borrar.")
        session.close()
        return

    print(f"\nBorrando {total:,} registros ...\n")

    # ── 2. Borrar uno a uno ──────────────────────────────────────────────────
    deleted = 0
    errors  = 0

    for i, record_id in enumerate(ids, start=1):
        try:
            resp = session.delete(f"{DELETE_ENDPOINT}/{record_id}", timeout=15)
            if resp.status_code in (200, 204):
                deleted += 1
            else:
                errors += 1
                if errors <= 5:
                    print(f"\n  [WARN] ID {record_id}: HTTP {resp.status_code} -- {resp.text[:80]}")
        except requests.RequestException as exc:
            errors += 1
            if errors <= 5:
                print(f"\n  [ERROR] ID {record_id}: {exc}")

        if i % 500 == 0 or i == total:
            pct = i / total * 100
            bar_len = 38
            filled  = int(bar_len * i / total)
            bar     = "=" * filled + "-" * (bar_len - filled)
            print(f"  [{bar}] {pct:5.1f}%  borrados={deleted:,}  errores={errors:,}",
                  end="\r", flush=True)

    print()
    session.close()

    # ── 3. Verificar que quedo en 0 ──────────────────────────────────────────
    print("\nVerificando coleccion ...")
    token2   = _get_auth_token()
    session2 = _make_session(token2)
    resp = session2.get(LIST_ENDPOINT, params={"page": 1, "perPage": 1}, timeout=10)
    session2.close()
    remaining = resp.json().get("totalItems", "?")

    print(f"  Registros borrados: {deleted:,}")
    print(f"  Errores:            {errors:,}")
    print(f"  Registros restantes en PocketBase: {remaining}")

    if remaining == 0:
        print("\n  [OK] Coleccion vaciada correctamente.")
    else:
        print(f"\n  [WARN] Quedaron {remaining} registros. Puede re-ejecutar el script.")


if __name__ == "__main__":
    reset()
