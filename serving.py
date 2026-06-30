"""
serving.py — Capa de lectura del dashboard/API desde ClickHouse (OP3 · Fase 2).

Cada función devuelve la estructura JSON lista para el endpoint, leída de las
agregaciones ClickHouse (pobladas por clickhouse/populate.py), o **None** si:
  - ClickHouse está deshabilitado (CLICKHOUSE_ENABLED=0),
  - no se puede conectar / la librería no está instalada,
  - la tabla de agregación está vacía.

Al devolver None, app.py cae automáticamente a su consulta StarRocks existente
(fallback). Así migramos el serving a ClickHouse sin riesgo de dejar dashboards
en blanco. ClickHouse se alimenta SOLO de StarRocks (RT-02).
"""

from config import (
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_DB,
    CLICKHOUSE_USER, CLICKHOUSE_PASS, CLICKHOUSE_ENABLED,
)

_client = None


def _get_client():
    """Cliente ClickHouse perezoso y reutilizado; None si no está disponible."""
    global _client
    if not CLICKHOUSE_ENABLED:
        return None
    if _client is not None:
        return _client
    try:
        import clickhouse_connect
        _client = clickhouse_connect.get_client(
            host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
            username=CLICKHOUSE_USER, password=CLICKHOUSE_PASS,
            database=CLICKHOUSE_DB, connect_timeout=3, send_receive_timeout=10,
        )
        return _client
    except Exception:
        _client = None
        return None


def _q(sql: str):
    """Ejecuta una consulta y devuelve result_rows, o None ante cualquier fallo."""
    c = _get_client()
    if c is None:
        return None
    try:
        return c.query(sql).result_rows
    except Exception:
        # invalida el cliente para reintentar conexión en la próxima llamada
        global _client
        _client = None
        return None


def disponible() -> bool:
    return _get_client() is not None


# ── KPI helper (espejo de app._kpi; las metas/umbrales son la misma fuente) ────
def _kpi(clave, etiqueta, valor, meta, unidad, mejor, sub=""):
    valor = round(float(valor or 0), 2)
    if mejor == "mayor":
        estado = "verde" if valor >= meta else ("amarillo" if valor >= meta * 0.9 else "rojo")
    else:
        estado = "verde" if valor <= meta else ("amarillo" if valor <= meta * 1.1 else "rojo")
    return {"clave": clave, "etiqueta": etiqueta, "valor": valor, "meta": meta,
            "unidad": unidad, "mejor": mejor, "estado": estado, "sub": sub}


# ══════════════════════════════════════════════════════════════════════════════
# VINO
# ══════════════════════════════════════════════════════════════════════════════

def kpis():
    rows = _q("""SELECT total_resenas, puntuacion_promedio, precio_promedio,
                        precio_maximo, precio_minimo, total_paises,
                        total_variedades, total_bodegas
                 FROM agg_kpis_vino LIMIT 1""")
    if not rows:
        return None
    r = rows[0]
    if int(r[0] or 0) == 0:
        return None
    return {
        "total_resenas": int(r[0]), "puntuacion_promedio": float(r[1]),
        "precio_promedio": float(r[2]), "precio_maximo": float(r[3]),
        "precio_minimo": float(r[4]), "total_paises": int(r[5]),
        "total_variedades": int(r[6]), "total_bodegas": int(r[7]),
    }


def grafica_paises():
    rows = _q("""SELECT pais, puntuacion_promedio, total FROM agg_pais
                 ORDER BY puntuacion_promedio DESC LIMIT 15""")
    if not rows:
        return None
    return [{"pais": r[0], "puntuacion": float(r[1]), "total": int(r[2])} for r in rows]


def grafica_variedades():
    # total_con_precio = reseñas con price>0 (espeja el WHERE price>0 del endpoint).
    rows = _q("""SELECT variedad, precio_promedio, total_con_precio FROM agg_variedad
                 WHERE precio_promedio > 0 ORDER BY precio_promedio DESC LIMIT 12""")
    if not rows:
        return None
    return [{"variedad": r[0], "precio_promedio": float(r[1]), "total": int(r[2])} for r in rows]


