"""
pb_client.py — Cliente REST mínimo para PocketBase (capa operacional).

Centraliza autenticación de superusuario, CRUD de registros y creación
idempotente de colecciones. Lo usan `db/pb_setup.py` (bootstrap del esquema) y
`models_clientes.py` (lógica de CU-O08). Respeta la arquitectura de capas: aquí
SOLO se habla con PocketBase (operacional); nunca con StarRocks/ClickHouse.

Compatible con PocketBase 0.22.x (campos de colección bajo la clave `schema`).
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    POCKETBASE_URL, POCKETBASE_ADMIN_EMAIL, POCKETBASE_ADMIN_PASSWORD,
)

# Mismos endpoints que ya usan etl/pb_loader.py y etl/reset_pocketbase.py.
_AUTH_PATHS = [
    "/api/collections/_superusers/auth-with-password",
    "/api/_superusers/auth-with-password",
    "/api/admins/auth-with-password",
]


class PBError(RuntimeError):
    """Fallo de comunicación con PocketBase."""


def _quote(value) -> str:
    """Serializa un valor para un filtro PocketBase (string entre comillas)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "\\'") + "'"


class PBClient:
    """Cliente autenticado y reutilizable contra una instancia de PocketBase."""

    def __init__(self, base_url: str = POCKETBASE_URL,
                 email: str = POCKETBASE_ADMIN_EMAIL,
                 password: str = POCKETBASE_ADMIN_PASSWORD,
                 timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.timeout = timeout
        self._session: requests.Session | None = None

    # ── conexión ─────────────────────────────────────────────────────────────
    def _new_session(self, token: str) -> requests.Session:
        s = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        s.headers.update({"Authorization": f"Bearer {token}"})
        return s

    def _authenticate(self) -> str:
        payload = {"identity": self.email, "password": self.password}
        last = ""
        for path in _AUTH_PATHS:
            try:
                r = requests.post(self.base_url + path, json=payload, timeout=self.timeout)
                if r.status_code == 200:
                    token = r.json().get("token", "")
                    if token:
                        return token
                last = f"HTTP {r.status_code}"
            except requests.RequestException as exc:
                last = str(exc)
        raise PBError(f"No se pudo autenticar en PocketBase ({last}).")

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = self._new_session(self._authenticate())
        return self._session

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/health", timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    # ── colecciones (idempotente) ────────────────────────────────────────────
    def collection_exists(self, name: str) -> bool:
        r = self.session.get(f"{self.base_url}/api/collections/{name}",
                             timeout=self.timeout)
        return r.status_code == 200

    def ensure_collection(self, name: str, schema: list[dict],
                          type_: str = "base") -> bool:
        """Crea la colección si no existe. Devuelve True si la creó."""
        if self.collection_exists(name):
            return False
        body = {"name": name, "type": type_, "schema": schema}
        r = self.session.post(f"{self.base_url}/api/collections",
                             json=body, timeout=self.timeout)
        if r.status_code not in (200, 201):
            raise PBError(f"No se pudo crear la colección '{name}': "
                          f"HTTP {r.status_code} — {r.text[:200]}")
        return True

    # ── registros ────────────────────────────────────────────────────────────
    def find(self, collection: str, per_page: int = 200, **filters) -> list[dict]:
        """Lista registros que cumplen TODAS las igualdades de `filters`."""
        params = {"perPage": per_page}
        if filters:
            params["filter"] = " && ".join(
                f"({k}={_quote(v)})" for k, v in filters.items()
            )
        r = self.session.get(
            f"{self.base_url}/api/collections/{collection}/records",
            params=params, timeout=self.timeout,
        )
        if r.status_code != 200:
            raise PBError(f"Listado de '{collection}' falló: HTTP {r.status_code} "
                          f"— {r.text[:200]}")
        return r.json().get("items", [])

    def find_one(self, collection: str, **filters) -> dict | None:
        items = self.find(collection, per_page=1, **filters)
        return items[0] if items else None

    def create(self, collection: str, data: dict) -> dict:
        r = self.session.post(
            f"{self.base_url}/api/collections/{collection}/records",
            json=data, timeout=self.timeout,
        )
        if r.status_code not in (200, 201):
            raise PBError(f"Alta en '{collection}' falló: HTTP {r.status_code} "
                          f"— {r.text[:200]}")
        return r.json()

    def update(self, collection: str, record_id: str, data: dict) -> dict:
        r = self.session.patch(
            f"{self.base_url}/api/collections/{collection}/records/{record_id}",
            json=data, timeout=self.timeout,
        )
        if r.status_code not in (200, 201):
            raise PBError(f"Actualización en '{collection}/{record_id}' falló: "
                          f"HTTP {r.status_code} — {r.text[:200]}")
        return r.json()


# Instancia perezosa compartida por la app (no se conecta hasta el primer uso).
_default_client: PBClient | None = None


def get_client() -> PBClient:
    global _default_client
    if _default_client is None:
        _default_client = PBClient()
    return _default_client
