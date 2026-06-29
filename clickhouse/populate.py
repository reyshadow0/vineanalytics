"""
Populador de agregaciones StarRocks → ClickHouse (OP3 · Fase 2).

Última etapa del flujo de datos (Princ. IX: ... → agregaciones). Lee el Data
Warehouse Fact-Dim en StarRocks y materializa en ClickHouse las tablas de
agregación que sirven al dashboard/API (ver clickhouse/aggregations.sql).

- Respeta el orden de capas: ClickHouse se alimenta SOLO desde StarRocks (RT-02),
  nunca desde PocketBase.
- Idempotente: TRUNCATE + INSERT en cada tabla.
- Cubre TODAS las agregaciones del dashboard: vino (KPIs, países, variedades,
  puntuación, bodegas, regiones) y BSC (MRR, % API, CAC, LTV/CAC, costo cloud,
  conversión, churn, NPS, adopción, uptime, TTM, latencia, calidad, aprendizaje,
  rankings y embudo).

El DAG de Airflow (fase posterior) ejecuta esta etapa SOLO si las suites de
calidad (CU-O04) pasaron (fail-fast).
"""

import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB, STARROCKS_USER, STARROCKS_PASS,
    CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_DB, CLICKHOUSE_USER, CLICKHOUSE_PASS,
)

DDL_FILE = Path(__file__).resolve().parent / "aggregations.sql"


# ── Conexiones ────────────────────────────────────────────────────────────────

def _sr() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST, port=STARROCKS_PORT, database=STARROCKS_DB,
        user=STARROCKS_USER, password=STARROCKS_PASS, connection_timeout=20,
    )


def _ch():
    import clickhouse_connect
    # Conecta a 'default' para poder crear la base si no existe.
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER, password=CLICKHOUSE_PASS,
    )


# ── Lectura StarRocks ─────────────────────────────────────────────────────────

def _rows(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params) if params else cur.execute(sql)
    out = cur.fetchall()
    cur.close()
    return out


def _scalar(conn, sql, params=()):
    r = _rows(conn, sql, params)
    return r[0][0] if r and r[0] and r[0][0] is not None else None


def _f(v, default=0.0):
    return float(v) if v is not None else float(default)


# ── DDL ───────────────────────────────────────────────────────────────────────

def _run_ddl(ch):
    sql = DDL_FILE.read_text(encoding="utf-8")
    # El DDL fija el nombre 'vinanalytics'; si CLICKHOUSE_DB difiere, lo alineamos.
    if CLICKHOUSE_DB != "vinanalytics":
        sql = sql.replace("vinanalytics", CLICKHOUSE_DB)
    for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
        ch.command(stmt)


def _reset(ch, table):
    ch.command(f"TRUNCATE TABLE IF EXISTS {CLICKHOUSE_DB}.{table}")


# ══════════════════════════════════════════════════════════════════════════════
# AGREGACIONES DE VINO
# ══════════════════════════════════════════════════════════════════════════════