def grafica_puntuacion():
    rows = _q("SELECT puntuacion, total FROM agg_puntuacion_hist ORDER BY puntuacion")
    if not rows:
        return None
    return [{"puntuacion": int(r[0]), "total": int(r[1])} for r in rows]


def grafica_bodegas():
    rows = _q("""SELECT bodega, puntuacion_promedio, total FROM agg_bodega
                 WHERE total >= 10 ORDER BY puntuacion_promedio DESC LIMIT 10""")
    if not rows:
        return None
    return [{"bodega": r[0], "puntuacion": float(r[1]), "total": int(r[2])} for r in rows]


def paises():
    rows = _q("SELECT pais, total FROM agg_pais ORDER BY total DESC")
    if not rows:
        return None
    return [{"nombre": r[0], "total": int(r[1])} for r in rows]


def variedades():
    rows = _q("SELECT variedad, total FROM agg_variedad ORDER BY total DESC LIMIT 60")
    if not rows:
        return None
    return [{"nombre": r[0], "total": int(r[1])} for r in rows]


def browse():
    pais = _q("SELECT pais, total FROM agg_pais ORDER BY total DESC LIMIT 6")
    var  = _q("SELECT variedad, total FROM agg_variedad ORDER BY total DESC LIMIT 6")
    bod  = _q("SELECT bodega, total FROM agg_bodega ORDER BY total DESC LIMIT 6")
    reg  = _q("SELECT region, total FROM agg_region ORDER BY total DESC LIMIT 6")
    if pais is None or var is None or bod is None or reg is None:
        return None
    if not (pais or var or bod or reg):   # ClickHouse vacío → fallback a StarRocks
        return None
    f = lambda rows: [{"nombre": r[0], "total": int(r[1])} for r in rows]
    return {"paises": f(pais), "variedades": f(var), "bodegas": f(bod), "regiones": f(reg)}


def comparar_mercados(nombres):
    """nombres: lista de hasta 4 países. Devuelve métricas por país (orden de entrada)."""
    if not nombres:
        return []
    safe = [n.replace("'", "''") for n in nombres]
    in_list = ",".join(f"'{n}'" for n in safe)
    rows = _q(f"""SELECT pais, total, puntuacion_promedio, precio_promedio, variedades
                  FROM agg_pais WHERE pais IN ({in_list})""")
    if rows is None:
        return None
    por_pais = {r[0]: r for r in rows}
    out = []
    for n in nombres:
        if n in por_pais:
            r = por_pais[n]
            out.append({"pais": n, "total": int(r[1]), "puntuacion": float(r[2]),
                        "precio": float(r[3]), "variedades": int(r[4])})
    return out


def v1_mercados():
    rows = _q("""SELECT pais, total, puntuacion_promedio, precio_promedio
                 FROM agg_pais ORDER BY total DESC LIMIT 50""")
    if not rows:
        return None
    return {"api_version": "1.0",
            "data": [{"mercado": r[0], "resenas": int(r[1]),
                      "puntuacion_promedio": float(r[2]),
                      "precio_promedio": float(r[3] or 0)} for r in rows]}


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARDS POR CLIENTE / TEMA (CU-O05) — lectura desde ClickHouse
# ══════════════════════════════════════════════════════════════════════════════

