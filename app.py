"""
VinAnalytics Group — Servidor Flask principal.

ETL:
  POST /etl/cargar-pocketbase  → CSV → PocketBase
  POST /etl/extraer            → PocketBase → stage/retail_raw.parquet
  POST /etl/transformar        → raw → dimensiones + fact (parquet)
  POST /etl/cargar-starrocks   → parquet → StarRocks (modelo estrella)
  POST /etl/reset-starrocks    → borra y recrea todas las tablas
  GET  /etl/status             → estado de archivos, PocketBase y StarRocks

Dashboard:
  GET  /                       → index.html
  GET  /api/kpis               → métricas clave
  GET  /api/interacciones      → registros paginados + filtros
  GET  /api/graficas/precios   → histograma de precios
  GET  /api/graficas/canal     → conversiones por canal
  GET  /api/graficas/region    → interacciones por región
  GET  /api/graficas/tendencia → serie diaria últimos 30 días
"""

import io
import os
import sys
from datetime import date
from pathlib import Path

import mysql.connector
import requests as _http
from flask import Flask, jsonify, render_template, request, session, redirect, url_for

from config import (
    STARROCKS_DB, STARROCKS_HOST, STARROCKS_PASS, STARROCKS_PORT, STARROCKS_USER,
    POCKETBASE_URL, POCKETBASE_COLLECTION, STAGE_DIR,
)

import serving   # capa de lectura ClickHouse (Fase 2) con fallback a StarRocks

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vinanalytics-secret-2024")

from auth import auth_bp
from models import init_default_users, get_all_users, create_user, update_user, delete_user, username_exists
from audit import registrar_evento, get_eventos
from backup_manager import (
    list_backups, create_backup, restore_backup, delete_backup,
    get_db_status, get_recovery_history, start_monitor,
)
app.register_blueprint(auth_bp)

with app.app_context():
    try:
        from db.starrocks_setup import setup as _sr_setup
        _sr_setup()
        from db.bsc_setup import setup_bsc as _bsc_setup
        _bsc_setup()
        init_default_users()
        start_monitor()
    except Exception as _e:
        print(f"[WARN] Inicialización StarRocks: {_e}")
    # CU-O08 (OP5): base operacional de cuentas/suscripciones en PocketBase.
    # Independiente de StarRocks; si PocketBase no está arriba aún, no bloquea.
    try:
        from db.pb_setup import setup as _pb_setup
        print(f"[OK] PocketBase suscripciones: {_pb_setup()}")
    except Exception as _e:
        print(f"[WARN] Inicialización PocketBase (suscripciones): {_e}")

STAGE         = Path(STAGE_DIR)
RAW_PARQUET   = STAGE / "wine_raw.parquet"
CLEAN_PARQUET = STAGE / "wine_clean.parquet"

DROP_ORDER = [
    "fact_resenas",
    "dim_pais", "dim_variedad", "dim_bodega",
    "dim_provincia", "dim_region", "dim_catador",
]


# ── Helpers de base de datos ──────────────────────────────────────────────────

def _conn() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        database=STARROCKS_DB,
        user=STARROCKS_USER,
        password=STARROCKS_PASS,
        connection_timeout=10,
    )


def _fetchall(sql: str, params: tuple = ()) -> list[tuple]:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def _fetchone(sql: str, params: tuple = ()):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        return cur.fetchone()
    finally:
        conn.close()


def _table_count(table: str) -> int:
    try:
        row = _fetchone(f"SELECT COUNT(*) FROM `{table}`")
        return int(row[0]) if row else 0
    except Exception:
        return -1


# ── Helper ETL: captura stdout ───────────────────────────────────────────────

def _run(fn, *args, **kwargs):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        result = fn(*args, **kwargs)
    except SystemExit as exc:
        raise RuntimeError(f"El proceso ETL terminó con sys.exit({exc.code})") from exc
    finally:
        sys.stdout = old
    return result, buf.getvalue()


# ═════════════════════════════════════════════════════════════════════════════
# RUTAS ETL
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/etl/cargar-pocketbase", methods=["POST"])
def etl_cargar_pocketbase():
    """Carga el CSV de vinos a PocketBase en lotes."""
    try:
        from etl.pb_loader import upload
        insertados, log = _run(upload)
        return jsonify({"ok": True, "insertados": insertados, "log": log})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/etl/generar-aleatorio", methods=["POST"])
def etl_generar_aleatorio():
    """Genera reseñas aleatorias directo en StarRocks (fact_resenas)."""
    try:
        body = request.get_json(silent=True) or {}
        n = int(body.get("n", 100_000))
        from etl.data_generator import generate
        total_ok, log = _run(generate, n)
        return jsonify({"ok": True, "insertados": total_ok, "log": log})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/etl/extraer", methods=["POST"])
