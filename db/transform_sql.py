"""
ELT -- Transformaciones SQL dentro de MonetDB.

Lee de staging_interacciones (datos crudos en VARCHAR) y puebla:
  - dim_categoria, dim_marca, dim_canal, dim_dispositivo, dim_region, dim_trafico
  - dim_tiempo  (extrae anio, mes, dia, hora con EXTRACT)
  - fact_interacciones  (JOIN con todas las dimensiones)

Sintaxis MonetDB:
  - EXTRACT(YEAR FROM ts), EXTRACT(MONTH FROM ts), etc. -- no YEAR()/MONTH()
  - EXTRACT(DOW FROM ts)  -> 0=domingo, 1=lunes ... 6=sabado
  - CAST(... AS TIMESTAMP) para parsear strings ISO
"""

import sys
from pathlib import Path
import pymonetdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MONETDB_HOST, MONETDB_PORT, MONETDB_DB, MONETDB_USER, MONETDB_PASS

# Expresion para parsear timestamp_raw VARCHAR a TIMESTAMP en MonetDB.
# Maneja: "2026-01-08T02:34:40Z" --> "2026-01-08 02:34:40" --> TIMESTAMP
_PARSE_TS = (
    "CAST(REPLACE(SUBSTRING(TRIM({col}), 1, 19), 'T', ' ') AS TIMESTAMP)"
)


def _connect():
    return pymonetdb.connect(
        hostname=MONETDB_HOST,
        port=MONETDB_PORT,
        database=MONETDB_DB,
        username=MONETDB_USER,
        password=MONETDB_PASS,
        autocommit=False,
    )


def _exec_and_count(cur, conn, sql: str, count_sql: str, label: str) -> int:
    """Ejecuta INSERT y mide el resultado con SELECT COUNT para evitar el rowcount=0 de pymonetdb."""
    cur.execute(sql)
    conn.commit()
    cur.execute(count_sql)
    n = int(cur.fetchone()[0])
    print(f"  {label:25s}  {n:>7,} filas en tabla")
    return n