def metricas_dashboard(tema: str, filtros: dict | None = None):
    """Lee las métricas de un tema desde las agregaciones ClickHouse (RF-301/304).

    Devuelve ``{"fuente": "clickhouse", "valores": {clave: valor}}`` o **None** si
    ClickHouse no está disponible / la agregación está vacía. Al devolver None,
    app.py cae a StarRocks (fallback, RT-01/RT-02). Soporta el filtro Dim_Mercado
    (`filtros["mercado"]`) en los temas que lo permiten; los demás filtros (tiempo,
    cliente, plan) acotan/aíslan la vista y se registran en la definición.
    """
    filtros = filtros or {}
    tema = (tema or "").lower()
    mercado = filtros.get("mercado")

    if tema in ("resenas", "reseñas"):
        if mercado:
            safe = str(mercado).replace("'", "''")
            rows = _q(f"SELECT total, puntuacion_promedio FROM agg_pais "
                      f"WHERE pais = '{safe}' LIMIT 1")
            if not rows:
                return None
            r = rows[0]
            return {"fuente": "clickhouse", "valores": {
                "total_resenas": int(r[0] or 0), "puntuacion_promedio": float(r[1] or 0)}}
        rows = _q("SELECT total_resenas, puntuacion_promedio FROM agg_kpis_vino LIMIT 1")
        if not rows or int(rows[0][0] or 0) == 0:
            return None
        r = rows[0]
        return {"fuente": "clickhouse", "valores": {
            "total_resenas": int(r[0]), "puntuacion_promedio": float(r[1] or 0)}}

    if tema == "precios":
        if mercado:
            safe = str(mercado).replace("'", "''")
            rows = _q(f"SELECT precio_promedio FROM agg_pais WHERE pais = '{safe}' LIMIT 1")
            if not rows:
                return None
            return {"fuente": "clickhouse", "valores": {
                "precio_promedio": float(rows[0][0] or 0),
                "precio_maximo": None, "precio_minimo": None}}
        rows = _q("SELECT precio_promedio, precio_maximo, precio_minimo "
                  "FROM agg_kpis_vino LIMIT 1")
        if not rows:
            return None
        r = rows[0]
        return {"fuente": "clickhouse", "valores": {
            "precio_promedio": float(r[0] or 0), "precio_maximo": float(r[1] or 0),
            "precio_minimo": float(r[2] or 0)}}

    if tema == "ingresos":
        rows = _q("SELECT mrr_actual, churn, clientes_activos FROM agg_bsc_kpis LIMIT 1")
        if not rows:
            return None
        r = rows[0]
        return {"fuente": "clickhouse", "valores": {
            "mrr_actual": float(r[0] or 0), "churn": float(r[1] or 0),
            "clientes_activos": int(r[2] or 0)}}

    if tema == "uso":
        rows = _q("SELECT adopcion, nps FROM agg_bsc_kpis LIMIT 1")
        if not rows:
            return None
        r = rows[0]
        return {"fuente": "clickhouse", "valores": {
            "adopcion": float(r[0] or 0), "nps": float(r[1] or 0)}}

    return None


# ══════════════════════════════════════════════════════════════════════════════
# BALANCED SCORECARD
# ══════════════════════════════════════════════════════════════════════════════

def _bsc_kpi_row():
    rows = _q("""SELECT periodo, clientes_activos, mrr_actual, mrr_growth, api_share,
                        cac, ltv_cac, cloud_cli, conversion, churn, nps, adopcion,
                        nuevos_trim, uptime, ttm, latencia, calidad,
                        horas, ddd, mlmod, rotacion, tecno
                 FROM agg_bsc_kpis LIMIT 1""")
    return rows[0] if rows else None