def etl_extraer():
    """E — Extrae todos los registros de PocketBase → stage/retail_raw.parquet."""
    try:
        from etl.extractor import extract
        out_path, log = _run(extract)
        return jsonify({
            "ok":     True,
            "archivo": str(out_path),
            "bytes":   out_path.stat().st_size,
            "log":     log,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/etl/transformar", methods=["POST"])
def etl_transformar():
    """
    T — Transforma retail_raw.parquet:
    Parsea tipos, construye dimensiones y fact_interacciones en Python.
    Guarda todos los parquet en stage/.
    """
    try:
        from etl.transformer import transform
        tables, log = _run(transform)
        resumen = {name: len(df) for name, df in tables.items()}
        return jsonify({
            "ok":     True,
            "resumen": resumen,
            "log":    log,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/etl/cargar-starrocks", methods=["POST"])
def etl_cargar_starrocks():
    """
    L — Carga los DataFrames transformados en StarRocks (modelo estrella).
    Body JSON opcional: {"limit": 50000}
    """
    try:
        body  = request.get_json(silent=True) or {}
        limit = int(body["limit"]) if body.get("limit") is not None else None

        from etl.transformer import transform
        tables, log_t = _run(transform)

        from etl.loader import load
        counts, log_l = _run(load, tables=tables, limit=limit)

        return jsonify({
            "ok":     True,
            "resumen": counts,
            "log":    log_t + "\n" + log_l,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/etl/reset-starrocks", methods=["POST"])
def etl_reset_starrocks():
    """
    Borra todas las tablas y las recrea vacías.
    Body JSON requerido: {"confirmar": true}
    """
    body = request.get_json(silent=True) or {}
    if not body.get("confirmar"):
        return jsonify({
            "error": 'Se requiere {"confirmar": true} para ejecutar el reset.'
        }), 400

    try:
        conn = _conn()
        cur  = conn.cursor()

        dropped = []
        errores = []
        for table in DROP_ORDER:
            try:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`")
                conn.commit()
                dropped.append(table)
            except Exception as exc:
                errores.append(f"{table}: {exc}")

        cur.close()
        conn.close()

        from db.starrocks_setup import setup
        _, log = _run(setup)

        return jsonify({
            "ok":               True,
            "tablas_eliminadas": dropped,
            "errores_drop":     errores,
            "log":              log,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/etl/status", methods=["GET"])
def etl_status():
    pb_accesible = False
    pb_registros = None
    try:
        r = _http.get(f"{POCKETBASE_URL}/api/health", timeout=3)
        pb_accesible = r.status_code == 200
    except Exception:
        pass

    if pb_accesible:
        try:
            r2 = _http.get(
                f"{POCKETBASE_URL}/api/collections/{POCKETBASE_COLLECTION}/records",
                params={"page": 1, "perPage": 1},
                timeout=5,
            )
            if r2.status_code == 200:
                pb_registros = r2.json().get("totalItems")
        except Exception:
            pass

    sr_tables = list(reversed(DROP_ORDER))
    starrocks = {t: _table_count(t) for t in sr_tables}

    stage_files = {}
    for fname in ["wine_raw.parquet", "wine_clean.parquet",
                  "dim_pais.parquet", "dim_variedad.parquet", "dim_bodega.parquet",
                  "dim_provincia.parquet", "dim_region.parquet",
                  "dim_catador.parquet", "fact_resenas.parquet"]:
        p = STAGE / fname
        stage_files[fname] = p.stat().st_size if p.exists() else None

    return jsonify({
        "pocketbase_accesible": pb_accesible,
        "pocketbase_registros": pb_registros,
        "stage":     stage_files,
        "starrocks": starrocks,
    })


# ═════════════════════════════════════════════════════════════════════════════
# RUTAS DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/vinos")
def vinos():
    return render_template("vinos.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next="/dashboard"))
    return render_template("index.html", show_admin=False)


@app.route("/admin")
def admin():
    if session.get("rol") != "admin":
        if "user_id" not in session:
            return redirect(url_for("auth.login", next="/admin"))
        return redirect(url_for("dashboard"))
    return render_template("index.html", show_admin=True)


@app.route("/api/kpis")
def api_kpis():
    _ch = serving.kpis()
    if _ch is not None:
        return jsonify(_ch)
    # Fallback (ClickHouse no disponible): lee la MISMA agregación desde la vista
    # DBT en StarRocks (serving.agg_kpis_vino). Princ. VI: sin GROUP BY en Python.
    try:
        row = _fetchone("""SELECT total_resenas, puntuacion_promedio, precio_promedio,
                                  precio_maximo, precio_minimo, total_paises,
                                  total_variedades, total_bodegas
                           FROM agg_kpis_vino LIMIT 1""")
        if not row:
            return jsonify({"total_resenas": 0, "puntuacion_promedio": 0, "precio_promedio": 0,
                            "precio_maximo": 0, "precio_minimo": 0, "total_paises": 0,
                            "total_variedades": 0, "total_bodegas": 0})
        return jsonify({
            "total_resenas":       int(row[0] or 0),
            "puntuacion_promedio": float(row[1] or 0),
            "precio_promedio":     float(row[2] or 0),
            "precio_maximo":       float(row[3] or 0),
            "precio_minimo":       float(row[4] or 0),
            "total_paises":        int(row[5] or 0),
            "total_variedades":    int(row[6] or 0),
            "total_bodegas":       int(row[7] or 0),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/resenas")
def api_resenas():
    try:
        page     = max(1,   int(request.args.get("page",     1)))
        per_page = min(200, int(request.args.get("per_page", 50)))
        offset   = (page - 1) * per_page

        conditions, params = [], []

        if v := request.args.get("pais"):
            conditions.append("dp.nombre = %s"); params.append(v)
        if v := request.args.get("variedad"):
            conditions.append("dv.nombre = %s"); params.append(v)
        if v := request.args.get("bodega"):
            conditions.append("db.nombre LIKE %s"); params.append(f"%{v}%")
        if v := request.args.get("puntos_min"):
            conditions.append("fr.points >= %s"); params.append(int(v))
        if v := request.args.get("precio_max"):
            conditions.append("fr.price <= %s"); params.append(float(v))

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        base_join = """
            FROM fact_resenas fr
            JOIN dim_pais      dp  ON fr.id_pais      = dp.id_pais
            JOIN dim_variedad  dv  ON fr.id_variedad  = dv.id_variedad
            JOIN dim_bodega    db  ON fr.id_bodega    = db.id_bodega
            JOIN dim_provincia dpr ON fr.id_provincia = dpr.id_provincia
            JOIN dim_region    dr  ON fr.id_region    = dr.id_region
            JOIN dim_catador   dc  ON fr.id_catador   = dc.id_catador
        """

        total = int(_fetchone(f"SELECT COUNT(*) {base_join} {where}", tuple(params))[0])

        rows = _fetchall(
            f"""
            SELECT fr.id_resena, fr.title, dv.nombre AS variedad,
                   dp.nombre AS pais, db.nombre AS bodega,
                   dpr.nombre AS provincia, dr.nombre AS region,
                   fr.points, fr.price, dc.nombre AS catador
            {base_join} {where}
            ORDER BY fr.points DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params) + (per_page, offset),
        )

        return jsonify({
            "total":       total,
            "page":        page,
            "per_page":    per_page,
            "total_pages": -(-total // per_page),
            "data": [
                {"id": r[0], "title": r[1], "variedad": r[2], "pais": r[3],
                 "bodega": r[4], "provincia": r[5], "region": r[6],
                 "points": r[7], "price": float(r[8]), "catador": r[9]}
                for r in rows
            ],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/paises")
def api_graficas_paises():
    _ch = serving.grafica_paises()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_pais en StarRocks (sin GROUP BY en Python).
        rows = _fetchall("""SELECT pais, puntuacion_promedio, total FROM agg_pais
                            ORDER BY puntuacion_promedio DESC LIMIT 15""")
        return jsonify([{"pais": r[0], "puntuacion": float(r[1]), "total": int(r[2])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/variedades")
def api_graficas_variedades():
    _ch = serving.grafica_variedades()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_variedad en StarRocks.
        rows = _fetchall("""SELECT variedad, precio_promedio, total_con_precio FROM agg_variedad
                            WHERE precio_promedio > 0 ORDER BY precio_promedio DESC LIMIT 12""")
        return jsonify([{"variedad": r[0], "precio_promedio": float(r[1]), "total": int(r[2])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/puntuacion")
def api_graficas_puntuacion():
    _ch = serving.grafica_puntuacion()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_puntuacion_hist en StarRocks.
        rows = _fetchall("SELECT puntuacion, total FROM agg_puntuacion_hist ORDER BY puntuacion")
        return jsonify([{"puntuacion": int(r[0]), "total": int(r[1])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/bodegas")
def api_graficas_bodegas():
    _ch = serving.grafica_bodegas()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_bodega en StarRocks.
        rows = _fetchall("""SELECT bodega, puntuacion_promedio, total FROM agg_bodega
                            WHERE total >= 10 ORDER BY puntuacion_promedio DESC LIMIT 10""")
        return jsonify([{"bodega": r[0], "puntuacion": float(r[1]), "total": int(r[2])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/export/csv")
def api_export_csv():
    """Exporta reseñas filtradas como CSV (máx 50 000 filas)."""
    try:
        import csv as _csv

        conditions, params = [], []
        if v := request.args.get("pais"):
            conditions.append("dp.nombre = %s"); params.append(v)
        if v := request.args.get("variedad"):
            conditions.append("dv.nombre = %s"); params.append(v)
        if v := request.args.get("bodega"):
            conditions.append("db.nombre LIKE %s"); params.append(f"%{v}%")
        if v := request.args.get("puntos_min"):
            conditions.append("fr.points >= %s"); params.append(int(v))
        if v := request.args.get("precio_max"):
            conditions.append("fr.price <= %s"); params.append(float(v))

        limit = min(int(request.args.get("limit", 10_000)), 50_000)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = _fetchall(f"""
            SELECT fr.title, dv.nombre, dp.nombre, db.nombre,
                   dpr.nombre, dr.nombre, fr.points, fr.price, dc.nombre
            FROM fact_resenas fr
            JOIN dim_pais      dp  ON fr.id_pais      = dp.id_pais
            JOIN dim_variedad  dv  ON fr.id_variedad  = dv.id_variedad
            JOIN dim_bodega    db  ON fr.id_bodega    = db.id_bodega
            JOIN dim_provincia dpr ON fr.id_provincia = dpr.id_provincia
            JOIN dim_region    dr  ON fr.id_region    = dr.id_region
            JOIN dim_catador   dc  ON fr.id_catador   = dc.id_catador
            {where}
            ORDER BY fr.points DESC
            LIMIT %s
        """, tuple(params) + (limit,))

        buf = io.StringIO()
        w = _csv.writer(buf)
        w.writerow(["Título", "Variedad", "País", "Bodega", "Provincia", "Región", "Puntos", "Precio", "Catador"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3], r[4], r[5], int(r[6]),
                        f"{float(r[7]):.2f}" if r[7] else "", r[8]])

        from flask import Response
        return Response(
            buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=vinanalytics_reporte.csv"},
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/comparar-mercados")
def api_graficas_comparar_mercados():
    """KPIs comparativos para hasta 4 países (query param: paises=Italy,France,...)."""
    _paises = [p.strip() for p in request.args.get("paises", "").split(",") if p.strip()][:4]
    _ch = serving.comparar_mercados(_paises)
    if _ch is not None:
        return jsonify(_ch)
    # Fallback: vista DBT serving.agg_pais en StarRocks (sin recomputar por país).
    try:
        paises = [p.strip() for p in request.args.get("paises", "").split(",") if p.strip()][:4]
        if not paises:
            return jsonify([])

        ph = ", ".join(["%s"] * len(paises))
        rows = _fetchall(f"""SELECT pais, total, puntuacion_promedio, precio_promedio, variedades
                             FROM agg_pais WHERE pais IN ({ph})""", tuple(paises))
        por_pais = {r[0]: r for r in rows}
        result = []
        for pais in paises:
            if pais in por_pais:
                r = por_pais[pais]
                result.append({
                    "pais":       pais,
                    "total":      int(r[1] or 0),
                    "puntuacion": float(r[2] or 0),
                    "precio":     float(r[3] or 0),
                    "variedades": int(r[4] or 0),
                })
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/tendencias-precio")
def api_graficas_tendencias_precio():
    """Evolución de precio promedio por año extraído del título. Incluye proyección 2 períodos."""
    try:
        variedad = request.args.get("variedad", "").strip()

        # Princ. VI: la agregación (avg precio por año) vive en la vista DBT
        # serving.agg_tendencia_precio; aquí solo se LEE y se calcula la regresión
        # (presentación). '__ALL__' = agregado global (sin filtro de variedad).
        clave = variedad if variedad else "__ALL__"
        rows = _fetchall("""SELECT anio, precio_promedio, total FROM agg_tendencia_precio
                            WHERE variedad = %s ORDER BY anio""", (clave,))

        historico = []
        for yr_str, avg_price, total in rows:
            try:
                yr = int(yr_str)
            except (TypeError, ValueError):
                continue
            if 2005 <= yr <= 2023:
                historico.append({"year": yr, "precio": float(avg_price or 0), "total": int(total)})

        historico.sort(key=lambda x: x["year"])

        if len(historico) < 2:
            return jsonify({"variedad": variedad or "Todas", "historico": historico, "proyeccion": [], "tendencia": 0})

        xs = [h["year"] for h in historico]
        ys = [h["precio"] for h in historico]
        n  = len(xs)
        sx, sy = sum(xs), sum(ys)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, ys))
        denom = n * sxx - sx * sx
        m = (n * sxy - sx * sy) / denom if denom else 0
        b = (sy - m * sx) / n

        last_yr = max(xs)
        proyeccion = [
            {"year": last_yr + 1, "precio": round(max(0, m * (last_yr + 1) + b), 2)},
            {"year": last_yr + 2, "precio": round(max(0, m * (last_yr + 2) + b), 2)},
        ]

        return jsonify({
            "variedad":   variedad or "Todas las variedades",
            "historico":  historico,
            "proyeccion": proyeccion,
            "tendencia":  round(m, 4),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/paises")
def api_paises():
    """Lista todos los países disponibles ordenados por cantidad de reseñas."""
    _ch = serving.paises()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_pais en StarRocks.
        rows = _fetchall("SELECT pais, total FROM agg_pais ORDER BY total DESC")
        return jsonify([{"nombre": r[0], "total": int(r[1])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/variedades")
def api_variedades():
    """Lista las principales variedades ordenadas por cantidad de reseñas."""
    _ch = serving.variedades()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_variedad en StarRocks.
        rows = _fetchall("SELECT variedad, total FROM agg_variedad ORDER BY total DESC LIMIT 60")
        return jsonify([{"nombre": r[0], "total": int(r[1])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/browse")
def api_browse():
    _ch = serving.browse()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vistas DBT serving.agg_* en StarRocks (top 6 por total).
        paises     = _fetchall("SELECT pais, total FROM agg_pais ORDER BY total DESC LIMIT 6")
        variedades = _fetchall("SELECT variedad, total FROM agg_variedad ORDER BY total DESC LIMIT 6")
        bodegas    = _fetchall("SELECT bodega, total FROM agg_bodega ORDER BY total DESC LIMIT 6")
        regiones   = _fetchall("SELECT region, total FROM agg_region ORDER BY total DESC LIMIT 6")
        return jsonify({
            "paises":     [{"nombre": r[0], "total": int(r[1])} for r in paises],
            "variedades": [{"nombre": r[0], "total": int(r[1])} for r in variedades],
            "bodegas":    [{"nombre": r[0], "total": int(r[1])} for r in bodegas],
            "regiones":   [{"nombre": r[0], "total": int(r[1])} for r in regiones],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# BALANCED SCORECARD CORPORATIVO  (CU-E01 … CU-E08)
# Alimentado por las agregaciones declarativas DBT (serving.agg_bsc_*), leídas de
# ClickHouse vía serving.py con fallback a la vista StarRocks. app.py NO calcula
# agregaciones del BSC: la lógica vive en dbt_vinanalytics/models/serving/ (Princ. VI).
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/balanced-scorecard")
def balanced_scorecard():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next="/balanced-scorecard"))
    return render_template("balanced_scorecard.html",
                           show_admin=(session.get("rol") == "admin"))


@app.route("/etl/generar-bsc", methods=["POST"])
def etl_generar_bsc():
    """Crea (si faltan) y puebla las tablas del Balanced Scorecard con datos sintéticos."""
    try:
        from db.bsc_setup import setup_bsc
        from etl.bsc_generator import generate_bsc
        _, log1 = _run(setup_bsc)
        resumen, log2 = _run(generate_bsc)
        return jsonify({"ok": True, "resumen": resumen, "log": (log1 + "\n" + log2).strip()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/bsc/kpis")
def api_bsc_kpis():
    """CU-E01 — Tarjetas del Balanced Scorecard por las 4 perspectivas."""
    _ch = serving.bsc_kpis()
    if _ch is not None:
        return jsonify(_ch)
    # Fallback: lee la MISMA agregación desde la vista DBT serving.agg_bsc_kpis en
    # StarRocks y reutiliza el formateador de tarjetas de serving (metas/umbrales en
    # un solo lugar). Princ. VI: el cálculo de KPIs ya no se duplica aquí.
    try:
        row = _fetchone("""SELECT periodo, clientes_activos, mrr_actual, mrr_growth, api_share,
                                  cac, ltv_cac, cloud_cli, conversion, churn, nps, adopcion,
                                  nuevos_trim, uptime, ttm, latencia, calidad,
                                  horas, ddd, mlmod, rotacion, tecno
                           FROM agg_bsc_kpis LIMIT 1""")
        if not row:
            return jsonify({"disponible": False})
        return jsonify(serving.bsc_kpis_payload(row))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/bsc/series")
def api_bsc_series():
    """Series temporales y rankings para los casos CU-E02 … CU-E06."""
    _ch = serving.bsc_series()
    if _ch is not None:
        return jsonify(_ch)
    # Fallback: lee la MISMA agregación de series desde la vista DBT
    # serving.agg_bsc_series en StarRocks y reutiliza el armador de serving.
    # Princ. VI: las 16 consultas de series ya no se duplican aquí.
    try:
        rows = _fetchall("""SELECT perspectiva, serie, etiqueta, orden, valor FROM agg_bsc_series
                            ORDER BY perspectiva, serie, orden""")
        if not rows:
            return jsonify({"disponible": False})
        return jsonify(serving.bsc_series_payload(rows))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# INTELIGENCIA / MACHINE LEARNING  (OE4 · secciones 9.10–9.11)
# Churn · Segmentación RFM · Precios dinámicos · Detección de anomalías
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/inteligencia")
def inteligencia():
    if "user_id" not in session:
        return redirect(url_for("auth.login", next="/inteligencia"))
    return render_template("inteligencia.html",
                           show_admin=(session.get("rol") == "admin"))


@app.route("/api/ml/churn")
def api_ml_churn():
    """CU-E05 / CU-T09 / CU-O12 — Predicción de churn por cuenta."""
    try:
        from etl.ml_models import predecir_churn
        return jsonify(predecir_churn())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/ml/segmentacion")
def api_ml_segmentacion():
    """CU-T02 — Segmentación RFM de clientes B2B."""
    try:
        from etl.ml_models import segmentar_clientes
        return jsonify(segmentar_clientes())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/ml/precios")
def api_ml_precios():
    """CU-T08 / CU-E02 — Precios dinámicos y demanda por mercado."""
    try:
        from etl.ml_models import precios_dinamicos, tendencia_demanda_mercado
        data = precios_dinamicos()
        data["mercados"] = tendencia_demanda_mercado().get("mercados", [])
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/ml/anomalias")
def api_ml_anomalias():
    """CU-E04 / CU-O13 — Detección de anomalías en series de negocio."""
    try:
        from etl.ml_models import detectar_anomalias
        return jsonify(detectar_anomalias())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# REPORTE OPERATIVO DIARIO  (OP11 · CU-O16)
# Consolida ingesta/API/uso/incidentes SOLO desde ClickHouse (RN-1202), con gate
# de calidad CU-O04 (RF-1104). La generación oficial corre como último paso del
# DAG; estos endpoints exponen la vista (tablero) y el export del Administrador.
# ═════════════════════════════════════════════════════════════════════════════

def _reporte_diario_payload():
    """Devuelve el reporte del día. Con `?fecha=AAAA-MM-DD` lee el archivado
    (reproducibilidad RN-1205); sin fecha, lo genera en vivo en modo solo-lectura
    (sin archivar ni persistir). Solo-ClickHouse para las cifras (RN-1202)."""
    import json as _json
    from reportes import reporte_diario as rd
    fecha = request.args.get("fecha")
    if fecha:
        f = rd.ARCHIVO_DIR / f"reporte_diario_{fecha}.json"
        if not f.exists():
            return None, f"Sin reporte archivado para {fecha}."
        return _json.loads(f.read_text(encoding="utf-8")), None
    return rd.generar(persistir=False, archivar_fn=lambda r: None), None


@app.route("/api/reporte-diario")
def api_reporte_diario():
    """CU-O16 — Reporte operativo diario (tablero/export) para el Administrador."""
    if session.get("rol") != "admin":
        return jsonify({"error": "no autorizado"}), 403
    try:
        rep, err = _reporte_diario_payload()
        if err:
            return jsonify({"error": err}), 404
        return jsonify(rep)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/reporte-diario")
def reporte_diario_export():
    """Export del reporte diario (JSON descargable) — RF-1105."""
    if session.get("rol") != "admin":
        return redirect(url_for("auth.login", next="/reporte-diario"))
    try:
        import json as _json
        rep, err = _reporte_diario_payload()
        if err:
            return jsonify({"error": err}), 404
        from flask import Response
        nombre = f"reporte_diario_{rep.get('fecha', 'hoy')}.json"
        return Response(
            _json.dumps(rep, ensure_ascii=False, indent=2),
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={nombre}"},
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ═════════════════════════════════════════════════════════════════════════════
# API PÚBLICA v1  (OE2 · CU-T03 SDD/OpenAPI · CU-O07)
# Autenticación por API key + límite de tasa. Documentada en /api-docs.
# ═════════════════════════════════════════════════════════════════════════════

from functools import wraps as _wraps
import time as _time

API_KEYS = {
    "vinapi_demo_2026":          "Demo / Sandbox",
    "vinapi_mercadovino_latam":  "Mercado Vino LATAM",
    "vinapi_winehub":            "WineHub API",
    "vinapi_vinoconnect":        "VinoConnect",
}
_RATE_LIMIT   = 60          # solicitudes por minuto y por key
_RATE_WINDOW  = 60.0
_rl_state: dict[str, list[float]] = {}
_api_metrics  = {"total": 0, "por_key": {}}


def require_api_key(fn):
    @_wraps(fn)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key") or request.args.get("api_key")
        if not key or key not in API_KEYS:
            return jsonify({"error": "API key inválida o ausente",
                            "ayuda": "Envíe el header X-API-Key. Documentación en /api-docs"}), 401
        now = _time.time()
        win = _rl_state.setdefault(key, [])
        win[:] = [t for t in win if now - t < _RATE_WINDOW]
        if len(win) >= _RATE_LIMIT:
            return jsonify({"error": f"Límite de tasa excedido ({_RATE_LIMIT}/min)"}), 429
        win.append(now)
        _api_metrics["total"] += 1
        _api_metrics["por_key"][key] = _api_metrics["por_key"].get(key, 0) + 1
        return fn(*args, **kwargs)
    return wrapper


@app.route("/api/v1/health")
def api_v1_health():
    fact = _table_count("fact_resenas")
    return jsonify({"status": "ok", "version": "1.0", "servicio": "VinAnalytics Public API",
                    "reseñas_disponibles": fact, "llamadas_totales": _api_metrics["total"]})


@app.route("/api/v1/vinos")
@require_api_key
def api_v1_vinos():
    """Catálogo de vinos con filtros y paginación (consumido por partners)."""
    try:
        page     = max(1, int(request.args.get("page", 1)))
        per_page = min(100, int(request.args.get("per_page", 20)))
        offset   = (page - 1) * per_page
        cond, params = [], []
        if v := request.args.get("pais"):
            cond.append("dp.nombre = %s"); params.append(v)
        if v := request.args.get("variedad"):
            cond.append("dv.nombre = %s"); params.append(v)
        if v := request.args.get("puntos_min"):
            cond.append("fr.points >= %s"); params.append(int(v))
        where = ("WHERE " + " AND ".join(cond)) if cond else ""
        join = """FROM fact_resenas fr
                  JOIN dim_pais dp ON fr.id_pais=dp.id_pais
                  JOIN dim_variedad dv ON fr.id_variedad=dv.id_variedad
                  JOIN dim_bodega db ON fr.id_bodega=db.id_bodega"""
        total = int(_fetchone(f"SELECT COUNT(*) {join} {where}", tuple(params))[0])
        rows = _fetchall(f"""SELECT fr.id_resena, fr.title, dv.nombre, dp.nombre, db.nombre,
                                    fr.points, fr.price {join} {where}
                             ORDER BY fr.points DESC LIMIT %s OFFSET %s""",
                         tuple(params) + (per_page, offset))
        return jsonify({
            "api_version": "1.0", "page": page, "per_page": per_page, "total": total,
            "data": [{"id": r[0], "titulo": r[1], "variedad": r[2], "pais": r[3],
                      "bodega": r[4], "puntos": r[5], "precio": float(r[6])} for r in rows],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/mercados")
@require_api_key
def api_v1_mercados():
    """Indicadores agregados por mercado (país)."""
    _ch = serving.v1_mercados()
    if _ch is not None:
        return jsonify(_ch)
    try:  # Fallback: vista DBT serving.agg_pais en StarRocks.
        rows = _fetchall("""SELECT pais, total, puntuacion_promedio, precio_promedio
                            FROM agg_pais ORDER BY total DESC LIMIT 50""")
        return jsonify({"api_version": "1.0",
                        "data": [{"mercado": r[0], "resenas": int(r[1]),
                                  "puntuacion_promedio": float(r[2]),
                                  "precio_promedio": float(r[3] or 0)} for r in rows]})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/precios")
@require_api_key
def api_v1_precios():
    """Recomendaciones de precio dinámico por variedad (modelo de IA)."""
    try:
        from etl.ml_models import precios_dinamicos
        return jsonify(precios_dinamicos())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/scorecard")
@require_api_key
def api_v1_scorecard():
    """Resumen ejecutivo del Balanced Scorecard (KPIs principales)."""
    _ch = serving.v1_scorecard()
    if _ch is not None:
        return jsonify(_ch)
    # Fallback: vista DBT serving.agg_bsc_kpis en StarRocks (sin recomputar).
    try:
        row = _fetchone("""SELECT mrr_actual, clientes_activos, churn, uptime
                           FROM agg_bsc_kpis LIMIT 1""")
        if not row:
            return jsonify({"api_version": "1.0", "disponible": False})
        return jsonify({"api_version": "1.0", "disponible": True,
                        "mrr_mensual": round(float(row[0]), 2), "clientes_activos": int(row[1]),
                        "churn_pct": round(float(row[2]), 2), "uptime_pct": round(float(row[3]), 3)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/v1/openapi.json")
def api_v1_openapi():
    """Contrato OpenAPI 3.0 (enfoque Specification-Driven Development)."""
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "VinAnalytics Public API", "version": "1.0.0",
                 "description": "API pública de inteligencia vitivinícola para marketplaces, "
                                "integradores y partners (OE2 · escalabilidad por APIs)."},
        "servers": [{"url": "/api/v1"}],
        "components": {"securitySchemes": {"ApiKeyAuth": {
            "type": "apiKey", "in": "header", "name": "X-API-Key"}}},
        "security": [{"ApiKeyAuth": []}],
        "paths": {
            "/health":    {"get": {"summary": "Estado del servicio", "security": []}},
            "/vinos":     {"get": {"summary": "Catálogo de vinos paginado",
                                   "parameters": [
                                       {"name": "page", "in": "query", "schema": {"type": "integer"}},
                                       {"name": "per_page", "in": "query", "schema": {"type": "integer"}},
                                       {"name": "pais", "in": "query", "schema": {"type": "string"}},
                                       {"name": "variedad", "in": "query", "schema": {"type": "string"}},
                                       {"name": "puntos_min", "in": "query", "schema": {"type": "integer"}}]}},
            "/mercados":  {"get": {"summary": "Indicadores por mercado"}},
            "/precios":   {"get": {"summary": "Precios dinámicos recomendados (IA)"}},
            "/scorecard": {"get": {"summary": "Resumen del Balanced Scorecard"}},
        },
    }
    return jsonify(spec)


@app.route("/api-docs")
def api_docs():
    return render_template("api_docs.html", api_keys=API_KEYS,
                           demo_key="vinapi_demo_2026",
                           rate_limit=_RATE_LIMIT)


# ═════════════════════════════════════════════════════════════════════════════
# RUTAS DE SISTEMA
# ═════════════════════════════════════════════════════════════════════════════

@app.route("/auditoria")
def auditoria():
    from flask import session, redirect, url_for
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    filtros = {
        "usuario": request.args.get("usuario", ""),
        "accion":  request.args.get("accion",  ""),
        "fecha":   request.args.get("fecha",   ""),
    }
    eventos = get_eventos(
        usuario=filtros["usuario"] or None,
        accion=filtros["accion"]   or None,
        fecha=filtros["fecha"]     or None,
    )
    return render_template("auditoria.html", eventos=eventos, filtros=filtros)


@app.route("/usuarios")
def usuarios():
    from flask import session, redirect, url_for
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    return render_template("usuarios.html", usuarios=get_all_users())


@app.route("/usuarios/crear", methods=["POST"])
def usuarios_crear():
    from flask import session, redirect, url_for, flash
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm_password", "")
    rol      = request.form.get("rol", "analista")
    if not username or not password:
        flash("Usuario y contraseña son requeridos.", "error")
    elif password != confirm:
        flash("Las contraseñas no coinciden.", "error")
    elif len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", "error")
    elif username_exists(username):
        flash(f"El usuario '{username}' ya existe.", "error")
    else:
        create_user(username, password, rol)
        registrar_evento(session["username"], session["rol"], "CREAR_USUARIO",
                         f"Usuario creado: {username}", request.remote_addr)
        flash(f"Usuario '{username}' creado correctamente.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/editar/<int:uid>", methods=["POST"])
def usuarios_editar(uid):
    from flask import session, redirect, url_for, flash
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    rol    = request.form.get("rol", "analista")
    activo = "activo" in request.form
    update_user(uid, rol, activo)
    registrar_evento(session["username"], session["rol"], "EDITAR_USUARIO",
                     f"Usuario id={uid} actualizado rol={rol} activo={activo}",
                     request.remote_addr)
    flash("Usuario actualizado.", "success")
    return redirect(url_for("usuarios"))


@app.route("/usuarios/eliminar/<int:uid>", methods=["POST"])
def usuarios_eliminar(uid):
    from flask import session, redirect, url_for, flash
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    if uid == 1:
        flash("No se puede eliminar el usuario administrador principal.", "error")
    else:
        delete_user(uid)
        registrar_evento(session["username"], session["rol"], "ELIMINAR_USUARIO",
                         f"Usuario id={uid} eliminado", request.remote_addr)
        flash("Usuario eliminado.", "success")
    return redirect(url_for("usuarios"))


@app.route("/respaldos")
def respaldos():
    from flask import session, redirect, url_for
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    return render_template("respaldos.html",
                           backups=list_backups(),
                           history=get_recovery_history(),
                           db_status=get_db_status())


@app.route("/respaldos/crear", methods=["POST"])
def respaldos_crear():
    from flask import session, redirect, url_for, flash
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    ok, msg = create_backup("manual")
    flash(f"Respaldo creado: {msg}" if ok else f"Error: {msg}",
          "success" if ok else "error")
    return redirect(url_for("respaldos"))


@app.route("/respaldos/restaurar", methods=["POST"])
def respaldos_restaurar():
    from flask import session, redirect, url_for, flash
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    filename = request.form.get("filename", "")
    ok, msg  = restore_backup(filename)
    flash("Restauración completada." if ok else f"Error: {msg}",
          "success" if ok else "error")
    return redirect(url_for("respaldos"))


@app.route("/respaldos/eliminar", methods=["POST"])
def respaldos_eliminar():
    from flask import session, redirect, url_for, flash
    if session.get("rol") != "admin":
        return redirect(url_for("index"))
    filename = request.form.get("filename", "")
    ok = delete_backup(filename)
    flash("Respaldo eliminado." if ok else "No se pudo eliminar el respaldo.",
          "success" if ok else "error")
    return redirect(url_for("respaldos"))


@app.route("/api/db-status")
def api_db_status():
    return jsonify({"status": get_db_status()})


# ═════════════════════════════════════════════════════════════════════════════
# CU-O08 (OP5) — Cuentas y suscripciones de clientes (capa operacional PocketBase)
# Toda la lógica vive en models_clientes.py; aquí solo el transporte HTTP + auth
# de Administrador + auditoría en StarRocks. No se escribe al DW (RN-606).
# ═════════════════════════════════════════════════════════════════════════════

def _solo_admin():
    """Devuelve None si el actor es admin; si no, una respuesta 403."""
    if session.get("rol") != "admin":
        return jsonify({"status": "error", "message": "Acceso denegado (admin)"}), 403
    return None


def _audit(accion: str, detalle: str):
    try:
        registrar_evento(session.get("username", "sistema"),
                         session.get("rol", "admin"), accion, detalle,
                         request.remote_addr)
    except Exception:
        pass


# ── OP3 · lectura de métricas del dashboard: ClickHouse con fallback StarRocks ──
def _metricas_tema_starrocks(tema: str, filtros: dict | None = None) -> dict:
    """Fallback de lectura (capa DW) cuando ClickHouse no responde. Solo lectura;
    misma semántica que /api/kpis. Las métricas de negocio (ingresos/uso) viven en
    las tablas BSC y se devuelven vacías si aún no fueron proyectadas (sintéticas)."""
    tema = (tema or "").lower()
    try:
        if tema in ("resenas", "reseñas"):
            row = _fetchone("SELECT COUNT(*), ROUND(AVG(CAST(points AS DOUBLE)), 1) "
                            "FROM fact_resenas")
            return {"total_resenas": int(row[0] or 0),
                    "puntuacion_promedio": float(row[1] or 0)} if row else {}
        if tema == "precios":
            row = _fetchone(
                "SELECT ROUND(AVG(CASE WHEN price > 0 THEN CAST(price AS DOUBLE) END), 2), "
                "MAX(CASE WHEN price > 0 THEN price END), "
                "MIN(CASE WHEN price > 0 THEN price END) FROM fact_resenas")
            return {"precio_promedio": float(row[0] or 0),
                    "precio_maximo": float(row[1] or 0),
                    "precio_minimo": float(row[2] or 0)} if row else {}
    except Exception:
        return {}
    return {}


def _leer_metricas_tema(tema: str, filtros: dict | None = None) -> dict:
    """RT-01: lee de ClickHouse vía serving; si no hay datos, cae a StarRocks.
    Devuelve {"fuente": "clickhouse"|"starrocks", "valores": {...}}."""
    ch = serving.metricas_dashboard(tema, filtros)
    if ch is not None:
        return ch
    return {"fuente": "starrocks", "valores": _metricas_tema_starrocks(tema, filtros)}


@app.route("/planes", methods=["GET"])
def planes_list():
    from pb_client import get_client
    try:
        return jsonify({"status": "ok", "planes": get_client().find("planes")})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    import models_clientes as mc
    if request.method == "GET":
        from pb_client import get_client
        try:
            return jsonify({"status": "ok", "clientes": get_client().find("clientes")})
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 502

    denied = _solo_admin()
    if denied:
        return denied
    datos = request.get_json(silent=True) or request.form.to_dict()
    try:
        cli = mc.crear_cliente(datos)
        _audit("ALTA_CLIENTE", f"cliente={cli['id']} {cli.get('razon_social','')}")
        return jsonify({"status": "ok", "cliente": cli}), 201
    except mc.ReglaNegocioError as e:
        return jsonify({"status": "error", "codigo": e.codigo,
                        "message": e.mensaje, "detalle": e.detalle}), 409
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/suscripciones", methods=["POST"])
def suscripciones_crear():
    import models_clientes as mc
    denied = _solo_admin()
    if denied:
        return denied
    d = request.get_json(silent=True) or request.form.to_dict()
    try:
        susc = mc.crear_suscripcion(
            cliente_id=d.get("cliente_id", ""),
            plan_codigo=d.get("plan", ""),
            periodo=d.get("periodo", "mensual"),
            facturacion=d.get("facturacion"),
            monto=d.get("monto"),
            moneda=d.get("moneda", "USD"),
            usuario=session.get("username", "admin"),
        )
        _audit("ALTA_SUSCRIPCION",
               f"susc={susc['id']} cliente={susc['cliente']} plan={susc['plan']} estado={susc['estado']}")
        return jsonify({"status": "ok", "suscripcion": susc}), 201
    except mc.ReglaNegocioError as e:
        return jsonify({"status": "error", "codigo": e.codigo,
                        "message": e.mensaje, "detalle": e.detalle}), 409
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/suscripciones/<sid>/estado", methods=["POST"])
def suscripciones_estado(sid):
    import models_clientes as mc
    denied = _solo_admin()
    if denied:
        return denied
    d = request.get_json(silent=True) or request.form.to_dict()
    try:
        susc = mc.cambiar_estado(sid, d.get("estado", ""),
                                 usuario=session.get("username", "admin"))
        _audit("CAMBIO_ESTADO_SUSCRIPCION", f"susc={sid} -> {susc['estado']}")
        return jsonify({"status": "ok", "suscripcion": susc})
    except mc.ReglaNegocioError as e:
        return jsonify({"status": "error", "codigo": e.codigo,
                        "message": e.mensaje, "detalle": e.detalle}), 409
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/suscripciones/<sid>/plan", methods=["POST"])
def suscripciones_plan(sid):
    import models_clientes as mc
    denied = _solo_admin()
    if denied:
        return denied
    d = request.get_json(silent=True) or request.form.to_dict()
    try:
        susc = mc.cambiar_plan(sid, d.get("plan", ""),
                               usuario=session.get("username", "admin"))
        _audit("CAMBIO_PLAN_SUSCRIPCION", f"susc={sid} -> {susc['plan']}")
        return jsonify({"status": "ok", "suscripcion": susc})
    except mc.ReglaNegocioError as e:
        return jsonify({"status": "error", "codigo": e.codigo,
                        "message": e.mensaje, "detalle": e.detalle}), 409
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/clientes/<cid>/acceso", methods=["GET"])
def clientes_acceso(cid):
    """RF-507/RN-603: plan/estado vigente para autorizar dashboards/API."""
    import models_clientes as mc
    try:
        return jsonify({"status": "ok", "acceso": mc.acceso_vigente(cid)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


# ═════════════════════════════════════════════════════════════════════════════
# OP3 · CU-O05 construir dashboard / CU-O06 publicar a la cuenta del cliente
# Lectura analítica SOLO de ClickHouse (serving) con fallback a StarRocks (RT-01).
# Publicación bloqueada sin sello de calidad vigente (RN-401, regla dura).
# ═════════════════════════════════════════════════════════════════════════════

def _rol_permitido(*roles):
    """None si el rol de la sesión está permitido; si no, respuesta 403."""
    if session.get("rol") not in roles:
        return jsonify({"status": "error",
                        "message": f"Acceso denegado ({'/'.join(roles)})"}), 403
    return None


def _err_dashboard(e):
    """Mapea un DashboardError al código HTTP correcto."""
    import models_dashboards as md
    code = 403 if isinstance(e, md.FugaMultiTenant) else 409
    return jsonify({"status": "error", "codigo": e.codigo,
                    "message": e.mensaje, "detalle": e.detalle}), code


@app.route("/api/dashboards/temas", methods=["GET"])
def dashboards_temas():
    import models_dashboards as md
    return jsonify({"status": "ok", "temas": md.temas()})


@app.route("/dashboards", methods=["GET", "POST"])
def dashboards():
    """GET: lista (filtrable por ?cliente=). POST: construir (CU-O05, analista/admin)."""
    import models_dashboards as md
    if request.method == "GET":
        from pb_client import get_client
        try:
            cliente = request.args.get("cliente")
            flt = {"cliente": cliente} if cliente else {}
            return jsonify({"status": "ok", "dashboards": get_client().find("dashboards", **flt)})
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 502

    denied = _rol_permitido("admin", "analista")  # construir = Analista de datos
    if denied:
        return denied
    d = request.get_json(silent=True) or request.form.to_dict()
    try:
        dash = md.construir_dashboard(
            cliente_id=d.get("cliente", ""), tema=d.get("tema", ""),
            nombre=d.get("nombre"), filtros=d.get("filtros"),
            lectura_fn=_leer_metricas_tema, usuario=session.get("username", "analista"))
        _audit("CONSTRUIR_DASHBOARD",
               f"dash={dash['id']} cliente={dash['cliente']} tema={dash['tema']} "
               f"fuente={dash.get('fuente_lectura')}")
        return jsonify({"status": "ok", "dashboard": dash}), 201
    except md.DashboardError as e:
        return _err_dashboard(e)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/dashboards/<did>/listo", methods=["POST"])
def dashboards_listo(did):
    """RF-303: marca el dashboard LISTO_PARA_PUBLICAR (analista/admin)."""
    import models_dashboards as md
    denied = _rol_permitido("admin", "analista")
    if denied:
        return denied
    try:
        dash = md.marcar_listo(did, usuario=session.get("username", "analista"))
        _audit("DASHBOARD_LISTO", f"dash={did} -> {dash['estado']}")
        return jsonify({"status": "ok", "dashboard": dash})
    except md.DashboardError as e:
        return _err_dashboard(e)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/dashboards/<did>/publicar", methods=["POST"])
def dashboards_publicar(did):
    """CU-O06 (admin): publica con permisos/versión. Bloquea sin calidad (RN-401)."""
    import models_dashboards as md
    denied = _solo_admin()  # autorizar publicación = Administrador
    if denied:
        return denied
    d = request.get_json(silent=True) or request.form.to_dict()
    try:
        pub = md.publicar(did, cuenta_id=d.get("cuenta", ""),
                          permisos=d.get("permisos"),
                          usuario=session.get("username", "admin"))
        _audit("PUBLICAR_DASHBOARD",
               f"dash={did} cuenta={pub['cuenta']} v{pub['version']} sello={pub.get('sello')}")
        return jsonify({"status": "ok", "publicacion": pub}), 201
    except md.CalidadNoVigente as e:
        _audit("PUBLICACION_BLOQUEADA", f"dash={did} motivo={e.mensaje}")
        return _err_dashboard(e)
    except md.DashboardError as e:
        return _err_dashboard(e)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/dashboards/<did>/publicaciones", methods=["GET"])
def dashboards_publicaciones(did):
    """RF-307/RN-405: historial auditable de publicaciones del dashboard."""
    import models_dashboards as md
    try:
        return jsonify({"status": "ok", "publicaciones": md.publicaciones_de(did)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/publicaciones/<pid>/despublicar", methods=["POST"])
def publicaciones_despublicar(pid):
    """RF-308: despublica conservando el historial (admin)."""
    import models_dashboards as md
    denied = _solo_admin()
    if denied:
        return denied
    try:
        pub = md.despublicar(pid, usuario=session.get("username", "admin"))
        _audit("DESPUBLICAR_DASHBOARD", f"pub={pid} -> {pub['estado']}")
        return jsonify({"status": "ok", "publicacion": pub})
    except md.DashboardError as e:
        return _err_dashboard(e)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/calidad/estado", methods=["GET"])
def calidad_estado():
    """Estado del sello de calidad (CU-O04) que gobierna la publicación (RN-401)."""
    import models_dashboards as md
    try:
        return jsonify({"status": "ok", "calidad": md.calidad_vigente()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@app.route("/calidad/sello", methods=["POST"])
def calidad_sello():
    """Registra manualmente un sello de calidad (admin). El gate automático lo
    emite `quality/run_quality.py` tras cada corrida del pipeline."""
    import models_dashboards as md
    denied = _solo_admin()
    if denied:
        return denied
    d = request.get_json(silent=True) or request.form.to_dict()
    try:
        sello = md.registrar_sello(
            suite=d.get("suite", "manual"),
            exito=str(d.get("exito", "true")).lower() in ("1", "true", "si", "sí", "yes"),
            evaluadas=int(d.get("evaluadas", 0) or 0),
            fallidas=int(d.get("fallidas", 0) or 0),
            vigencia_horas=float(d.get("vigencia_horas", 24) or 24))
        _audit("SELLO_CALIDAD", f"sello={sello['id']} suite={sello['suite']} exito={sello['exito']}")
        return jsonify({"status": "ok", "sello": sello}), 201
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
