"""
Modelo estrella corporativo — Balanced Scorecard (BSC) de VinAnalytics Group.

Implementa las tablas Fact-Dim de negocio descritas en la "Visión arquitectónica"
del documento de Desarrollo Empresarial (sección 9.3 / 9.4), que el warehouse
vitivinícola (fact_resenas) no cubría:

  Fact_Suscripcion · Fact_Uso_Plataforma · Fact_Consumo_API · Fact_Campana ·
  Fact_Conversion · Fact_Retencion · Fact_Disponibilidad · Fact_Integracion_Partner

Más fact_aprendizaje (perspectiva de Aprendizaje y Crecimiento) y las dimensiones
de negocio (Dim_Tiempo, Dim_Mercado, Dim_Cliente, Dim_Plan, Dim_Canal_Adquisicion,
Dim_Partner_API, Dim_Campana, Dim_Estado_Suscripcion).

Con estas tablas el sistema alimenta el Balanced Scorecard corporativo (CU-E01) y
los casos de uso estratégicos CU-E02 … CU-E08.

Idempotente: CREATE TABLE IF NOT EXISTS. Convención StarRocks idéntica a
db/starrocks_setup.py (PRIMARY KEY en dimensiones, DUPLICATE KEY en hechos).
"""

import sys
from pathlib import Path
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS,
)