def bsc_kpis_payload(r):
    """Construye el payload de tarjetas del BSC a partir de UNA fila de agg_bsc_kpis.
    Lo comparten serving.bsc_kpis() (lee ClickHouse) y el fallback de app.py (lee la
    vista DBT agg_bsc_kpis en StarRocks): las metas/umbrales viven en un solo lugar."""
    (periodo, activos, mrr_now, mrr_growth, api_share, cac_now, ltv_cac, cloud_cli,
     conv, churn, nps, adopcion, nuevos_trim, uptime, ttm, lat, calidad,
     horas, ddd, mlmod, rota, tecno) = r
    return {
        "disponible": True,
        "periodo": periodo,
        "clientes_activos": int(activos),
        "mrr_actual": round(float(mrr_now), 2),
        "perspectivas": {
            "financiera": [
                _kpi("mrr_growth", "Crecimiento de MRR", mrr_growth, 30, "%", "mayor", f"MRR ${float(mrr_now):,.0f}/mes"),
                _kpi("api_share",  "Ingresos vía API",   api_share,  35, "%", "mayor", "% de ingresos totales"),
                _kpi("cac",        "CAC internacional",  cac_now,  1200, "$", "menor", "objetivo −20 % i.a."),
                _kpi("ltv_cac",    "Ratio LTV / CAC",    ltv_cac,     3, "x", "mayor", "valor de vida / costo"),
                _kpi("cloud",      "Costo cloud / cliente", cloud_cli, 50, "$", "menor", "FinOps · −15 % anual"),
            ],
            "cliente": [
                _kpi("conversion", "Conversión del embudo", conv,    8, "%", "mayor", "clientes / leads"),
                _kpi("churn",      "Tasa de churn",         churn,   4, "%", "menor", "cancelaciones mensuales"),
                _kpi("nps",        "Net Promoter Score",    nps,    50, "",  "mayor", "satisfacción del cliente"),
                _kpi("adopcion",   "Adopción plataforma",   adopcion,70, "%", "mayor", "usuarios activos / totales"),
                _kpi("nuevos",     "Nuevos clientes (trim)", nuevos_trim, 15, "", "mayor", "últimos 3 meses"),
            ],
            "procesos": [
                _kpi("uptime",   "Disponibilidad (Uptime)", uptime, 99.9, "%",  "mayor", "nube multi-región"),
                _kpi("ttm",      "Time-to-market",          ttm,       1, "d",  "menor", "commit → producción"),
                _kpi("latencia", "Latencia global",         lat,     200, "ms", "menor", "promedio por región"),
                _kpi("apis",     "APIs documentadas (SDD)", 100,     100, "%",  "mayor", "contrato OpenAPI"),
                _kpi("calidad",  "Calidad del Data Warehouse", calidad, 98, "%", "mayor", "registros válidos"),
            ],
            "aprendizaje": [
                _kpi("horas",   "Horas de capacitación",   horas, 32, "h", "mayor", "run-rate anual / persona"),
                _kpi("ddd",     "Decisiones data-driven",  ddd,   80, "%", "mayor", "con respaldo analítico"),
                _kpi("mlmod",   "Modelos ML en producción", mlmod, 6, "",  "mayor", "pipeline MLOps"),
                _kpi("rotacion","Rotación de personal",    rota,  10, "%", "menor", "talento técnico"),
                _kpi("tecno",   "Tecnologías adoptadas",   tecno,  4, "",  "mayor", "roadmap de innovación"),
            ],
        },
    }


def bsc_kpis():
    r = _bsc_kpi_row()
    return bsc_kpis_payload(r) if r is not None else None


def v1_scorecard():
    r = _bsc_kpi_row()
    if r is None:
        return None
    return {"api_version": "1.0", "disponible": True,
            "mrr_mensual": round(float(r[2]), 2), "clientes_activos": int(r[1]),
            "churn_pct": round(float(r[9]), 2), "uptime_pct": round(float(r[13]), 3)}


