"""
models_dashboards.py — Lógica de negocio de CU-O05 «Construir dashboard de cliente»
y CU-O06 «Publicar dashboard a la cuenta del cliente» (OP3 · paquete `dashboards`).

Capas (constitución · RN-404 / RT-01):
  - Los DATOS ANALÍTICOS del dashboard se leen SOLO de ClickHouse, vía `serving.py`,
    con fallback a StarRocks resuelto en `app.py`. Aquí NO se consulta el DW directo:
    la lectura llega por la callable `lectura_fn(tema, filtros)`.
  - Los METADATOS (dashboards, publicaciones, sellos de calidad) son operacionales y
    viven en PocketBase, reutilizando el patrón de la Sesión 1 (pb_client/pb_setup).

Reglas de negocio implementadas:
  - RN-401  No se publica un dashboard sin validación de calidad vigente (CU-O04).
            (Regla dura · Princ. X) → `calidad_vigente()` + estado BLOQUEADO_SIN_CALIDAD.
  - RN-402  Solo se publica a cuentas con plan vigente (Dim_Plan) → `acceso_vigente`.
  - RN-403  Aislamiento multi-tenant: un dashboard solo se publica a su propia cuenta;
            un filtro Dim_Cliente no puede apuntar a otra cuenta.
  - RN-405  Toda publicación queda registrada y versionada (auditable).
  - RF-303  Versionado borrador → publicable. RF-308 despublicar/reemplazar con historial.
"""

from __future__ import annotations

import json
from datetime import datetime

from pb_client import PBClient, get_client
from models_clientes import acceso_vigente

# ── Estados del dashboard (spec §9) ───────────────────────────────────────────
BORRADOR              = "BORRADOR"
EN_REVISION           = "EN_REVISION"
LISTO_PARA_PUBLICAR   = "LISTO_PARA_PUBLICAR"
PUBLICADO             = "PUBLICADO"
DESPUBLICADO          = "DESPUBLICADO"
REEMPLAZADO           = "REEMPLAZADO"
BLOQUEADO_SIN_CALIDAD = "BLOQUEADO_SIN_CALIDAD"

# ── Estados de una publicación ────────────────────────────────────────────────
PUB_ACTIVA   = "ACTIVA"
PUB_BAJA     = "DESPUBLICADA"
PUB_REEMPLAZADA = "REEMPLAZADA"


# ── Catálogo de temas (RF-304: Fact por tema) y sus métricas/definiciones ──────
# Las `clave`s coinciden con las que devuelve serving.metricas_dashboard().
TEMAS: dict[str, dict] = {
    "ingresos": {
        "titulo": "Ingresos y suscripciones",
        "fact": "Fact_Suscripcion",
        "metricas": [
            {"clave": "mrr_actual", "etiqueta": "MRR", "unidad": "$",
             "definicion": "Ingreso recurrente mensual de las suscripciones activas."},
            {"clave": "churn", "etiqueta": "Churn", "unidad": "%",
             "definicion": "Porcentaje de cancelaciones mensuales sobre clientes activos."},
            {"clave": "clientes_activos", "etiqueta": "Clientes activos", "unidad": "",
             "definicion": "Cuentas con suscripción vigente."},
        ],
    },
    "resenas": {
        "titulo": "Reseñas y puntuaciones",
        "fact": "Fact_Resena",
        "metricas": [
            {"clave": "total_resenas", "etiqueta": "Reseñas", "unidad": "",
             "definicion": "Total de reseñas en el periodo/mercado seleccionado."},
            {"clave": "puntuacion_promedio", "etiqueta": "Puntuación media", "unidad": "pts",
             "definicion": "Promedio de puntos en la escala 80-100."},
        ],
    },
    "precios": {
        "titulo": "Precios de mercado",
        "fact": "Fact_Precio_Mercado",
        "metricas": [
            {"clave": "precio_promedio", "etiqueta": "Precio medio", "unidad": "$",
             "definicion": "Precio promedio (USD) de los vinos del mercado."},
            {"clave": "precio_maximo", "etiqueta": "Precio máx.", "unidad": "$",
             "definicion": "Precio más alto observado."},
            {"clave": "precio_minimo", "etiqueta": "Precio mín.", "unidad": "$",
             "definicion": "Precio más bajo observado."},
        ],
    },
    "uso": {
        "titulo": "Uso y adopción",
        "fact": "Fact_Uso_Plataforma",
        "metricas": [
            {"clave": "adopcion", "etiqueta": "Adopción", "unidad": "%",
             "definicion": "Porcentaje de usuarios activos sobre el total de la cuenta."},
            {"clave": "nps", "etiqueta": "NPS", "unidad": "",
             "definicion": "Net Promoter Score de la cuenta."},
        ],
    },
}