# Orden de creación: dimensiones primero, hechos después.
BSC_TABLES: list[tuple[str, str]] = [
    # ── DIMENSIONES ──────────────────────────────────────────────────────────
    ("dim_tiempo", """
        CREATE TABLE IF NOT EXISTS dim_tiempo (
            id_tiempo  INT          NOT NULL,   -- AAAAMM (p.ej. 202601)
            fecha      DATE,
            anio       INT,
            trimestre  INT,
            mes        INT,
            mes_nombre VARCHAR(20),
            periodo    VARCHAR(10)              -- 'AAAA-MM'
        )
        ENGINE = OLAP
        PRIMARY KEY(id_tiempo)
        DISTRIBUTED BY HASH(id_tiempo) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_mercado", """
        CREATE TABLE IF NOT EXISTS dim_mercado (
            id_mercado INT          NOT NULL,
            pais       VARCHAR(80)  NOT NULL,
            region_geo VARCHAR(60)
        )
        ENGINE = OLAP
        PRIMARY KEY(id_mercado)
        DISTRIBUTED BY HASH(id_mercado) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_plan", """
        CREATE TABLE IF NOT EXISTS dim_plan (
            id_plan        INT           NOT NULL,
            nombre         VARCHAR(40)   NOT NULL,
            precio_mensual DECIMAL(10,2) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_plan)
        DISTRIBUTED BY HASH(id_plan) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_canal_adquisicion", """
        CREATE TABLE IF NOT EXISTS dim_canal_adquisicion (
            id_canal INT         NOT NULL,
            nombre   VARCHAR(40) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_canal)
        DISTRIBUTED BY HASH(id_canal) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_partner_api", """
        CREATE TABLE IF NOT EXISTS dim_partner_api (
            id_partner INT          NOT NULL,
            nombre     VARCHAR(80)  NOT NULL,
            tipo       VARCHAR(40)
        )
        ENGINE = OLAP
        PRIMARY KEY(id_partner)
        DISTRIBUTED BY HASH(id_partner) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_estado_suscripcion", """
        CREATE TABLE IF NOT EXISTS dim_estado_suscripcion (
            id_estado INT         NOT NULL,
            nombre    VARCHAR(30) NOT NULL
        )
        ENGINE = OLAP
        PRIMARY KEY(id_estado)
        DISTRIBUTED BY HASH(id_estado) BUCKETS 1
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_cliente", """
        CREATE TABLE IF NOT EXISTS dim_cliente (
            id_cliente INT          NOT NULL,
            nombre     VARCHAR(120) NOT NULL,
            tipo       VARCHAR(40),
            tamano     VARCHAR(20),
            segmento   VARCHAR(30),
            id_mercado INT,
            id_plan    INT,
            id_canal   INT,
            fecha_alta DATE
        )
        ENGINE = OLAP
        PRIMARY KEY(id_cliente)
        DISTRIBUTED BY HASH(id_cliente) BUCKETS 4
        PROPERTIES("replication_num" = "1")
    """),
    ("dim_campana", """
        CREATE TABLE IF NOT EXISTS dim_campana (
            id_campana INT          NOT NULL,
            nombre     VARCHAR(120) NOT NULL,
            id_mercado INT,
            id_canal   INT,
            segmento   VARCHAR(30)
        )
        ENGINE = OLAP
        PRIMARY KEY(id_campana)
        DISTRIBUTED BY HASH(id_campana) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),

    # ── HECHOS ───────────────────────────────────────────────────────────────
    ("fact_suscripcion", """
        CREATE TABLE IF NOT EXISTS fact_suscripcion (
            id_suscripcion BIGINT        NOT NULL,
            id_tiempo      INT           NOT NULL,
            id_cliente     INT,
            id_plan        INT,
            id_estado      INT,
            mrr            DECIMAL(10,2),
            es_nuevo       INT,
            es_upgrade     INT,
            es_downgrade   INT,
            es_churn       INT
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_suscripcion, id_tiempo)
        DISTRIBUTED BY HASH(id_suscripcion) BUCKETS 6
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_uso_plataforma", """
        CREATE TABLE IF NOT EXISTS fact_uso_plataforma (
            id_uso           BIGINT NOT NULL,
            id_tiempo        INT    NOT NULL,
            id_cliente       INT,
            sesiones         INT,
            dashboards_vistos INT,
            funciones_usadas INT,
            usuarios_activos INT,
            usuarios_totales INT,
            nps_score        INT     -- 0..10 ; -1 = sin respuesta
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_uso, id_tiempo)
        DISTRIBUTED BY HASH(id_uso) BUCKETS 6
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_consumo_api", """
        CREATE TABLE IF NOT EXISTS fact_consumo_api (
            id_consumo  BIGINT        NOT NULL,
            id_tiempo   INT           NOT NULL,
            id_partner  INT,
            llamadas    BIGINT,
            latencia_ms DECIMAL(8,2),
            errores     INT,
            ingreso_api DECIMAL(12,2)
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_consumo, id_tiempo)
        DISTRIBUTED BY HASH(id_consumo) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_campana", """
        CREATE TABLE IF NOT EXISTS fact_campana (
            id_fact_campana BIGINT        NOT NULL,
            id_tiempo       INT           NOT NULL,
            id_campana      INT,
            impresiones     BIGINT,
            clics           INT,
            gasto           DECIMAL(10,2),
            leads           INT
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_fact_campana, id_tiempo)
        DISTRIBUTED BY HASH(id_fact_campana) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_conversion", """
        CREATE TABLE IF NOT EXISTS fact_conversion (
            id_conversion BIGINT        NOT NULL,
            id_tiempo     INT           NOT NULL,
            id_mercado    INT,
            id_canal      INT,
            leads         INT,
            oportunidades INT,
            conversiones  INT,
            cac           DECIMAL(10,2)
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_conversion, id_tiempo)
        DISTRIBUTED BY HASH(id_conversion) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_retencion", """
        CREATE TABLE IF NOT EXISTS fact_retencion (
            id_retencion BIGINT        NOT NULL,
            id_tiempo    INT           NOT NULL,
            id_cliente   INT,
            activo       INT,
            cancelacion  INT,
            ltv          DECIMAL(12,2),
            riesgo_churn DECIMAL(5,2)   -- 0..1
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_retencion, id_tiempo)
        DISTRIBUTED BY HASH(id_retencion) BUCKETS 6
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_disponibilidad", """
        CREATE TABLE IF NOT EXISTS fact_disponibilidad (
            id_disponibilidad   BIGINT        NOT NULL,
            id_tiempo           INT           NOT NULL,
            id_mercado          INT,
            uptime              DECIMAL(6,3),   -- %
            latencia_ms         DECIMAL(8,2),
            incidentes          INT,
            despliegues         INT,
            time_to_market_dias DECIMAL(5,2),
            costo_cloud         DECIMAL(10,2)
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_disponibilidad, id_tiempo)
        DISTRIBUTED BY HASH(id_disponibilidad) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_integracion_partner", """
        CREATE TABLE IF NOT EXISTS fact_integracion_partner (
            id_integracion     BIGINT        NOT NULL,
            id_tiempo          INT           NOT NULL,
            id_partner         INT,
            conexiones_activas INT,
            ingreso_api        DECIMAL(12,2)
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_integracion, id_tiempo)
        DISTRIBUTED BY HASH(id_integracion) BUCKETS 3
        PROPERTIES("replication_num" = "1")
    """),
    ("fact_aprendizaje", """
        CREATE TABLE IF NOT EXISTS fact_aprendizaje (
            id_aprendizaje          BIGINT        NOT NULL,
            id_tiempo               INT           NOT NULL,
            horas_capacitacion      DECIMAL(6,2), -- acumulado/año por persona
            decisiones_data_driven  DECIMAL(5,2), -- %
            tecnologias_adoptadas   INT,          -- acumulado en el año
            rotacion_personal       DECIMAL(5,2), -- %
            modelos_ml_produccion   INT
        )
        ENGINE = OLAP
        DUPLICATE KEY(id_aprendizaje, id_tiempo)
        DISTRIBUTED BY HASH(id_aprendizaje) BUCKETS 1
        PROPERTIES("replication_num" = "1")
    """),
]

# Para reset: borrar hechos antes que dimensiones.
BSC_DROP_ORDER = [
    "fact_aprendizaje", "fact_integracion_partner", "fact_disponibilidad",
    "fact_retencion", "fact_conversion", "fact_campana", "fact_consumo_api",
    "fact_uso_plataforma", "fact_suscripcion",
    "dim_campana", "dim_cliente", "dim_estado_suscripcion", "dim_partner_api",
    "dim_canal_adquisicion", "dim_plan", "dim_mercado", "dim_tiempo",
]


def _connect() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        database=STARROCKS_DB,
        user=STARROCKS_USER,
        password=STARROCKS_PASS,
        connection_timeout=15,
    )


def setup_bsc() -> list[str]:
    """Crea las tablas del Balanced Scorecard. Idempotente."""
    conn = _connect()
    cur  = conn.cursor()

    created: list[str] = []
    skipped: list[str] = []

    for name, ddl in BSC_TABLES:
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
    print("RESUMEN SETUP BSC (StarRocks)")
    print("=" * 50)
    print(f"Total: {len(created)} creada(s)/verificada(s), {len(skipped)} ya existían.")
    return created


if __name__ == "__main__":
    setup_bsc()