def bsc_series_payload(rows):
    """Arma el payload de series/rankings del BSC a partir de las filas largas de
    agg_bsc_series. Compartido por serving.bsc_series() (ClickHouse) y el fallback
    de app.py (vista DBT agg_bsc_series en StarRocks)."""
    grp: dict = {}
    for persp, serie, etiqueta, _orden, valor in rows:
        grp.setdefault(persp, {}).setdefault(serie, []).append([etiqueta, round(float(valor), 2)])

    def pares(persp, serie):
        return grp.get(persp, {}).get(serie, [])

    embudo_pairs = pares("cliente", "embudo")
    embudo = [int(v) for _et, v in embudo_pairs] if embudo_pairs else [0, 0, 0]

    return {
        "disponible": True,
        "financiera": {
            "mrr": pares("financiera", "mrr"),
            "api": pares("financiera", "api"),
            "cac": pares("financiera", "cac"),
            "por_plan": pares("financiera", "por_plan"),
        },
        "cliente": {
            "nuevos_mercado": pares("cliente", "nuevos_mercado"),
            "conversion": pares("cliente", "conversion"),
            "churn": pares("cliente", "churn"),
            "nps": pares("cliente", "nps"),
            "embudo": embudo,
        },
        "procesos": {
            "uptime": pares("procesos", "uptime"),
            "ttm": pares("procesos", "ttm"),
            "latencia_region": pares("procesos", "latencia_region"),
            "incidentes": pares("procesos", "incidentes"),
        },
        "ecosistema": {
            "ingresos_partner": pares("ecosistema", "ingresos_partner"),
            "llamadas": pares("ecosistema", "llamadas"),
            "conexiones_partner": pares("ecosistema", "conexiones_partner"),
        },
    }


def bsc_series():
    rows = _q("""SELECT perspectiva, serie, etiqueta, orden, valor FROM agg_bsc_series
                 ORDER BY perspectiva, serie, orden""")
    if not rows:
        return None
    return bsc_series_payload(rows)


# ══════════════════════════════════════════════════════════════════════════════
# REPORTE OPERATIVO DIARIO (CU-O16 · OP11) — lectura SOLO de ClickHouse (RN-1202)
# ══════════════════════════════════════════════════════════════════════════════

def reporte_diario_fuentes():
    """Lee las cifras del reporte operativo diario desde las agregaciones ClickHouse.

    SOLO ClickHouse (RN-1202): no hay fallback a StarRocks aquí (el reporte se
    construye exclusivamente sobre la capa de serving). Devuelve un dict con las
    cifras crudas y su período, o **None** si ClickHouse no está disponible o aún
    no hay agregaciones del período (el reporte queda FALLIDO en ese caso).
    """
    op = _q("""SELECT id_tiempo, periodo, api_llamadas, api_errores, api_latencia_ms,
                      api_ingreso, uso_sesiones, uso_funciones, uso_usuarios_activos,
                      uso_dashboards, incidentes, uptime, despliegues
               FROM agg_reporte_diario ORDER BY id_tiempo DESC LIMIT 1""")
    if not op:
        return None
    o = op[0]

    kv = _q("SELECT total_resenas, puntuacion_promedio FROM agg_kpis_vino LIMIT 1")
    cal = _q("SELECT calidad FROM agg_bsc_kpis LIMIT 1")

    return {
        "periodo": o[1],
        "id_tiempo": int(o[0]),
        # Ingesta (agg_kpis_vino): filas cargadas al DW + calidad del DW (agg_bsc_kpis).
        "ingesta": {
            "resenas_en_dw": int(kv[0][0]) if kv else 0,
            "puntuacion_promedio": float(kv[0][1]) if kv else 0.0,
            "calidad_dw_pct": float(cal[0][0]) if cal else None,
        },
        # API (agg_reporte_diario ← Fact_Consumo_API).
        "api": {
            "llamadas": int(o[2] or 0),
            "errores": int(o[3] or 0),
            "latencia_ms": float(o[4] or 0),
            "ingreso": float(o[5] or 0),
        },
        # Uso de plataforma (agg_reporte_diario ← Fact_Uso_Plataforma).
        "uso": {
            "sesiones": int(o[6] or 0),
            "funciones": int(o[7] or 0),
            "usuarios_activos": int(o[8] or 0),
            "dashboards_vistos": int(o[9] or 0),
        },
        # Incidentes / disponibilidad (agg_reporte_diario ← Fact_Disponibilidad).
        "incidentes": {
            "incidentes": int(o[10] or 0),
            "uptime_pct": float(o[11] or 0),
            "despliegues": int(o[12] or 0),
        },
    }
