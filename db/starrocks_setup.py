"""
Crea el modelo estrella en StarRocks.
Idempotente: usa CREATE TABLE IF NOT EXISTS.
Tablas creadas en orden (dimensiones → hechos).

Notas StarRocks:
  - Dimensiones: PRIMARY KEY model (soporta UPSERT/updates).
  - Fact table: DUPLICATE KEY model (alto rendimiento analítico).
  - Cada tabla requiere DISTRIBUTED BY HASH(...) y PROPERTIES replication_num.
  - Conecta vía protocolo MySQL (mysql-connector-python, puerto 9030).
"""

import sys
from pathlib import Path
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS,
)

TABLES: list[tuple[str, str]] = [
    ("usuarios_sistema", """
        CREATE TABLE IF NOT EXISTS usuarios_sistema (
            id            INT          NOT NULL,
            username      VARCHAR(50)  NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            rol           VARCHAR(20)  NOT NULL,
            activo        BOOLEAN      NOT NULL,
            created_at    DATETIME
        )
        ENGINE = OLAP
        PRIMARY KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("auditoria", """
        CREATE TABLE IF NOT EXISTS auditoria (
            id      INT          NOT NULL,
            usuario VARCHAR(50)  NOT NULL,
            rol     VARCHAR(20)  NOT NULL,
            accion  VARCHAR(100) NOT NULL,
            detalle VARCHAR(1000),
            ip      VARCHAR(50),
            fecha   DATETIME
        )
        ENGINE = OLAP
        DUPLICATE KEY(id)
        DISTRIBUTED BY HASH(id) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_pais", """
        CREATE TABLE IF NOT EXISTS dim_pais (
            id_pais INT          NOT NULL,
            nombre  VARCHAR(100) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_pais)
        DISTRIBUTED BY HASH(id_pais) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_variedad", """
        CREATE TABLE IF NOT EXISTS dim_variedad (
            id_variedad INT          NOT NULL,
            nombre      VARCHAR(150) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_variedad)
        DISTRIBUTED BY HASH(id_variedad) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_bodega", """
        CREATE TABLE IF NOT EXISTS dim_bodega (
            id_bodega INT          NOT NULL,
            nombre    VARCHAR(200) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_bodega)
        DISTRIBUTED BY HASH(id_bodega) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_provincia", """
        CREATE TABLE IF NOT EXISTS dim_provincia (
            id_provincia INT          NOT NULL,
            nombre       VARCHAR(150) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_provincia)
        DISTRIBUTED BY HASH(id_provincia) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_region", """
        CREATE TABLE IF NOT EXISTS dim_region (
            id_region INT          NOT NULL,
            nombre    VARCHAR(150) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_region)
        DISTRIBUTED BY HASH(id_region) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_catador", """
        CREATE TABLE IF NOT EXISTS dim_catador (
            id_catador INT          NOT NULL,
            nombre     VARCHAR(150) NOT NULL,
            twitter    VARCHAR(100)
        )
        ENGINE = OLAP
        PRIMARY KEY(id_catador)
        DISTRIBUTED BY HASH(id_catador) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_resenas", """
        CREATE TABLE IF NOT EXISTS fact_resenas (
            id_resena    INT            NOT NULL,
            points       INT            NOT NULL,
            price        DECIMAL(10, 2) NOT NULL,
            title        VARCHAR(500),
            designation  VARCHAR(300),
            description  VARCHAR(1000),
            region_2     VARCHAR(150),
            id_pais      INT,
            id_variedad  INT,
            id_bodega    INT,
            id_provincia INT,
            id_region    INT,
            id_catador   INT
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_resena)
        DISTRIBUTED BY HASH(id_resena) BUCKETS 10
        PROPERTIES("replication_num" = "1")
    """),
]


def _connect() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        database=STARROCKS_DB,
        user=STARROCKS_USER,
        password=STARROCKS_PASS,
        connection_timeout=10,
    )


def ensure_database() -> None:
    """Crea la base de datos si no existe (conecta sin DB)."""
    conn = mysql.connector.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        user=STARROCKS_USER,
        password=STARROCKS_PASS,
        connection_timeout=10,
    )
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{STARROCKS_DB}`")
    cur.close()
    conn.close()
    print(f"  [DB]    Base de datos '{STARROCKS_DB}' asegurada")


def setup() -> list[str]:
    ensure_database()

    conn = _connect()
    cur  = conn.cursor()

    created: list[str] = []
    skipped: list[str] = []

    for name, ddl in TABLES:
        try:
            cur.execute(ddl.strip())
            conn.commit()
            created.append(name)
            print(f"  [OK]    {name}")
        except mysql.connector.Error as exc:
            msg = str(exc).lower()
            if "already exists" in msg or "1050" in str(exc.errno):
                skipped.append(name)
                print(f"  [SKIP]  {name}  (ya existe)")
            else:
                conn.rollback()
                raise

    cur.close()
    conn.close()

    print("\n" + "=" * 50)
    print("RESUMEN DE SETUP STARROCKS")
    print("=" * 50)
    for name, _ in TABLES:
        estado = "nueva" if name in created else "existente"
        print(f"  {name:30s}  [{estado}]")
    print(f"\nTotal: {len(created)} nueva(s), {len(skipped)} existente(s).")

    return created


if __name__ == "__main__":
    setup()
