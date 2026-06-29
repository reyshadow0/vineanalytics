"""
etl/source_catalog.py — Catálogo de fuentes de datos externas · CU-O01 (OP1).

Registra y gobierna las fuentes externas del mercado vitivinícola (reseñas,
precios, puntuaciones) en PocketBase (capa operacional). La ingesta (CU-O02,
`etl/ingesta.py`) SOLO lee de fuentes que existan aquí y estén HABILITADAS
(RN-201). Esta capa NUNCA escribe en StarRocks/ClickHouse (RN-206, RT-01).

Reglas de negocio implementadas (ingesta-datos-spec.md):
  - RF-101  Alta con metadatos: nombre, tipo, formato, endpoint, frecuencia, etc.
  - RF-102  Validación de metadatos (y conectividad) ANTES de habilitar la fuente.
  - RF-103  Persistencia en PocketBase + asociación a Dim_Mercado / Dim_Catador.
  - RF-104 / RN-202  Rechazo de alta duplicada (tipo+endpoint+formato) devolviendo
            el id de la fuente existente.
  - RF-105  Activar / pausar / dar de baja sin borrar el historial.

Estados de la fuente (enunciado de la sesión → §9 del spec):
  REGISTRADA   (= BORRADOR, alta validada, aún no operativa)
  HABILITADA   (= ACTIVA, elegible para ingesta)
  DESHABILITADA(= PAUSADA/BAJA, no se ingiere)
  RECHAZADA    (validación de conectividad fallida; terminal hasta corregir)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pb_client import PBClient, PBError, get_client

COLECCION = "fuentes_externas"

# ── Estados (enunciado / §9 del spec) ─────────────────────────────────────────
REGISTRADA, HABILITADA, DESHABILITADA, RECHAZADA = (
    "REGISTRADA", "HABILITADA", "DESHABILITADA", "RECHAZADA",
)

# ── Dominios de metadatos (RF-101) ────────────────────────────────────────────
TIPOS_VALIDOS = ("reseñas", "precios", "puntuaciones")
FORMATOS_VALIDOS = ("json", "parquet", "api", "csv-origen")

# Esquema mínimo esperado por tipo (campos obligatorios del dato entrante, RF-102).
# La validación profunda (GE, CU-O04) es aguas abajo; aquí solo el contrato mínimo.
ESQUEMA_MINIMO: dict[str, tuple[str, ...]] = {
    "reseñas":      ("title", "points", "taster_name", "winery"),
    "precios":      ("title", "price", "moneda", "fecha_precio"),
    "puntuaciones": ("title", "points", "taster_name", "fecha_cata"),
}

# Clave natural por tipo para la deduplicación en staging (RN-203). El id de la
# fuente se añade implícitamente (una fuente por partición). Las fuentes pueden
# sobrescribir la clave vía el campo `clave_natural` del catálogo.
#   Spec RN-203:
#     Fact_Resena       (fuente, catador, vino, fecha_resena)
#     Fact_Precio_Mercado (fuente, vino, mercado, fecha_precio)
#     Fact_Puntuacion   (fuente, catador, vino, fecha_cata)
#   El dataset winemag (reseñas) no trae `fecha_resena`; `title` porta la identidad
#   del vino (bodega+añada+designación), por lo que la clave práctica de reseñas es
#   (taster_name, title, winery).
CLAVE_NATURAL_DEFAULT: dict[str, tuple[str, ...]] = {
    "reseñas":      ("taster_name", "title", "winery"),
    "precios":      ("title", "mercado", "fecha_precio"),
    "puntuaciones": ("taster_name", "title", "fecha_cata"),
}


# ── Errores de negocio ────────────────────────────────────────────────────────
class CatalogoError(Exception):
    """Violación de una regla del catálogo de fuentes (mapea a 4xx en una API)."""

    def __init__(self, codigo: str, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


class FuenteInvalida(CatalogoError): ...      # RF-102 (metadatos)
class FuenteDuplicada(CatalogoError): ...     # RF-104 / RN-202
class FuenteInexistente(CatalogoError): ...
class ConectividadInvalida(CatalogoError): ...  # RF-102 (conexión) → RECHAZADA


# ── Esquema PocketBase (idempotente) ──────────────────────────────────────────
def _txt(name: str, required: bool = False) -> dict:
    return {"name": name, "type": "text", "required": required, "options": {}}


_SCHEMA: list[dict] = [
    _txt("nombre", required=True),
    _txt("tipo", required=True),            # reseñas | precios | puntuaciones
    _txt("formato", required=True),         # json | parquet | api | csv-origen
    _txt("endpoint", required=True),        # url / origen / nombre de colección PB
    _txt("coleccion"),                      # colección PB a leer (fuentes PB-backed)
    _txt("frecuencia"),                     # cron (ej. "0 6 * * *")
    _txt("mercado"),                        # → Dim_Mercado
    _txt("catador"),                        # → Dim_Catador_Sumiller
    _txt("clave_natural"),                  # CSV de columnas (override de dedup)
    _txt("estado"),                         # REGISTRADA|HABILITADA|DESHABILITADA|RECHAZADA
    _txt("motivo_rechazo"),
    _txt("ultima_ingesta"),                 # ISO ts de la última ingesta COMPLETADA/PARCIAL
    _txt("ultimo_estado_ingesta"),          # COMPLETADA | PARCIAL | FALLIDA
]


def ensure_schema(client: PBClient | None = None) -> bool:
    """Crea la colección `fuentes_externas` si falta. Devuelve True si la creó."""
    client = client or get_client()
    return client.ensure_collection(COLECCION, _SCHEMA)


# ── Helpers de dominio ────────────────────────────────────────────────────────
def esquema_minimo_de(tipo: str) -> tuple[str, ...]:
    return ESQUEMA_MINIMO.get(tipo, ())


def clave_natural_de(fuente: dict) -> list[str]:
    """Columnas de la clave natural de una fuente (override o default por tipo)."""
    override = str(fuente.get("clave_natural", "")).strip()
    if override:
        return [c.strip() for c in override.split(",") if c.strip()]
    return list(CLAVE_NATURAL_DEFAULT.get(fuente.get("tipo", ""), ()))


def validar_metadatos(datos: dict) -> list[str]:
    """RF-101/RF-102: valida los metadatos de alta. Devuelve lista de errores."""
    errores: list[str] = []
    if not str(datos.get("nombre", "")).strip():
        errores.append("nombre: obligatorio")

    tipo = str(datos.get("tipo", "")).strip()
    if tipo not in TIPOS_VALIDOS:
        errores.append(f"tipo: debe ser uno de {TIPOS_VALIDOS}")

    formato = str(datos.get("formato", "")).strip()
    if formato not in FORMATOS_VALIDOS:
        errores.append(f"formato: debe ser uno de {FORMATOS_VALIDOS}")

    if not str(datos.get("endpoint", "")).strip():
        errores.append("endpoint: obligatorio")

    frecuencia = str(datos.get("frecuencia", "")).strip()
    # Cron mínimo de 5 campos (no validamos la sintaxis completa, solo la forma).
    if not frecuencia or len(frecuencia.split()) < 5:
        errores.append("frecuencia: se espera una expresión cron de 5 campos")

    # Debe existir un esquema mínimo conocido para el tipo (RF-102).
    if tipo in TIPOS_VALIDOS and not ESQUEMA_MINIMO.get(tipo):
        errores.append(f"tipo '{tipo}': sin esquema mínimo declarado")

    return errores


def _validar_conectividad(fuente: dict, client: PBClient) -> tuple[bool, str]:
    """RF-102: comprueba conectividad/origen antes de habilitar.

    Para fuentes respaldadas por PocketBase verifica que la colección exista.
    Para otros formatos no se puede comprobar offline → se asume alcanzable
    (la ingesta reintentará y, al agotar reintentos, marcará FALLIDA — Esc-107).
    """
    coleccion = str(fuente.get("coleccion", "")).strip()
    if coleccion:
        try:
            if not client.collection_exists(coleccion):
                return False, f"colección de origen '{coleccion}' inexistente en PocketBase"
        except PBError as exc:
            return False, f"PocketBase inaccesible: {exc}"
    return True, ""


# ── RF-104 / RN-202 · Dedup por (tipo + endpoint + formato) ───────────────────
def buscar_fuente(tipo: str, endpoint: str, formato: str,
                  client: PBClient | None = None) -> dict | None:
    client = client or get_client()
    return client.find_one(COLECCION, tipo=tipo, endpoint=endpoint, formato=formato)


def obtener_fuente(fuente_id: str, client: PBClient | None = None) -> dict:
    client = client or get_client()
    fuente = client.find_one(COLECCION, id=fuente_id)
    if fuente is None:
        raise FuenteInexistente("fuente_inexistente",
                                f"No existe la fuente {fuente_id}.")
    return fuente


# ── RF-101..RF-104 · Registro de fuente ───────────────────────────────────────
def registrar_fuente(datos: dict, client: PBClient | None = None) -> dict:
    """Registra una fuente externa. Valida metadatos y deduplica.

    - Metadatos inválidos → `FuenteInvalida` (no se persiste basura).
    - Alta duplicada (tipo+endpoint+formato) → `FuenteDuplicada` con el id existente.
    - Caso nominal → registro en estado REGISTRADA.
    """
    client = client or get_client()
    ensure_schema(client)

    errores = validar_metadatos(datos)
    if errores:
        raise FuenteInvalida("metadatos_invalidos",
                             "Los metadatos de la fuente no son válidos.",
                             {"errores": errores})

    tipo = str(datos["tipo"]).strip()
    endpoint = str(datos["endpoint"]).strip()
    formato = str(datos["formato"]).strip()

    # RN-202: rechazar duplicado devolviendo el id existente.
    existente = buscar_fuente(tipo, endpoint, formato, client)
    if existente:
        raise FuenteDuplicada(
            "fuente_duplicada",
            f"Ya existe una fuente {tipo}/{formato} para endpoint '{endpoint}'.",
            {"id_existente": existente["id"]})

    return client.create(COLECCION, {
        "nombre": str(datos["nombre"]).strip(),
        "tipo": tipo,
        "formato": formato,
        "endpoint": endpoint,
        "coleccion": str(datos.get("coleccion", "")).strip(),
        "frecuencia": str(datos.get("frecuencia", "")).strip(),
        "mercado": str(datos.get("mercado", "")).strip(),
        "catador": str(datos.get("catador", "")).strip(),
        "clave_natural": ",".join(datos["clave_natural"])
        if isinstance(datos.get("clave_natural"), (list, tuple))
        else str(datos.get("clave_natural", "")).strip(),
        "estado": REGISTRADA,
        "motivo_rechazo": "",
        "ultima_ingesta": "",
        "ultimo_estado_ingesta": "",
    })


# ── RF-102/RF-105 · Ciclo de vida ─────────────────────────────────────────────
def habilitar_fuente(fuente_id: str, client: PBClient | None = None) -> dict:
    """RF-105: habilita una fuente. Revalida metadatos y conectividad ANTES
    de habilitar (RF-102). Si la conexión falla, la marca RECHAZADA y aborta."""
    client = client or get_client()
    fuente = obtener_fuente(fuente_id, client)

    errores = validar_metadatos(fuente)
    if errores:
        raise FuenteInvalida("metadatos_invalidos",
                             "No se puede habilitar: metadatos inválidos.",
                             {"errores": errores})

    ok, motivo = _validar_conectividad(fuente, client)
    if not ok:
        client.update(COLECCION, fuente_id,
                      {"estado": RECHAZADA, "motivo_rechazo": motivo})
        raise ConectividadInvalida("conectividad_invalida",
                                   f"No se puede habilitar la fuente: {motivo}.",
                                   {"motivo": motivo})

    return client.update(COLECCION, fuente_id,
                         {"estado": HABILITADA, "motivo_rechazo": ""})


def deshabilitar_fuente(fuente_id: str, client: PBClient | None = None) -> dict:
    """RF-105: pausa/da de baja una fuente sin borrar su historial."""
    client = client or get_client()
    obtener_fuente(fuente_id, client)  # valida existencia
    return client.update(COLECCION, fuente_id, {"estado": DESHABILITADA})


def fuentes_habilitadas(client: PBClient | None = None) -> list[dict]:
    """Fuentes elegibles para ingesta (RN-201)."""
    client = client or get_client()
    return client.find(COLECCION, per_page=200, estado=HABILITADA)


def marcar_ingesta(fuente_id: str, estado_ingesta: str,
                   ts: str | None = None, client: PBClient | None = None) -> dict:
    """Actualiza `ultima_ingesta`/`ultimo_estado_ingesta` tras un lote (RF-110)."""
    client = client or get_client()
    cambios = {"ultimo_estado_ingesta": estado_ingesta}
    if estado_ingesta in ("COMPLETADA", "PARCIAL"):
        cambios["ultima_ingesta"] = ts or datetime.now().isoformat(timespec="seconds")
    return client.update(COLECCION, fuente_id, cambios)


# ── Bootstrap de la fuente por defecto (reseñas winemag en PocketBase) ────────
def ensure_fuente_wine_reviews(coleccion: str, client: PBClient | None = None) -> dict:
    """Garantiza que la colección PocketBase de reseñas esté registrada y
    HABILITADA en el catálogo, para que la ingesta existente cumpla RN-201
    sin intervención manual. Idempotente."""
    client = client or get_client()
    ensure_schema(client)

    existente = buscar_fuente("reseñas", coleccion, "json", client)
    if existente is None:
        existente = registrar_fuente({
            "nombre": "Reseñas winemag (PocketBase)",
            "tipo": "reseñas",
            "formato": "json",
            "endpoint": coleccion,
            "coleccion": coleccion,
            "frecuencia": "0 6 * * *",
            "mercado": "Global",
            "catador": "Varios sumilleres winemag",
        }, client)

    if existente.get("estado") != HABILITADA:
        existente = habilitar_fuente(existente["id"], client)
    return existente


if __name__ == "__main__":
    import json

    from config import POCKETBASE_COLLECTION

    cli = get_client()
    if not cli.health():
        raise SystemExit("PocketBase no está accesible; no se puede inicializar el catálogo.")
    creada = ensure_schema(cli)
    fuente = ensure_fuente_wine_reviews(POCKETBASE_COLLECTION, cli)
    print(json.dumps({
        "coleccion_creada": creada,
        "fuente_wine_reviews": {"id": fuente["id"], "estado": fuente["estado"]},
        "habilitadas": [f["nombre"] for f in fuentes_habilitadas(cli)],
    }, ensure_ascii=False, indent=2))
