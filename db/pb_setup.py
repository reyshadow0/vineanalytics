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
    # ── OP3 · dashboards (CU-O05 / CU-O06) ────────────────────────────────────
    # Sello del gate de calidad CU-O04 (RN-401). El sello vigente habilita publicar.
    "sellos_calidad": [
        _TEXT("suite", required=True),        # stage | dw | pipeline
        _BOOL("exito"),
        _NUM("evaluadas"),
        _NUM("fallidas"),
        _TEXT("detalle"),                     # JSON serializado de fallos
        _NUM("vigencia_horas"),               # ventana de validez (def. 24 h)
        _DATE("fecha"),
    ],
    # Definición de dashboards por cliente/tema (RF-301..304).
    "dashboards": [
        _TEXT("nombre", required=True),
        _TEXT("cliente", required=True),      # id en `clientes` (multi-tenant, RN-403)
        _TEXT("tema", required=True),         # ingresos | resenas | precios | uso
        _NUM("version", required=True),       # RF-303 versionado
        _TEXT("estado", required=True),       # BORRADOR..PUBLICADO / BLOQUEADO_SIN_CALIDAD
        _TEXT("fuente_lectura"),              # clickhouse | starrocks (trazabilidad RT-01)
        _TEXT("definicion"),                  # JSON: métricas + filtros + definiciones
        _TEXT("usuario"),
        _DATE("creado"),
        _DATE("actualizado"),
    ],
    # Registro de publicaciones (RF-307 / RN-405): cuenta, permisos, versión, fecha.
    "publicaciones": [
        _TEXT("dashboard", required=True),    # id en `dashboards`
        _TEXT("cuenta", required=True),       # id en `clientes` (cuenta destino)
        _TEXT("plan"),                        # Dim_Plan vigente al publicar (RN-402)
        _TEXT("permisos"),                    # JSON de roles/permisos
        _NUM("version", required=True),
        _BOOL("calidad_ok"),                  # RN-401: solo true si hubo sello vigente
        _TEXT("sello"),                       # id del sello de calidad usado
        _TEXT("estado"),                      # ACTIVA | DESPUBLICADA | REEMPLAZADA
        _TEXT("usuario"),
        _DATE("publicado_en"),
        _DATE("baja_en"),
    ],
    # ── OP11 · reportes-operativos (CU-O16) ───────────────────────────────────
    # Registro/archivo operacional del reporte diario (auditoría RN-1205). Las
    # CIFRAS viven en ClickHouse; aquí solo el metadato + documento serializado.
    "reportes_operativos": [
        _TEXT("fecha", required=True),        # clave de upsert (un reporte por día)
        _TEXT("periodo"),                     # período Dim_Tiempo consolidado
        _TEXT("estado", required=True),       # PUBLICADO | BLOQUEADO_SIN_CALIDAD | FALLIDO
        _BOOL("calidad_ok"),                  # RF-1104: gate de calidad del día
        _TEXT("sello"),                       # id del sello de calidad CU-O04 usado
        _TEXT("documento"),                   # JSON del reporte (cifras + trazabilidad)
        _DATE("generado_en"),
    ],
    # ── OP7 · observabilidad (CU-O11) ─────────────────────────────────────────
    # Historial de incidentes con duración y región para el SLA mensual (RF-706).
    # Las MEDICIONES (uptime/latencia) van a Fact_Disponibilidad en StarRocks; aquí
    # solo el registro operacional del incidente.
    "incidentes": [
        _TEXT("clave", required=True),        # dedup determinista (servicio+periodo+region)
        _TEXT("servicio", required=True),     # starrocks | clickhouse | pocketbase | ...
        _TEXT("region"),                      # país/región (Dim_Mercado)
        _NUM("id_mercado"),                   # → Dim_Mercado.id_mercado
        _NUM("id_tiempo"),                    # período Dim_Tiempo
        _TEXT("severidad"),                   # warning | critical
        _TEXT("causa"),                       # caída de uptime | latencia elevada | servicio caído
        _TEXT("estado"),                      # ABIERTO | RECUPERADO
        _NUM("uptime"),                       # % medido en la ventana
        _NUM("latencia_ms"),                  # latencia promedio medida
        _NUM("duracion_min"),                 # duración estimada del incidente (RF-706)
        _DATE("inicio"),
        _DATE("fin"),
    ],
    # ── OP8 · machine-learning (CU-O12) ───────────────────────────────────────
    # Registro de predicciones con su versión de modelo, features y score (RF-805,
    # RN-902). Idempotente por (corrida, id_entidad). Las predicciones se sirven a
    # dashboards SOLO vía ClickHouse (RN-905); aquí es la traza operacional.
    "predicciones_ml": [
        _TEXT("corrida", required=True),      # id determinista: modelo-version-id_tiempo
        _TEXT("modelo", required=True),       # churn | precio
        _TEXT("version_modelo", required=True),
        _TEXT("entidad"),                     # cliente | variedad
        _TEXT("id_entidad"),                  # clave natural de la entidad
        _TEXT("nombre"),                      # etiqueta legible
        _NUM("score"),                        # probabilidad / ajuste recomendado
        _TEXT("nivel"),                       # Alto | Medio | Bajo (churn)
        _NUM("umbral"),                       # umbral de disparo de alerta
        _BOOL("supera_umbral"),               # score por encima del umbral
        _TEXT("features"),                    # JSON de features usadas (explicabilidad)
        _TEXT("periodo"),
        _NUM("id_tiempo"),
        _DATE("fecha"),
    ],
    # ── OP9 · alertas (CU-O13) ────────────────────────────────────────────────
    # Bus de señales: cada paquete emisor (ML, observabilidad, ingesta, API,
    # conversión) deja aquí una señal normalizada; `alertas` la consume (RF-902).
    "senales_alerta": [
        _TEXT("origen", required=True),       # machine-learning | observabilidad | ingesta | api | conversion
        _TEXT("tipo", required=True),         # churn | precio | uptime | latencia | ingesta | api | conversion
        _TEXT("severidad"),                   # info | warning | critical (sugerida)
        _TEXT("causa"),
        _TEXT("entidad"),                     # entidad afectada (cliente/variedad/servicio)
        _TEXT("clave", required=True),        # dedup_key de la condición sostenida
        _NUM("valor"),                        # valor observado
        _NUM("umbral"),                       # umbral cruzado
        _NUM("id_tiempo"),
        _TEXT("payload"),                     # JSON con contexto adicional
        _BOOL("procesada"),                   # la consumió `alertas`
        _DATE("fecha"),
    ],
    # Registro/auditoría de cada alerta generada con su ciclo de vida (RF-904/907).
    "alertas": [
        _TEXT("tipo", required=True),         # churn | precio | uptime | latencia | ingesta | api | conversion
        _TEXT("severidad", required=True),    # info | warning | critical (RF-903)
        _TEXT("causa", required=True),
        _TEXT("origen"),                      # paquete emisor
        _TEXT("responsable"),                 # Customer Success | DevOps | Ingeniería de datos (RF-905)
        _TEXT("entidad"),
        _TEXT("clave", required=True),        # dedup_key (RF-906 / RN-1004)
        _TEXT("estado", required=True),       # ABIERTA | RECONOCIDA | RESUELTA | SILENCIADA (RF-907)
        _NUM("ocurrencias"),                  # nº de señales agrupadas (anti-tormenta)
        _NUM("valor"),
        _NUM("umbral"),
        _NUM("id_tiempo"),
        _TEXT("payload"),                     # JSON con contexto/trazabilidad (RNF-905)
        _DATE("primera_vez"),
        _DATE("ultima_vez"),
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