def _pop_vino(sr, ch):
    # KPIs globales
    k = _rows(sr, """
        SELECT COUNT(*),
               ROUND(AVG(CAST(points AS DOUBLE)),1),
               ROUND(AVG(CASE WHEN price>0 THEN CAST(price AS DOUBLE) END),2),
               MAX(CASE WHEN price>0 THEN price END),
               MIN(CASE WHEN price>0 THEN price END)
        FROM fact_resenas
    """)[0]
    n_pais = _scalar(sr, "SELECT COUNT(*) FROM dim_pais") or 0
    n_var  = _scalar(sr, "SELECT COUNT(*) FROM dim_variedad") or 0
    n_bod  = _scalar(sr, "SELECT COUNT(*) FROM dim_bodega") or 0
    _reset(ch, "agg_kpis_vino")
    ch.insert(f"{CLICKHOUSE_DB}.agg_kpis_vino",
              [[int(k[0] or 0), _f(k[1]), _f(k[2]), _f(k[3]), _f(k[4]),
                int(n_pais), int(n_var), int(n_bod)]],
              column_names=["total_resenas", "puntuacion_promedio", "precio_promedio",
                            "precio_maximo", "precio_minimo", "total_paises",
                            "total_variedades", "total_bodegas"])

    # Por país (sirve gráfica países, lista, browse, v1/mercados, comparar)
    rows = _rows(sr, """
        SELECT dp.nombre, COUNT(*),
               ROUND(AVG(CAST(fr.points AS DOUBLE)),1),
               ROUND(AVG(CASE WHEN fr.price>0 THEN CAST(fr.price AS DOUBLE) END),2),
               COUNT(DISTINCT fr.id_variedad)
        FROM fact_resenas fr JOIN dim_pais dp ON fr.id_pais=dp.id_pais
        WHERE dp.nombre!='Desconocido'
        GROUP BY dp.nombre
    """)
    _reset(ch, "agg_pais")
    if rows:
        ch.insert(f"{CLICKHOUSE_DB}.agg_pais",
                  [[r[0], int(r[1]), _f(r[2]), _f(r[3]), int(r[4] or 0)] for r in rows],
                  column_names=["pais", "total", "puntuacion_promedio",
                                "precio_promedio", "variedades"])

    # Por variedad (total = todas; total_con_precio = filas con price>0, para la gráfica)
    rows = _rows(sr, """
        SELECT dv.nombre, COUNT(*),
               ROUND(AVG(CASE WHEN fr.price>0 THEN CAST(fr.price AS DOUBLE) END),2),
               SUM(CASE WHEN fr.price>0 THEN 1 ELSE 0 END)
        FROM fact_resenas fr JOIN dim_variedad dv ON fr.id_variedad=dv.id_variedad
        WHERE dv.nombre!='Desconocido'
        GROUP BY dv.nombre
    """)
    _reset(ch, "agg_variedad")
    if rows:
        ch.insert(f"{CLICKHOUSE_DB}.agg_variedad",
                  [[r[0], int(r[1]), _f(r[2]), int(r[3] or 0)] for r in rows],
                  column_names=["variedad", "total", "precio_promedio", "total_con_precio"])

    # Por bodega
    rows = _rows(sr, """
        SELECT db.nombre, COUNT(*), ROUND(AVG(CAST(fr.points AS DOUBLE)),1)
        FROM fact_resenas fr JOIN dim_bodega db ON fr.id_bodega=db.id_bodega
        WHERE db.nombre!='Desconocido'
        GROUP BY db.nombre
    """)
    _reset(ch, "agg_bodega")
    if rows:
        ch.insert(f"{CLICKHOUSE_DB}.agg_bodega",
                  [[r[0], int(r[1]), _f(r[2])] for r in rows],
                  column_names=["bodega", "total", "puntuacion_promedio"])

    # Por región
    rows = _rows(sr, """
        SELECT dr.nombre, COUNT(*)
        FROM fact_resenas fr JOIN dim_region dr ON fr.id_region=dr.id_region
        WHERE dr.nombre!='Desconocido'
        GROUP BY dr.nombre
    """)
    _reset(ch, "agg_region")
    if rows:
        ch.insert(f"{CLICKHOUSE_DB}.agg_region",
                  [[r[0], int(r[1])] for r in rows],
                  column_names=["region", "total"])

    # Histograma de puntuación
    rows = _rows(sr, "SELECT points, COUNT(*) FROM fact_resenas GROUP BY points ORDER BY points")
    _reset(ch, "agg_puntuacion_hist")
    if rows:
        ch.insert(f"{CLICKHOUSE_DB}.agg_puntuacion_hist",
                  [[int(r[0]), int(r[1])] for r in rows],
                  column_names=["puntuacion", "total"])

    print(f"  [OK] Vino: KPIs + {len(rows)} barras de puntuación + dims agregadas")


# ══════════════════════════════════════════════════════════════════════════════
# AGREGACIONES BSC (replica las consultas de /api/bsc/kpis y /api/bsc/series)
# ══════════════════════════════════════════════════════════════════════════════