# Filtros soportados (RF-302). Se documentan en la definición del dashboard.
DIM_FILTROS = ("tiempo", "mercado", "cliente", "plan")


# ── Errores de negocio (mapean a 4xx en la API, como models_clientes) ─────────
class DashboardError(Exception):
    def __init__(self, codigo: str, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


class TemaInvalido(DashboardError): ...          # RF-304
class DashboardInexistente(DashboardError): ...
class EstadoInvalido(DashboardError): ...        # RF-303
class CalidadNoVigente(DashboardError): ...      # RN-401 (regla dura)
class PlanNoVigente(DashboardError): ...         # RN-402
class FugaMultiTenant(DashboardError): ...       # RN-403


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cli(client: PBClient | None) -> PBClient:
    return client or get_client()


def _now() -> str:
    return datetime.now().isoformat()


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _load(value):
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {}
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {}


def _truthy(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes", "si", "sí")
    return bool(value)


def _parse_dt(value):
    """Parsea fechas propias (ISO) y de PocketBase ('YYYY-MM-DD HH:MM:SS.sssZ')."""
    if not value:
        return None
    raw = str(value).strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", ""))
    except ValueError:
        pass
    norm = raw.replace("Z", "").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(norm[:26], fmt)
        except ValueError:
            continue
    return None


def _get_dashboard(client: PBClient, dashboard_id: str) -> dict:
    dash = client.find_one("dashboards", id=dashboard_id)
    if dash is None:
        raise DashboardInexistente("dashboard_inexistente",
                                   f"No existe el dashboard {dashboard_id}.")
    return dash


def _publicacion_activa(client: PBClient, dashboard_id: str, cuenta_id: str):
    for p in client.find("publicaciones", dashboard=dashboard_id, cuenta=cuenta_id):
        if p.get("estado") == PUB_ACTIVA:
            return p
    return None


# ── Catálogo expuesto a la API ────────────────────────────────────────────────
def temas() -> dict:
    return {
        t: {"titulo": v["titulo"], "fact": v["fact"], "metricas": v["metricas"]}
        for t, v in TEMAS.items()
    }


# ══════════════════════════════════════════════════════════════════════════════
# CU-O05 · Construir dashboard de cliente
# ══════════════════════════════════════════════════════════════════════════════

def _lectura_solo_clickhouse(tema: str, filtros: dict):
    """Lectura por defecto: SOLO ClickHouse (sin fallback). app.py inyecta una
    `lectura_fn` que añade el fallback a StarRocks (RT-01/RT-02)."""
    import serving
    return serving.metricas_dashboard(tema, filtros)


def construir_dashboard(cliente_id: str, tema: str, nombre: str | None = None,
                        filtros: dict | None = None, lectura_fn=None,
                        usuario: str = "analista",
                        client: PBClient | None = None) -> dict:
    """RF-301/302/303/304: compone un dashboard por cliente y tema, con métricas,
    definiciones y filtros, leyendo de ClickHouse (vía `lectura_fn`). Lo deja en
    estado BORRADOR (Esc-301)."""
    client = _cli(client)
    tema = (tema or "").lower()
    if tema not in TEMAS:
        raise TemaInvalido("tema_invalido", f"Tema '{tema}' no soportado.",
                           {"temas": sorted(TEMAS)})

    cliente = client.find_one("clientes", id=cliente_id)
    if cliente is None:
        raise DashboardError("cliente_inexistente",
                             f"No existe la cuenta {cliente_id}.")

    filtros = dict(filtros or {})
    # RN-403: el filtro Dim_Cliente se fuerza a la cuenta dueña; otro valor es fuga.
    if filtros.get("cliente") and str(filtros["cliente"]) != str(cliente_id):
        raise FugaMultiTenant(
            "fuga_multitenant",
            "Un filtro Dim_Cliente no puede apuntar a otra cuenta.",
            {"cliente_dashboard": cliente_id, "filtro_cliente": filtros.get("cliente")})
    filtros["cliente"] = cliente_id

    nombre = nombre or f"{TEMAS[tema]['titulo']} — {cliente.get('razon_social', cliente_id)}"

    # Lectura de métricas desde ClickHouse (con fallback resuelto por lectura_fn).
    lectura_fn = lectura_fn or _lectura_solo_clickhouse
    datos = lectura_fn(tema, filtros) or {}
    valores = datos.get("valores", {})
    fuente = datos.get("fuente", "desconocida")

    metricas = [{**m, "valor": valores.get(m["clave"])} for m in TEMAS[tema]["metricas"]]
    definicion = {
        "tema": tema,
        "fact": TEMAS[tema]["fact"],
        "titulo": TEMAS[tema]["titulo"],
        "metricas": metricas,
        "filtros": filtros,
        "dim_filtros": list(DIM_FILTROS),
        "fuente_lectura": fuente,
    }

    # Upsert de un BORRADOR por (cliente, tema, nombre) — versión persistente.
    existente = client.find_one("dashboards", cliente=cliente_id, tema=tema, nombre=nombre)
    if existente:
        rec = client.update("dashboards", existente["id"], {
            "estado": BORRADOR,
            "fuente_lectura": fuente,
            "definicion": _dump(definicion),
            "usuario": usuario,
            "actualizado": _now(),
        })
    else:
        rec = client.create("dashboards", {
            "nombre": nombre, "cliente": cliente_id, "tema": tema, "version": 1,
            "estado": BORRADOR, "fuente_lectura": fuente,
            "definicion": _dump(definicion), "usuario": usuario,
            "creado": _now(), "actualizado": _now(),
        })
    rec["definicion"] = definicion
    return rec


def marcar_listo(dashboard_id: str, usuario: str = "analista",
                 client: PBClient | None = None) -> dict:
    """RF-303: promueve BORRADOR/EN_REVISION → LISTO_PARA_PUBLICAR."""
    client = _cli(client)
    dash = _get_dashboard(client, dashboard_id)
    if dash.get("estado") not in (BORRADOR, EN_REVISION, BLOQUEADO_SIN_CALIDAD):
        raise EstadoInvalido("estado_invalido",
                             f"No se puede marcar LISTO desde {dash.get('estado')}.",
                             {"estado": dash.get("estado")})
    return client.update("dashboards", dashboard_id,
                         {"estado": LISTO_PARA_PUBLICAR, "actualizado": _now()})


# ══════════════════════════════════════════════════════════════════════════════
# Sello de calidad (puente con CU-O04) — gate de RN-401
# ══════════════════════════════════════════════════════════════════════════════

def registrar_sello(suite: str, exito: bool, evaluadas: int = 0, fallidas: int = 0,
                    detalle: dict | None = None, vigencia_horas: float = 24,
                    fecha: str | None = None, client: PBClient | None = None) -> dict:
    """Persiste el resultado del gate de calidad (CU-O04) como 'sello' operacional.
    Lo invoca `quality/run_quality.py` tras cada corrida (best-effort)."""
    client = _cli(client)
    return client.create("sellos_calidad", {
        "suite": suite,
        "exito": bool(exito),
        "evaluadas": int(evaluadas),
        "fallidas": int(fallidas),
        "detalle": _dump(detalle or {}),
        "vigencia_horas": float(vigencia_horas),
        "fecha": fecha or _now(),
    })


def calidad_vigente(client: PBClient | None = None, ventana_horas: float = 24) -> dict:
    """RN-401/RF-305: ¿hay validación de calidad vigente? Devuelve
    {ok, motivo, sello}. Considera el sello MÁS RECIENTE: si la última corrida
    falló o el sello venció, NO es vigente (no se publica)."""
    client = _cli(client)
    sellos = client.find("sellos_calidad")
    if not sellos:
        return {"ok": False, "sello": None,
                "motivo": "No existe un sello de calidad (CU-O04); valide la calidad "
                          "antes de publicar."}
    sellos.sort(key=lambda s: _parse_dt(s.get("fecha")) or datetime.min, reverse=True)
    sello = sellos[0]
    if not _truthy(sello.get("exito")):
        return {"ok": False, "sello": sello,
                "motivo": "La última validación de calidad (CU-O04) FALLÓ; corrija los "
                          "datos antes de publicar."}
    fecha = _parse_dt(sello.get("fecha"))
    if fecha is None:
        return {"ok": False, "sello": sello,
                "motivo": "El sello de calidad no tiene fecha válida."}
    vigencia = float(sello.get("vigencia_horas") or ventana_horas)
    edad_h = (datetime.now() - fecha).total_seconds() / 3600.0
    if edad_h > vigencia:
        return {"ok": False, "sello": sello,
                "motivo": f"El sello de calidad venció (hace {edad_h:.1f} h; "
                          f"vigencia {vigencia:.0f} h)."}
    return {"ok": True, "sello": sello, "motivo": "Sello de calidad vigente."}


# ══════════════════════════════════════════════════════════════════════════════
# CU-O06 · Publicar dashboard a la cuenta del cliente
# ══════════════════════════════════════════════════════════════════════════════

def publicar(dashboard_id: str, cuenta_id: str, permisos=None, usuario: str = "admin",
             ventana_horas: float = 24, client: PBClient | None = None) -> dict:
    """RF-305/306/307: publica un dashboard a una cuenta con permisos y versión.

    Orden de verificación:
      1. Existencia y estado del dashboard (LISTO_PARA_PUBLICAR).
      2. RN-403 aislamiento multi-tenant (solo a la cuenta dueña).
      3. RN-401 gate de calidad (regla dura) → BLOQUEADO_SIN_CALIDAD si no vigente.
      4. RN-402 plan vigente de la cuenta.
      5. Registro de la publicación + versionado/reemplazo (RF-307/308).
    """
    client = _cli(client)
    permisos = permisos or ["lectura"]
    dash = _get_dashboard(client, dashboard_id)

    estado = dash.get("estado")
    if estado not in (LISTO_PARA_PUBLICAR, PUBLICADO, BLOQUEADO_SIN_CALIDAD):
        raise EstadoInvalido(
            "estado_invalido",
            f"El dashboard debe estar LISTO_PARA_PUBLICAR (actual: {estado}).",
            {"estado": estado})

    # RN-403: nunca a una cuenta distinta de la dueña del dashboard.
    if str(dash.get("cliente")) != str(cuenta_id):
        raise FugaMultiTenant(
            "fuga_multitenant",
            "El dashboard pertenece a otra cuenta; publicarlo a una cuenta distinta "
            "violaría el aislamiento multi-tenant.",
            {"cliente_dashboard": dash.get("cliente"), "cuenta_destino": cuenta_id})

    # RN-401 (regla dura · Princ. X): sin calidad vigente NO se publica.
    cal = calidad_vigente(client, ventana_horas)
    if not cal["ok"]:
        client.update("dashboards", dashboard_id,
                      {"estado": BLOQUEADO_SIN_CALIDAD, "actualizado": _now()})
        raise CalidadNoVigente(
            "calidad_no_vigente", cal["motivo"],
            {"estado": BLOQUEADO_SIN_CALIDAD,
             "sello": (cal.get("sello") or {}).get("id")})

    # RN-402: la cuenta debe tener plan vigente (Dim_Plan).
    acceso = acceso_vigente(cuenta_id, client=client)
    if not acceso.get("autorizado"):
        raise PlanNoVigente(
            "plan_no_vigente",
            "La cuenta no tiene un plan vigente; no se puede publicar.",
            {"acceso": acceso})

    # RF-308: si ya hay una publicación ACTIVA a esta cuenta, se reemplaza y versiona.
    version = int(dash.get("version", 1))
    activa = _publicacion_activa(client, dashboard_id, cuenta_id)
    if activa:
        version = int(activa.get("version", version)) + 1
        client.update("publicaciones", activa["id"],
                      {"estado": PUB_REEMPLAZADA, "baja_en": _now()})
        client.update("dashboards", dashboard_id, {"version": version})

    pub = client.create("publicaciones", {
        "dashboard": dashboard_id,
        "cuenta": cuenta_id,
        "plan": acceso.get("plan") or "",
        "permisos": _dump(permisos),
        "version": version,
        "calidad_ok": True,
        "sello": (cal.get("sello") or {}).get("id", ""),
        "estado": PUB_ACTIVA,
        "usuario": usuario,
        "publicado_en": _now(),
        "baja_en": "",
    })
    client.update("dashboards", dashboard_id,
                  {"estado": PUBLICADO, "actualizado": _now()})
    pub["permisos"] = permisos
    return pub


def despublicar(publicacion_id: str, usuario: str = "admin",
                client: PBClient | None = None) -> dict:
    """RF-308: da de baja una publicación, conservando el historial."""
    client = _cli(client)
    pub = client.find_one("publicaciones", id=publicacion_id)
    if pub is None:
        raise DashboardError("publicacion_inexistente",
                             f"No existe la publicación {publicacion_id}.")
    actualizada = client.update("publicaciones", publicacion_id,
                                {"estado": PUB_BAJA, "baja_en": _now()})
    # Si el dashboard ya no tiene publicaciones activas, queda DESPUBLICADO.
    activas = [p for p in client.find("publicaciones", dashboard=pub["dashboard"])
               if p.get("estado") == PUB_ACTIVA]
    if not activas:
        client.update("dashboards", pub["dashboard"],
                      {"estado": DESPUBLICADO, "actualizado": _now()})
    return actualizada


def publicaciones_de(dashboard_id: str, client: PBClient | None = None) -> list[dict]:
    """RF-307/405: historial de publicaciones de un dashboard (auditable)."""
    client = _cli(client)
    pubs = client.find("publicaciones", dashboard=dashboard_id)
    for p in pubs:
        p["permisos"] = _load(p.get("permisos"))
    pubs.sort(key=lambda p: _parse_dt(p.get("publicado_en")) or datetime.min, reverse=True)
    return pubs
