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
    try:
        row = _fetchone("""
            SELECT
                COUNT(*)                                                        AS total_resenas,
                ROUND(AVG(CAST(points AS DOUBLE)), 1)                           AS puntuacion_promedio,
                ROUND(AVG(CASE WHEN price > 0 THEN CAST(price AS DOUBLE) END), 2) AS precio_promedio,
                MAX(CASE WHEN price > 0 THEN price END)                         AS precio_maximo,
                MIN(CASE WHEN price > 0 THEN price END)                         AS precio_minimo
            FROM fact_resenas
        """)
        total   = int(row[0] or 0)
        avg_pts = float(row[1] or 0)
        avg_prc = float(row[2] or 0)
        max_prc = float(row[3] or 0)
        min_prc = float(row[4] or 0)

        n_paises     = int((_fetchone("SELECT COUNT(*) FROM dim_pais")      or [0])[0])
        n_variedades = int((_fetchone("SELECT COUNT(*) FROM dim_variedad")  or [0])[0])
        n_bodegas    = int((_fetchone("SELECT COUNT(*) FROM dim_bodega")    or [0])[0])

        return jsonify({
            "total_resenas":       total,
            "puntuacion_promedio": avg_pts,
            "precio_promedio":     avg_prc,
            "precio_maximo":       max_prc,
            "precio_minimo":       min_prc,
            "total_paises":        n_paises,
            "total_variedades":    n_variedades,
            "total_bodegas":       n_bodegas,
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
    try:
        rows = _fetchall("""
            SELECT dp.nombre, ROUND(AVG(CAST(fr.points AS DOUBLE)),1) AS avg_pts, COUNT(*) AS total
            FROM fact_resenas fr JOIN dim_pais dp ON fr.id_pais = dp.id_pais
            WHERE dp.nombre != 'Desconocido'
            GROUP BY dp.nombre ORDER BY avg_pts DESC LIMIT 15
        """)
        return jsonify([{"pais": r[0], "puntuacion": float(r[1]), "total": int(r[2])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/variedades")
def api_graficas_variedades():
    try:
        rows = _fetchall("""
            SELECT dv.nombre, ROUND(AVG(CAST(fr.price AS DOUBLE)),2) AS avg_price, COUNT(*) AS total
            FROM fact_resenas fr JOIN dim_variedad dv ON fr.id_variedad = dv.id_variedad
            WHERE fr.price > 0 AND dv.nombre != 'Desconocido'
            GROUP BY dv.nombre ORDER BY avg_price DESC LIMIT 12
        """)
        return jsonify([{"variedad": r[0], "precio_promedio": float(r[1]), "total": int(r[2])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/puntuacion")
def api_graficas_puntuacion():
    try:
        rows = _fetchall("""
            SELECT points, COUNT(*) AS total
            FROM fact_resenas
            GROUP BY points ORDER BY points
        """)
        return jsonify([{"puntuacion": int(r[0]), "total": int(r[1])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/bodegas")
def api_graficas_bodegas():
    try:
        rows = _fetchall("""
            SELECT db.nombre, ROUND(AVG(CAST(fr.points AS DOUBLE)),1) AS avg_pts, COUNT(*) AS total
            FROM fact_resenas fr JOIN dim_bodega db ON fr.id_bodega = db.id_bodega
            WHERE db.nombre != 'Desconocido'
            GROUP BY db.nombre HAVING COUNT(*) >= 10
            ORDER BY avg_pts DESC LIMIT 10
        """)
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
    try:
        paises = [p.strip() for p in request.args.get("paises", "").split(",") if p.strip()][:4]
        if not paises:
            return jsonify([])

        result = []
        for pais in paises:
            row = _fetchone("""
                SELECT COUNT(*) AS total,
                       ROUND(AVG(CAST(fr.points AS DOUBLE)), 1) AS avg_pts,
                       ROUND(AVG(CASE WHEN fr.price > 0 THEN CAST(fr.price AS DOUBLE) END), 2) AS avg_price,
                       COUNT(DISTINCT fr.id_variedad) AS variedades
                FROM fact_resenas fr
                JOIN dim_pais dp ON fr.id_pais = dp.id_pais
                WHERE dp.nombre = %s
            """, (pais,))
            if row:
                result.append({
                    "pais":       pais,
                    "total":      int(row[0] or 0),
                    "puntuacion": float(row[1] or 0),
                    "precio":     float(row[2] or 0),
                    "variedades": int(row[3] or 0),
                })

        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/graficas/tendencias-precio")
def api_graficas_tendencias_precio():
    """Evolución de precio promedio por año extraído del título. Incluye proyección 2 períodos."""
    try:
        variedad = request.args.get("variedad", "").strip()

        if variedad:
            rows = _fetchall("""
                SELECT REGEXP_EXTRACT(fr.title, '(2[0-9]{3})', 1) AS yr,
                       ROUND(AVG(CAST(fr.price AS DOUBLE)), 2) AS avg_price,
                       COUNT(*) AS total
                FROM fact_resenas fr
                JOIN dim_variedad dv ON fr.id_variedad = dv.id_variedad
                WHERE dv.nombre = %s AND fr.price > 0
                  AND REGEXP_EXTRACT(fr.title, '(2[0-9]{3})', 1) != ''
                GROUP BY yr
                ORDER BY yr
            """, (variedad,))
        else:
            rows = _fetchall("""
                SELECT REGEXP_EXTRACT(title, '(2[0-9]{3})', 1) AS yr,
                       ROUND(AVG(CAST(price AS DOUBLE)), 2) AS avg_price,
                       COUNT(*) AS total
                FROM fact_resenas
                WHERE price > 0
                  AND REGEXP_EXTRACT(title, '(2[0-9]{3})', 1) != ''
                GROUP BY yr
                ORDER BY yr
            """)

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
    try:
        rows = _fetchall("""
            SELECT dp.nombre, COUNT(*) AS n
            FROM fact_resenas fr JOIN dim_pais dp ON fr.id_pais = dp.id_pais
            WHERE dp.nombre != 'Desconocido'
            GROUP BY dp.nombre ORDER BY n DESC
        """)
        return jsonify([{"nombre": r[0], "total": int(r[1])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/variedades")
def api_variedades():
    """Lista las principales variedades ordenadas por cantidad de reseñas."""
    try:
        rows = _fetchall("""
            SELECT dv.nombre, COUNT(*) AS n
            FROM fact_resenas fr JOIN dim_variedad dv ON fr.id_variedad = dv.id_variedad
            WHERE dv.nombre != 'Desconocido'
            GROUP BY dv.nombre ORDER BY n DESC LIMIT 60
        """)
        return jsonify([{"nombre": r[0], "total": int(r[1])} for r in rows])
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/browse")
def api_browse():
    try:
        paises     = _fetchall("SELECT dp.nombre, COUNT(*) AS n FROM fact_resenas fr JOIN dim_pais dp ON fr.id_pais=dp.id_pais GROUP BY dp.nombre ORDER BY n DESC LIMIT 6")
        variedades = _fetchall("SELECT dv.nombre, COUNT(*) AS n FROM fact_resenas fr JOIN dim_variedad dv ON fr.id_variedad=dv.id_variedad GROUP BY dv.nombre ORDER BY n DESC LIMIT 6")
        bodegas    = _fetchall("SELECT db.nombre, COUNT(*) AS n FROM fact_resenas fr JOIN dim_bodega db ON fr.id_bodega=db.id_bodega WHERE db.nombre!='Desconocido' GROUP BY db.nombre ORDER BY n DESC LIMIT 6")
        regiones   = _fetchall("SELECT dr.nombre, COUNT(*) AS n FROM fact_resenas fr JOIN dim_region dr ON fr.id_region=dr.id_region WHERE dr.nombre!='Desconocido' GROUP BY dr.nombre ORDER BY n DESC LIMIT 6")
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
# Alimentado por las tablas Fact-Dim de negocio (db/bsc_setup.py).
# ═════════════════════════════════════════════════════════════════════════════

def _bsc_periodos():
    """Devuelve (último, mismo_mes_año_anterior, primero) según dim_tiempo."""
    row = _fetchone("SELECT MAX(id_tiempo), MIN(id_tiempo) FROM dim_tiempo")
    if not row or row[0] is None:
        return None, None, None
    latest = int(row[0])
    return latest, latest - 100, int(row[1])


def _ult_periodos(n: int) -> list[int]:
    rows = _fetchall(f"SELECT id_tiempo FROM dim_tiempo ORDER BY id_tiempo DESC LIMIT {n}")
    return [int(r[0]) for r in rows]


def _kpi(clave, etiqueta, valor, meta, unidad, mejor, sub=""):
    """Construye una tarjeta de KPI con semáforo (verde/amarillo/rojo)."""
    valor = round(float(valor or 0), 2)
    if mejor == "mayor":
        estado = "verde" if valor >= meta else ("amarillo" if valor >= meta * 0.9 else "rojo")
    else:  # menor es mejor
        estado = "verde" if valor <= meta else ("amarillo" if valor <= meta * 1.1 else "rojo")
    return {"clave": clave, "etiqueta": etiqueta, "valor": valor, "meta": meta,
            "unidad": unidad, "mejor": mejor, "estado": estado, "sub": sub}


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
    try:
        latest, prev_year, first = _bsc_periodos()
        if latest is None:
            return jsonify({"disponible": False})

        def val(sql, params=()):
            r = _fetchone(sql, params)
            return float(r[0]) if r and r[0] is not None else 0.0

        # ── Financiera ───────────────────────────────────────────────────────
        mrr_now  = val("SELECT SUM(mrr) FROM fact_suscripcion WHERE id_tiempo=%s AND es_churn=0", (latest,))
        mrr_prev = val("SELECT SUM(mrr) FROM fact_suscripcion WHERE id_tiempo=%s AND es_churn=0", (prev_year,))
        mrr_growth = ((mrr_now / mrr_prev) - 1) * 100 if mrr_prev else 0
        api_now  = val("SELECT SUM(ingreso_api) FROM fact_consumo_api WHERE id_tiempo=%s", (latest,))
        api_share = api_now / (mrr_now + api_now) * 100 if (mrr_now + api_now) else 0
        cac_now  = val("SELECT AVG(cac) FROM fact_conversion WHERE id_tiempo=%s AND conversiones>0", (latest,))
        ltv_now  = val("SELECT AVG(ltv) FROM fact_retencion WHERE id_tiempo=%s AND activo=1", (latest,))
        ltv_cac  = ltv_now / cac_now if cac_now else 0
        cloud    = val("SELECT SUM(costo_cloud) FROM fact_disponibilidad WHERE id_tiempo=%s", (latest,))
        activos  = val("SELECT SUM(activo) FROM fact_retencion WHERE id_tiempo=%s", (latest,)) or 1
        cloud_cli = cloud / activos

        # ── Cliente ──────────────────────────────────────────────────────────
        cv = _fetchone("SELECT SUM(conversiones), SUM(leads) FROM fact_conversion WHERE id_tiempo=%s", (latest,))
        conv = (float(cv[0]) / float(cv[1]) * 100) if cv and cv[1] else 0
        rt = _fetchone("SELECT SUM(cancelacion), SUM(activo) FROM fact_retencion WHERE id_tiempo=%s", (latest,))
        churn = (float(rt[0]) / (float(rt[1]) + float(rt[0])) * 100) if rt and (rt[0] or rt[1]) else 0
        npsr = _fetchone("""SELECT SUM(CASE WHEN nps_score>=9 THEN 1 ELSE 0 END),
                                   SUM(CASE WHEN nps_score BETWEEN 0 AND 6 THEN 1 ELSE 0 END),
                                   SUM(CASE WHEN nps_score>=0 THEN 1 ELSE 0 END)
                            FROM fact_uso_plataforma WHERE id_tiempo=%s""", (latest,))
        nps = ((float(npsr[0]) - float(npsr[1])) / float(npsr[2]) * 100) if npsr and npsr[2] else 0
        adr = _fetchone("SELECT SUM(usuarios_activos), SUM(usuarios_totales) FROM fact_uso_plataforma WHERE id_tiempo=%s", (latest,))
        adopcion = (float(adr[0]) / float(adr[1]) * 100) if adr and adr[1] else 0
        u3 = _ult_periodos(3)
        nuevos_trim = val(f"SELECT SUM(es_nuevo) FROM fact_suscripcion WHERE id_tiempo IN ({','.join(map(str,u3))})") if u3 else 0

        # ── Procesos internos ────────────────────────────────────────────────
        dp = _fetchone("SELECT AVG(uptime), AVG(time_to_market_dias), AVG(latencia_ms) FROM fact_disponibilidad WHERE id_tiempo=%s", (latest,))
        uptime = float(dp[0]) if dp and dp[0] is not None else 0
        ttm    = float(dp[1]) if dp and dp[1] is not None else 0
        lat    = float(dp[2]) if dp and dp[2] is not None else 0
        cq = _fetchone("SELECT SUM(CASE WHEN points BETWEEN 80 AND 100 THEN 1 ELSE 0 END), COUNT(*) FROM fact_resenas")
        calidad = (float(cq[0]) / float(cq[1]) * 100) if cq and cq[1] else 100.0

        # ── Aprendizaje y crecimiento ────────────────────────────────────────
        ap = _fetchone("""SELECT horas_capacitacion, decisiones_data_driven,
                                 tecnologias_adoptadas, rotacion_personal, modelos_ml_produccion
                          FROM fact_aprendizaje WHERE id_tiempo=%s""", (latest,))
        horas = float(ap[0]) if ap else 0
        ddd   = float(ap[1]) if ap else 0
        tecno = float(ap[2]) if ap else 0
        rota  = float(ap[3]) if ap else 0
        mlmod = float(ap[4]) if ap else 0

        per = _fetchone("SELECT periodo FROM dim_tiempo WHERE id_tiempo=%s", (latest,))
        periodo = per[0] if per else str(latest)

        return jsonify({
            "disponible": True,
            "periodo": periodo,
            "clientes_activos": int(activos),
            "mrr_actual": round(mrr_now, 2),
            "perspectivas": {
                "financiera": [
                    _kpi("mrr_growth", "Crecimiento de MRR", mrr_growth, 30, "%", "mayor", f"MRR ${mrr_now:,.0f}/mes"),
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
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/bsc/series")
def api_bsc_series():
    """Series temporales y rankings para los casos CU-E02 … CU-E06."""
    try:
        latest, _prev, _first = _bsc_periodos()
        if latest is None:
            return jsonify({"disponible": False})

        def pares(sql, params=()):
            return [[r[0], round(float(r[1] or 0), 2)] for r in _fetchall(sql, params)]

        T = "JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo"

        financiera = {
            "mrr": pares(f"SELECT t.periodo, SUM(f.mrr) FROM fact_suscripcion f {T} WHERE f.es_churn=0 GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "api": pares(f"SELECT t.periodo, SUM(f.ingreso_api) FROM fact_consumo_api f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "cac": pares(f"SELECT t.periodo, AVG(f.cac) FROM fact_conversion f {T} WHERE f.conversiones>0 GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "por_plan": pares("SELECT p.nombre, SUM(f.mrr) FROM fact_suscripcion f JOIN dim_plan p ON f.id_plan=p.id_plan WHERE f.id_tiempo=%s AND f.es_churn=0 GROUP BY p.nombre ORDER BY 2 DESC", (latest,)),
        }
        cliente = {
            "nuevos_mercado": pares("SELECT m.pais, SUM(f.es_nuevo) FROM fact_suscripcion f JOIN dim_cliente c ON f.id_cliente=c.id_cliente JOIN dim_mercado m ON c.id_mercado=m.id_mercado GROUP BY m.pais ORDER BY 2 DESC LIMIT 12"),
            "conversion": pares(f"SELECT t.periodo, SUM(f.conversiones)*100.0/SUM(f.leads) FROM fact_conversion f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "churn": pares(f"SELECT t.periodo, SUM(f.cancelacion)*100.0/(SUM(f.activo)+SUM(f.cancelacion)) FROM fact_retencion f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "nps": pares(f"SELECT t.periodo, (SUM(CASE WHEN f.nps_score>=9 THEN 1 ELSE 0 END)-SUM(CASE WHEN f.nps_score BETWEEN 0 AND 6 THEN 1 ELSE 0 END))*100.0/SUM(CASE WHEN f.nps_score>=0 THEN 1 ELSE 0 END) FROM fact_uso_plataforma f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
        }
        emb = _fetchone("SELECT SUM(leads), SUM(oportunidades), SUM(conversiones) FROM fact_conversion WHERE id_tiempo=%s", (latest,))
        cliente["embudo"] = [int(emb[0] or 0), int(emb[1] or 0), int(emb[2] or 0)] if emb else [0, 0, 0]

        procesos = {
            "uptime": pares(f"SELECT t.periodo, AVG(f.uptime) FROM fact_disponibilidad f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "ttm": pares(f"SELECT t.periodo, AVG(f.time_to_market_dias) FROM fact_disponibilidad f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "latencia_region": pares("SELECT m.region_geo, AVG(f.latencia_ms) FROM fact_disponibilidad f JOIN dim_mercado m ON f.id_mercado=m.id_mercado WHERE f.id_tiempo=%s GROUP BY m.region_geo ORDER BY 2 DESC", (latest,)),
            "incidentes": pares(f"SELECT t.periodo, SUM(f.incidentes) FROM fact_disponibilidad f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
        }
        ecosistema = {
            "ingresos_partner": pares("SELECT p.nombre, SUM(f.ingreso_api) FROM fact_consumo_api f JOIN dim_partner_api p ON f.id_partner=p.id_partner GROUP BY p.nombre ORDER BY 2 DESC"),
            "llamadas": pares(f"SELECT t.periodo, SUM(f.llamadas) FROM fact_consumo_api f {T} GROUP BY t.periodo, t.id_tiempo ORDER BY t.id_tiempo"),
            "conexiones_partner": pares("SELECT p.nombre, MAX(f.conexiones_activas) FROM fact_integracion_partner f JOIN dim_partner_api p ON f.id_partner=p.id_partner WHERE f.id_tiempo=%s GROUP BY p.nombre ORDER BY 2 DESC", (latest,)),
        }

        return jsonify({
            "disponible": True,
            "financiera": financiera,
            "cliente": cliente,
            "procesos": procesos,
            "ecosistema": ecosistema,
        })
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
    try:
        rows = _fetchall("""SELECT dp.nombre, COUNT(*),
                                   ROUND(AVG(CAST(fr.points AS DOUBLE)),1),
                                   ROUND(AVG(CASE WHEN fr.price>0 THEN CAST(fr.price AS DOUBLE) END),2)
                            FROM fact_resenas fr JOIN dim_pais dp ON fr.id_pais=dp.id_pais
                            WHERE dp.nombre!='Desconocido'
                            GROUP BY dp.nombre ORDER BY COUNT(*) DESC LIMIT 50""")
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
    try:
        latest, prev_year, _ = _bsc_periodos()
        if latest is None:
            return jsonify({"api_version": "1.0", "disponible": False})

        def val(sql, p=()):
            r = _fetchone(sql, p)
            return float(r[0]) if r and r[0] is not None else 0.0

        mrr  = val("SELECT SUM(mrr) FROM fact_suscripcion WHERE id_tiempo=%s AND es_churn=0", (latest,))
        act  = val("SELECT SUM(activo) FROM fact_retencion WHERE id_tiempo=%s", (latest,))
        rt   = _fetchone("SELECT SUM(cancelacion),SUM(activo) FROM fact_retencion WHERE id_tiempo=%s", (latest,))
        churn = (float(rt[0]) / (float(rt[1]) + float(rt[0])) * 100) if rt and (rt[0] or rt[1]) else 0
        up   = val("SELECT AVG(uptime) FROM fact_disponibilidad WHERE id_tiempo=%s", (latest,))
        return jsonify({"api_version": "1.0", "disponible": True,
                        "mrr_mensual": round(mrr, 2), "clientes_activos": int(act),
                        "churn_pct": round(churn, 2), "uptime_pct": round(up, 3)})
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

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