def _pop_bsc(sr, ch):
    row = _rows(sr, "SELECT MAX(id_tiempo), MIN(id_tiempo) FROM dim_tiempo")
    if not row or row[0][0] is None:
        _reset(ch, "agg_bsc_kpis")
        _reset(ch, "agg_bsc_series")
        print("  [SKIP] BSC sin datos (dim_tiempo vacía)")
        return
    latest = int(row[0][0])
    prev_year = latest - 100
    u3 = [int(r[0]) for r in _rows(sr, "SELECT id_tiempo FROM dim_tiempo ORDER BY id_tiempo DESC LIMIT 3")]

    def v(sql, params=()):
        return _f(_scalar(sr, sql, params))

    # ── KPIs (mismas fórmulas que app.api_bsc_kpis) ───────────────────────────
    mrr_now  = v("SELECT SUM(mrr) FROM fact_suscripcion WHERE id_tiempo=%s AND es_churn=0", (latest,))
    mrr_prev = v("SELECT SUM(mrr) FROM fact_suscripcion WHERE id_tiempo=%s AND es_churn=0", (prev_year,))
    mrr_growth = ((mrr_now / mrr_prev) - 1) * 100 if mrr_prev else 0
    api_now  = v("SELECT SUM(ingreso_api) FROM fact_consumo_api WHERE id_tiempo=%s", (latest,))
    api_share = api_now / (mrr_now + api_now) * 100 if (mrr_now + api_now) else 0
    cac_now  = v("SELECT AVG(cac) FROM fact_conversion WHERE id_tiempo=%s AND conversiones>0", (latest,))
    ltv_now  = v("SELECT AVG(ltv) FROM fact_retencion WHERE id_tiempo=%s AND activo=1", (latest,))
    ltv_cac  = ltv_now / cac_now if cac_now else 0
    cloud    = v("SELECT SUM(costo_cloud) FROM fact_disponibilidad WHERE id_tiempo=%s", (latest,))
    activos  = v("SELECT SUM(activo) FROM fact_retencion WHERE id_tiempo=%s", (latest,)) or 1
    cloud_cli = cloud / activos

    cv = _rows(sr, "SELECT SUM(conversiones), SUM(leads) FROM fact_conversion WHERE id_tiempo=%s", (latest,))[0]
    conv = (_f(cv[0]) / _f(cv[1]) * 100) if cv and cv[1] else 0
    rt = _rows(sr, "SELECT SUM(cancelacion), SUM(activo) FROM fact_retencion WHERE id_tiempo=%s", (latest,))[0]
    churn = (_f(rt[0]) / (_f(rt[1]) + _f(rt[0])) * 100) if rt and (rt[0] or rt[1]) else 0
    npsr = _rows(sr, """SELECT SUM(CASE WHEN nps_score>=9 THEN 1 ELSE 0 END),
                               SUM(CASE WHEN nps_score BETWEEN 0 AND 6 THEN 1 ELSE 0 END),
                               SUM(CASE WHEN nps_score>=0 THEN 1 ELSE 0 END)
                        FROM fact_uso_plataforma WHERE id_tiempo=%s""", (latest,))[0]
    nps = ((_f(npsr[0]) - _f(npsr[1])) / _f(npsr[2]) * 100) if npsr and npsr[2] else 0
    adr = _rows(sr, "SELECT SUM(usuarios_activos), SUM(usuarios_totales) FROM fact_uso_plataforma WHERE id_tiempo=%s", (latest,))[0]
    adopcion = (_f(adr[0]) / _f(adr[1]) * 100) if adr and adr[1] else 0
    nuevos_trim = v(f"SELECT SUM(es_nuevo) FROM fact_suscripcion WHERE id_tiempo IN ({','.join(map(str,u3))})") if u3 else 0

    dp = _rows(sr, "SELECT AVG(uptime), AVG(time_to_market_dias), AVG(latencia_ms) FROM fact_disponibilidad WHERE id_tiempo=%s", (latest,))[0]
    uptime = _f(dp[0]); ttm = _f(dp[1]); lat = _f(dp[2])
    cq = _rows(sr, "SELECT SUM(CASE WHEN points BETWEEN 80 AND 100 THEN 1 ELSE 0 END), COUNT(*) FROM fact_resenas")[0]
    calidad = (_f(cq[0]) / _f(cq[1]) * 100) if cq and cq[1] else 100.0

    ap = _rows(sr, """SELECT horas_capacitacion, decisiones_data_driven, tecnologias_adoptadas,
                             rotacion_personal, modelos_ml_produccion
                      FROM fact_aprendizaje WHERE id_tiempo=%s""", (latest,))
    ap = ap[0] if ap else (0, 0, 0, 0, 0)
    horas = _f(ap[0]); ddd = _f(ap[1]); tecno = _f(ap[2]); rota = _f(ap[3]); mlmod = _f(ap[4])

    per = _scalar(sr, "SELECT periodo FROM dim_tiempo WHERE id_tiempo=%s", (latest,)) or str(latest)

    _reset(ch, "agg_bsc_kpis")
    ch.insert(f"{CLICKHOUSE_DB}.agg_bsc_kpis",
              [[str(per), int(activos), round(mrr_now, 2), round(mrr_growth, 4),
                round(api_share, 4), round(cac_now, 2), round(ltv_cac, 4), round(cloud_cli, 4),
                round(conv, 4), round(churn, 4), round(nps, 4), round(adopcion, 4), round(nuevos_trim, 2),
                round(uptime, 4), round(ttm, 4), round(lat, 4), round(calidad, 4),
                round(horas, 4), round(ddd, 4), round(mlmod, 4), round(rota, 4), round(tecno, 4)]],
              column_names=["periodo", "clientes_activos", "mrr_actual", "mrr_growth",
                            "api_share", "cac", "ltv_cac", "cloud_cli", "conversion", "churn",
                            "nps", "adopcion", "nuevos_trim", "uptime", "ttm", "latencia",
                            "calidad", "horas", "ddd", "mlmod", "rotacion", "tecno"])

    # ── Series y rankings (formato largo) ─────────────────────────────────────
    T = "JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo"
    series_defs = [
        ("financiera", "mrr",  f"SELECT t.periodo, SUM(f.mrr) FROM fact_suscripcion f {T} WHERE f.es_churn=0 GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("financiera", "api",  f"SELECT t.periodo, SUM(f.ingreso_api) FROM fact_consumo_api f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("financiera", "cac",  f"SELECT t.periodo, AVG(f.cac) FROM fact_conversion f {T} WHERE f.conversiones>0 GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("financiera", "por_plan", "SELECT p.nombre, SUM(f.mrr) FROM fact_suscripcion f JOIN dim_plan p ON f.id_plan=p.id_plan WHERE f.id_tiempo=%s AND f.es_churn=0 GROUP BY p.nombre ORDER BY 2 DESC", (latest,)),
        ("cliente", "nuevos_mercado", "SELECT m.pais, SUM(f.es_nuevo) FROM fact_suscripcion f JOIN dim_cliente c ON f.id_cliente=c.id_cliente JOIN dim_mercado m ON c.id_mercado=m.id_mercado GROUP BY m.pais ORDER BY 2 DESC LIMIT 12", ()),
        ("cliente", "conversion", f"SELECT t.periodo, SUM(f.conversiones)*100.0/SUM(f.leads) FROM fact_conversion f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("cliente", "churn", f"SELECT t.periodo, SUM(f.cancelacion)*100.0/(SUM(f.activo)+SUM(f.cancelacion)) FROM fact_retencion f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("cliente", "nps", f"SELECT t.periodo, (SUM(CASE WHEN f.nps_score>=9 THEN 1 ELSE 0 END)-SUM(CASE WHEN f.nps_score BETWEEN 0 AND 6 THEN 1 ELSE 0 END))*100.0/SUM(CASE WHEN f.nps_score>=0 THEN 1 ELSE 0 END) FROM fact_uso_plataforma f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("procesos", "uptime", f"SELECT t.periodo, AVG(f.uptime) FROM fact_disponibilidad f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("procesos", "ttm", f"SELECT t.periodo, AVG(f.time_to_market_dias) FROM fact_disponibilidad f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("procesos", "latencia_region", "SELECT m.region_geo, AVG(f.latencia_ms) FROM fact_disponibilidad f JOIN dim_mercado m ON f.id_mercado=m.id_mercado WHERE f.id_tiempo=%s GROUP BY m.region_geo ORDER BY 2 DESC", (latest,)),
        ("procesos", "incidentes", f"SELECT t.periodo, SUM(f.incidentes) FROM fact_disponibilidad f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("ecosistema", "ingresos_partner", "SELECT p.nombre, SUM(f.ingreso_api) FROM fact_consumo_api f JOIN dim_partner_api p ON f.id_partner=p.id_partner GROUP BY p.nombre ORDER BY 2 DESC", ()),
        ("ecosistema", "llamadas", f"SELECT t.periodo, SUM(f.llamadas) FROM fact_consumo_api f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo", ()),
        ("ecosistema", "conexiones_partner", "SELECT p.nombre, MAX(f.conexiones_activas) FROM fact_integracion_partner f JOIN dim_partner_api p ON f.id_partner=p.id_partner WHERE f.id_tiempo=%s GROUP BY p.nombre ORDER BY 2 DESC", (latest,)),
    ]

    long_rows = []
    for perspectiva, serie, sql, params in series_defs:
        for i, r in enumerate(_rows(sr, sql, params)):
            long_rows.append([perspectiva, serie, str(r[0]), i, round(_f(r[1]), 4)])

    # Embudo (3 valores del período más reciente)
    emb = _rows(sr, "SELECT SUM(leads), SUM(oportunidades), SUM(conversiones) FROM fact_conversion WHERE id_tiempo=%s", (latest,))[0]
    for i, et in enumerate(["leads", "oportunidades", "conversiones"]):
        long_rows.append(["cliente", "embudo", et, i, _f(emb[i] if emb else 0)])

    _reset(ch, "agg_bsc_series")
    if long_rows:
        ch.insert(f"{CLICKHOUSE_DB}.agg_bsc_series", long_rows,
                  column_names=["perspectiva", "serie", "etiqueta", "orden", "valor"])

    print(f"  [OK] BSC: KPIs período {per} + {len(long_rows)} puntos de series/rankings")


# ══════════════════════════════════════════════════════════════════════════════

def populate() -> dict:
    print("Conectando a StarRocks y ClickHouse ...")
    sr = _sr()
    ch = _ch()
    try:
        _run_ddl(ch)
        print("  [OK] Esquema ClickHouse asegurado\n")
        _pop_vino(sr, ch)
        _pop_bsc(sr, ch)
    finally:
        sr.close()
        ch.close()
    print("\n" + "=" * 56)
    print("AGREGACIONES ClickHouse ACTUALIZADAS")
    print("=" * 56)
    return {"ok": True}


if __name__ == "__main__":
    populate()
