"""
Crea el modelo estrella en MonetDB.
Idempotente: intenta CREATE TABLE IF NOT EXISTS; si la versión de MonetDB
no lo soporta, captura el error "already exists" y continúa.
Las tablas se crean en orden (dimensiones → hechos) para respetar las FK.

Notas de compatibilidad MonetDB:
  - Usa INT AUTO_INCREMENT (no SERIAL, que no está soportado).
  - PRIMARY KEY se declara como constraint de tabla, no inline.
  - REFERENCES se omite porque MonetDB no las aplica; la integridad
    referencial la garantiza el código Python del loader.
"""

import sys
from pathlib import Path
import pymonetdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MONETDB_HOST, MONETDB_PORT, MONETDB_DB, MONETDB_USER, MONETDB_PASS

TABLES: list[tuple[str, str]] = [
    ("staging_interacciones", """
        CREATE TABLE IF NOT EXISTS staging_interacciones (
            session_id        VARCHAR(255),
            user_id           VARCHAR(255),
            user_action       VARCHAR(255),
            category          VARCHAR(255),
            brand             VARCHAR(255),
            price             VARCHAR(50),
            timestamp_raw     VARCHAR(255),
            channel           VARCHAR(255),
            device            VARCHAR(255),
            region            VARCHAR(255),
            traffic_source    VARCHAR(255),
            is_conversion     VARCHAR(255),
            drop_off_flag     VARCHAR(255),
            session_length    VARCHAR(255),
            interaction_count VARCHAR(255),
            time_spent_sec    VARCHAR(255)
        )
    """),
    ("dim_categoria", """
        CREATE TABLE IF NOT EXISTS dim_categoria (
            id_categoria INT         AUTO_INCREMENT NOT NULL,
            nombre       VARCHAR(100) NOT NULL,
            CONSTRAINT pk_dim_categoria PRIMARY KEY (id_categoria)
        )
    """),
    ("dim_marca", """
        CREATE TABLE IF NOT EXISTS dim_marca (
            id_marca INT         AUTO_INCREMENT NOT NULL,
            nombre   VARCHAR(100) NOT NULL,
            CONSTRAINT pk_dim_marca PRIMARY KEY (id_marca)
        )
    """),
    ("dim_canal", """
        CREATE TABLE IF NOT EXISTS dim_canal (
            id_canal INT        AUTO_INCREMENT NOT NULL,
            nombre   VARCHAR(50) NOT NULL,
            CONSTRAINT pk_dim_canal PRIMARY KEY (id_canal)
        )
    """),
    ("dim_dispositivo", """
        CREATE TABLE IF NOT EXISTS dim_dispositivo (
            id_dispositivo INT        AUTO_INCREMENT NOT NULL,
            nombre         VARCHAR(50) NOT NULL,
            CONSTRAINT pk_dim_dispositivo PRIMARY KEY (id_dispositivo)
        )
    """),
    ("dim_region", """
        CREATE TABLE IF NOT EXISTS dim_region (
            id_region INT         AUTO_INCREMENT NOT NULL,
            nombre    VARCHAR(100) NOT NULL,
            CONSTRAINT pk_dim_region PRIMARY KEY (id_region)
        )
    """),
    ("dim_trafico", """
        CREATE TABLE IF NOT EXISTS dim_trafico (
            id_trafico INT         AUTO_INCREMENT NOT NULL,
            nombre     VARCHAR(100) NOT NULL,
            CONSTRAINT pk_dim_trafico PRIMARY KEY (id_trafico)
        )
    """),
    ("dim_tiempo", """
        CREATE TABLE IF NOT EXISTS dim_tiempo (
            id_tiempo  INT  AUTO_INCREMENT NOT NULL,
            fecha      DATE NOT NULL,
            anio       INT  NOT NULL,
            mes        INT  NOT NULL,
            dia        INT  NOT NULL,
            hora       INT  NOT NULL,
            dia_semana INT  NOT NULL,
            CONSTRAINT pk_dim_tiempo PRIMARY KEY (id_tiempo)
        )
    """),
    ("fact_interacciones", """
        CREATE TABLE IF NOT EXISTS fact_interacciones (
            id_interaccion    INT           AUTO_INCREMENT NOT NULL,
            session_id        VARCHAR(100)  NOT NULL,
            user_id           VARCHAR(100)  NOT NULL,
            user_action       VARCHAR(50)   NOT NULL,
            price             DECIMAL(10,2) NOT NULL,
            is_conversion     BOOLEAN       NOT NULL DEFAULT FALSE,
            drop_off_flag     BOOLEAN       NOT NULL DEFAULT FALSE,
            session_length    INT           NOT NULL DEFAULT 0,
            interaction_count INT           NOT NULL DEFAULT 0,
            time_spent_sec    INT           NOT NULL DEFAULT 0,
            id_categoria      INT,
            id_marca          INT,
            id_canal          INT,
            id_dispositivo    INT,
            id_region         INT,
            id_trafico        INT,
            id_tiempo         INT,
            CONSTRAINT pk_fact_interacciones PRIMARY KEY (id_interaccion)
        )
    """),
]


def _create_table(cur, conn, name: str, ddl: str) -> str:
    """Ejecuta el DDL y devuelve 'creada' o 'ya existe'."""
    try:
        cur.execute(ddl.strip())
        conn.commit()
        return "creada"
    except pymonetdb.exceptions.OperationalError as exc:
        msg = str(exc).lower()
        if "already exists" in msg or "table already exists" in msg:
            conn.rollback()
            return "ya existe"
        conn.rollback()
        raise


def setup() -> list[str]:
    conn = pymonetdb.connect(
        hostname=MONETDB_HOST,
        port=MONETDB_PORT,
        database=MONETDB_DB,
        username=MONETDB_USER,
        password=MONETDB_PASS,
        autocommit=False,
    )
    cur = conn.cursor()

    created: list[str] = []
    skipped: list[str] = []

    for name, ddl in TABLES:
        result = _create_table(cur, conn, name, ddl)
        if result == "creada":
            created.append(name)
            print(f"  [OK]    {name}")
        else:
            skipped.append(name)
            print(f"  [SKIP]  {name}  (ya existe)")

    cur.close()
    conn.close()

    print("\nTablas creadas exitosamente")
    print("-" * 40)
    for name, _ in TABLES:
        estado = "nueva" if name in created else "existente"
        print(f"  {name:30s}  [{estado}]")
    print(f"\nTotal: {len(created)} nueva(s), {len(skipped)} existente(s).")

    return created


if __name__ == "__main__":
    setup()
