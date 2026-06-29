"""
db/pb_setup.py — Bootstrap idempotente de las colecciones operacionales en
PocketBase para CU-O08 (OP5 · paquete `suscripciones`).

Crea (solo si faltan) y siembra las colecciones base alineadas al modelo
Fact-Dim del DW. NO toca StarRocks ni ClickHouse: la capa operacional vive
exclusivamente en PocketBase y el DW se nutre después vía ETL (RN-606, RT-01).

Colecciones:
  - planes               → Dim_Plan            (basico / profesional / enterprise)
  - estados_suscripcion  → Dim_Estado_Suscripcion (PRUEBA/ACTIVA/EN_PAUSA/CANCELADA)
  - clientes             → Dim_Cliente         (tipo, tamano, segmento, mercado)
  - suscripciones        → (plan, monto, periodo, inicio, estado)
  - eventos_suscripcion  → feed de eventos para Fact_Suscripcion (RF-506)

Idempotente: `ensure_collection` no recrea lo existente; el sembrado usa
`find_one` antes de insertar.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pb_client import PBClient, get_client

# ── Definición de campos (PocketBase 0.22 → clave `schema`) ───────────────────
_TEXT = lambda name, required=False: {"name": name, "type": "text",
                                      "required": required, "options": {}}
_NUM = lambda name, required=False: {"name": name, "type": "number",
                                     "required": required, "options": {}}
_BOOL = lambda name: {"name": name, "type": "bool", "required": False, "options": {}}
_DATE = lambda name: {"name": name, "type": "date", "required": False, "options": {}}

COLLECTIONS: dict[str, list[dict]] = {
    "planes": [
        _TEXT("codigo", required=True),      # basico | profesional | enterprise
        _TEXT("nombre", required=True),
        _NUM("id_plan", required=True),       # mapea a Dim_Plan.id_plan
        _NUM("precio_mensual", required=True),
        _TEXT("periodo"),                     # mensual | anual (periodo base)
    ],
    "estados_suscripcion": [
        _TEXT("codigo", required=True),       # PRUEBA | ACTIVA | EN_PAUSA | CANCELADA
        _TEXT("nombre", required=True),
        _NUM("id_estado", required=True),     # mapea a Dim_Estado_Suscripcion.id_estado
    ],
    "clientes": [
        _TEXT("razon_social", required=True),
        _TEXT("id_fiscal"),                   # clave de dedup (RN-601)
        _TEXT("email_corp"),                  # clave de dedup (RN-601)
        _TEXT("tipo"),                        # bodega | distribuidor | retailer ...
        _TEXT("tamano"),                      # micro | pequena | mediana | grande
        _TEXT("segmento"),
        _TEXT("mercado"),                     # → Dim_Mercado
        _DATE("fecha_alta"),
    ],
    "suscripciones": [
        _TEXT("cliente", required=True),      # id del registro en `clientes`
        _TEXT("plan", required=True),         # codigo en `planes`
        _NUM("monto", required=True),
        _TEXT("moneda"),                      # USD por defecto
        _TEXT("periodo", required=True),      # mensual | anual
        _TEXT("estado", required=True),       # codigo en `estados_suscripcion`
        _DATE("inicio"),
        _DATE("fin"),
        _BOOL("facturacion_ok"),              # gate de activación (RN-602)
        _TEXT("metodo_pago"),                 # token enmascarado, NUNCA tarjeta (RNF-505)
    ],
    "eventos_suscripcion": [
        _TEXT("suscripcion", required=True),
        _TEXT("cliente", required=True),
        _TEXT("plan", required=True),
        _TEXT("tipo_evento", required=True),  # alta|upgrade|downgrade|pausa|cancelacion|reactivacion
        _NUM("monto"),
        _NUM("mrr_delta"),
        _TEXT("estado"),
        _TEXT("usuario"),                     # auditoría: quién (RNF-503)
        _DATE("fecha"),                       # auditoría: cuándo (RNF-503)
    ],
}

# ── Semillas de catálogo (Dim_Plan / Dim_Estado_Suscripcion) ──────────────────
PLANES_SEED = [
    {"codigo": "basico",       "nombre": "Básico",       "id_plan": 1, "precio_mensual": 49.0,  "periodo": "mensual"},
    {"codigo": "profesional",  "nombre": "Profesional",  "id_plan": 2, "precio_mensual": 149.0, "periodo": "mensual"},
    {"codigo": "enterprise",   "nombre": "Enterprise",   "id_plan": 3, "precio_mensual": 499.0, "periodo": "mensual"},
]

ESTADOS_SEED = [
    {"codigo": "PRUEBA",    "nombre": "En prueba", "id_estado": 1},
    {"codigo": "ACTIVA",    "nombre": "Activa",    "id_estado": 2},
    {"codigo": "EN_PAUSA",  "nombre": "En pausa",  "id_estado": 3},
    {"codigo": "CANCELADA", "nombre": "Cancelada", "id_estado": 4},
]


def _seed(client: PBClient, collection: str, rows: list[dict], key: str) -> int:
    creados = 0
    for row in rows:
        if client.find_one(collection, **{key: row[key]}) is None:
            client.create(collection, row)
            creados += 1
    return creados


def setup(client: PBClient | None = None) -> dict:
    """Crea/siembra colecciones. Idempotente. Devuelve un reporte."""
    client = client or get_client()
    if not client.health():
        raise RuntimeError("PocketBase no está accesible; no se puede inicializar.")

    creadas = []
    for name, schema in COLLECTIONS.items():
        if client.ensure_collection(name, schema):
            creadas.append(name)

    n_planes = _seed(client, "planes", PLANES_SEED, "codigo")
    n_estados = _seed(client, "estados_suscripcion", ESTADOS_SEED, "codigo")

    return {
        "colecciones_creadas": creadas,
        "planes_sembrados": n_planes,
        "estados_sembrados": n_estados,
    }


if __name__ == "__main__":
    print(setup())
