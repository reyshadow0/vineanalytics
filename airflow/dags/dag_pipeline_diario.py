"""
DAG operativo de VinAnalytics — dag_pipeline_diario.

Orquesta el pipeline declarativo (Princ. IX) en el orden FIJO de la constitución:

    ingesta → calidad (GE staging) → ETL/DBT → calidad (GE DW) → agregaciones (ClickHouse)

Arquitectura de ejecución (rev. runner):
  Airflow NO ejecuta las etapas en su propio entorno. Cada tarea hace
  `docker exec vinanalytics-runner ...` contra el contenedor `runner`, que tiene
  TODAS las dependencias del pipeline (ETL, DBT, Great Expectations,
  clickhouse-connect). Así se evita el conflicto de pip entre Airflow y GE/DBT.
  El `runner` es de larga vida: su /app (bind del repo) conserva el `stage/`
  Parquet entre tareas, de modo que la ingesta y el ETL comparten estado.

Propiedades (constitución):
  - Idempotencia: ingesta sobrescribe el Parquet; el ETL hace TRUNCATE+INSERT;
    los marts DBT son `table` (full refresh); GE es de solo lectura; el populador
    de ClickHouse hace TRUNCATE+INSERT.
  - Reintentos: retries=2, retry_delay=2 min (default_args).
  - Sin catchup; un único run activo a la vez.
  - Fail-fast: GE staging/DW devuelven exit≠0 al fallar (quality/run_quality.py),
    y `dbt test` también; `docker exec` propaga ese código → la tarea falla y el
    DAG se detiene. NO se carga a StarRocks ni se promueve a ClickHouse.

Los SEEDS sintéticos (etl/bsc_generator.py, etl/data_generator.py) NO forman parte
de este DAG (excepción documentada al Princ. VI).
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# Contenedor con las dependencias del pipeline (definido en docker-compose.yml).
RUNNER = "vinanalytics-runner"
DBT_DIR = "/app/dbt_vinanalytics"

default_args = {
    "owner": "ingenieria-datos",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "depends_on_past": False,
}

with DAG(
    dag_id="dag_pipeline_diario",
    description="ingesta → calidad → ETL/DBT → calidad → agregaciones (VinAnalytics OP1–OP3)",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["vinanalytics", "operativo", "OP1", "OP2", "OP3"],
) as dag:

    # OP1 · CU-O02 — PocketBase → stage/wine_raw.parquet (idempotente)
    ingesta = BashOperator(
        task_id="ingesta",
        bash_command=f"docker exec {RUNNER} python -m etl.extractor",
    )

    # OP2 · CU-O04 (previa) — gate fail-fast sobre el staging Parquet
    calidad_staging = BashOperator(
        task_id="calidad_staging_ge",
        bash_command=f"docker exec {RUNNER} python -m quality.run_quality --stage",
    )

    # OP2 · CU-O03 — transform + load del modelo base en StarRocks
    etl_starrocks = BashOperator(
        task_id="etl_carga_starrocks",
        bash_command=f"docker exec {RUNNER} python -m etl.loader",
    )

    # OP2 · CU-O03 — construye los marts Fact-Dim (DBT)
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"docker exec -w {DBT_DIR} {RUNNER} dbt run --profiles-dir .",
    )

    # OP2 · CU-O03 — tests DBT (unique/not_null/relationships/accepted_values + dominio)
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"docker exec -w {DBT_DIR} {RUNNER} dbt test --profiles-dir .",
    )

    # OP2 · CU-O04 (posterior) — gate fail-fast sobre los marts en StarRocks
    calidad_dw = BashOperator(
        task_id="calidad_dw_ge",
        bash_command=f"docker exec {RUNNER} python -m quality.run_quality --dw",
    )

    # OP3 — pobla las agregaciones de ClickHouse desde StarRocks (idempotente).
    # populate.py ya NO calcula agregaciones: solo TRANSPORTA las vistas DBT
    # serving.agg_* a ClickHouse (Princ. VI). La lógica vive en dbt_run.
    agregaciones = BashOperator(
        task_id="poblar_clickhouse",
        bash_command=f"docker exec {RUNNER} python -m clickhouse.populate",
    )

    # OP11 · CU-O16 — reporte operativo diario, ÚLTIMO paso del flujo (RN-1203).
    # Lee SOLO agregaciones de ClickHouse (RN-1202) y verifica el sello de calidad
    # del día (RF-1104): exit≠0 (BLOQUEADO_SIN_CALIDAD/FALLIDO) marca la tarea fallida.
    reporte_diario = BashOperator(
        task_id="reporte_diario",
        bash_command=f"docker exec {RUNNER} python -m reportes.reporte_diario",
    )

    # Orden FIJO del flujo de datos (Princ. IX); el reporte cierra el pipeline.
    (ingesta >> calidad_staging >> etl_starrocks >> dbt_run >> dbt_test
     >> calidad_dw >> agregaciones >> reporte_diario)