def transform() -> dict[str, int]:
    print("\nConectando a MonetDB para transformaciones SQL ...")
    conn = _connect()
    cur = conn.cursor()
    counts: dict[str, int] = {}

    print("\nPoblando dimensiones desde staging_interacciones:")

    # ── Dimensiones simples ────────────────────────────────────────────────────
    simple_dims = [
        ("dim_categoria",   "id_categoria",   "category"),
        ("dim_marca",       "id_marca",        "brand"),
        ("dim_canal",       "id_canal",        "channel"),
        ("dim_dispositivo", "id_dispositivo",  "device"),
        ("dim_region",      "id_region",       "region"),
        ("dim_trafico",     "id_trafico",      "traffic_source"),
    ]

    for table, id_col, src_col in simple_dims:
        insert_sql = f"""
            INSERT INTO {table} (nombre)
            SELECT DISTINCT TRIM(si.{src_col})
            FROM staging_interacciones si
            WHERE si.{src_col} IS NOT NULL
              AND TRIM(si.{src_col}) <> ''
              AND TRIM(si.{src_col}) NOT IN (SELECT nombre FROM {table})
        """
        counts[table] = _exec_and_count(
            cur, conn, insert_sql,
            f"SELECT COUNT(*) FROM {table}",
            table,
        )

    # ── dim_tiempo ─────────────────────────────────────────────────────────────
    # Usamos subquery para parsear el timestamp una sola vez y evitar repeticion.
    # EXTRACT(DOW FROM ts): 0=domingo,1=lunes,...,6=sabado
    # MOD(DOW - 1 + 7, 7) convierte a 0=lunes (mismo que pandas dayofweek)
    ts_raw = _PARSE_TS.format(col="timestamp_raw")
    insert_tiempo = f"""
        INSERT INTO dim_tiempo (fecha, anio, mes, dia, hora, dia_semana)
        SELECT DISTINCT
            CAST(ts AS DATE),
            CAST(EXTRACT(YEAR  FROM ts) AS INT),
            CAST(EXTRACT(MONTH FROM ts) AS INT),
            CAST(EXTRACT(DAY   FROM ts) AS INT),
            CAST(EXTRACT(HOUR  FROM ts) AS INT),
            CAST(MOD(CAST(EXTRACT(DOW FROM ts) AS INT) - 1 + 7, 7) AS INT)
        FROM (
            SELECT {ts_raw} AS ts
            FROM staging_interacciones
            WHERE timestamp_raw IS NOT NULL
              AND TRIM(timestamp_raw) <> ''
        ) t
        WHERE NOT EXISTS (
            SELECT 1 FROM dim_tiempo dt
            WHERE dt.fecha = CAST(ts AS DATE)
              AND dt.hora  = CAST(EXTRACT(HOUR FROM ts) AS INT)
        )
    """
    counts["dim_tiempo"] = _exec_and_count(
        cur, conn, insert_tiempo,
        "SELECT COUNT(*) FROM dim_tiempo",
        "dim_tiempo",
    )

    # ── fact_interacciones ─────────────────────────────────────────────────────
    print("\nPoblando fact_interacciones ...")
    ts_si = _PARSE_TS.format(col="si.timestamp_raw")

    insert_fact = f"""
        INSERT INTO fact_interacciones (
            session_id, user_id, user_action, price,
            is_conversion, drop_off_flag, session_length,
            interaction_count, time_spent_sec,
            id_categoria, id_marca, id_canal,
            id_dispositivo, id_region, id_trafico, id_tiempo
        )
        SELECT
            si.session_id,
            si.user_id,
            si.user_action,
            CAST(CASE
                WHEN si.price IS NULL OR TRIM(si.price) = '' THEN '0'
                ELSE TRIM(si.price)
            END AS DECIMAL(10,2)),
            CASE WHEN LOWER(TRIM(si.is_conversion))  IN ('1','true','yes') THEN TRUE  ELSE FALSE END,
            CASE WHEN LOWER(TRIM(si.drop_off_flag))  IN ('1','true','yes') THEN TRUE  ELSE FALSE END,
            CAST(CASE WHEN si.session_length    IS NULL OR TRIM(si.session_length)    = '' THEN '0' ELSE TRIM(si.session_length)    END AS INT),
            CAST(CASE WHEN si.interaction_count IS NULL OR TRIM(si.interaction_count) = '' THEN '0' ELSE TRIM(si.interaction_count) END AS INT),
            CAST(CASE WHEN si.time_spent_sec    IS NULL OR TRIM(si.time_spent_sec)    = '' THEN '0' ELSE TRIM(si.time_spent_sec)    END AS INT),
            dc.id_categoria,
            dm.id_marca,
            dca.id_canal,
            dd.id_dispositivo,
            dr.id_region,
            dtr.id_trafico,
            dt.id_tiempo
        FROM staging_interacciones si
        JOIN dim_categoria   dc  ON dc.nombre  = TRIM(si.category)
        JOIN dim_marca       dm  ON dm.nombre  = TRIM(si.brand)
        JOIN dim_canal       dca ON dca.nombre = TRIM(si.channel)
        JOIN dim_dispositivo dd  ON dd.nombre  = TRIM(si.device)
        JOIN dim_region      dr  ON dr.nombre  = TRIM(si.region)
        JOIN dim_trafico     dtr ON dtr.nombre = TRIM(si.traffic_source)
        JOIN dim_tiempo      dt
            ON dt.fecha = CAST({ts_si} AS DATE)
           AND dt.hora  = CAST(EXTRACT(HOUR FROM {ts_si}) AS INT)
        WHERE si.timestamp_raw IS NOT NULL
          AND TRIM(si.timestamp_raw) <> ''
    """
    counts["fact_interacciones"] = _exec_and_count(
        cur, conn, insert_fact,
        "SELECT COUNT(*) FROM fact_interacciones",
        "fact_interacciones",
    )

    cur.close()
    conn.close()

    print("\n" + "=" * 50)
    print("RESUMEN DE TRANSFORMACION SQL")
    print("=" * 50)
    for tbl, n in counts.items():
        print(f"  {tbl:25s}  {n:>7,} filas")
    print("=" * 50)

    return counts


if __name__ == "__main__":
    transform()
