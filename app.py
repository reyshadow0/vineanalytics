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

        n_paises    = int((_fetchone("SELECT COUNT(*) FROM dim_pais")   or [0])[0])
        n_variedades = int((_fetchone("SELECT COUNT(*) FROM dim_variedad") or [0])[0])

        return jsonify({
            "total_resenas":       total,
            "puntuacion_promedio": avg_pts,
            "precio_promedio":     avg_prc,
            "precio_maximo":       max_prc,
            "precio_minimo":       min_prc,
            "total_paises":        n_paises,
            "total_variedades":    n_variedades,
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
