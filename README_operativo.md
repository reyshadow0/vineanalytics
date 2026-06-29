# VinAnalytics — Sistema operativo (Punto 3 · SDD)

Implementación del stack operativo que exige la
[constitución](.specify/memory/constitution.md), siguiendo las specs de
`specs/operativo/`. Flujo de datos en capas fijas:

```
PocketBase ─► Parquet (staging, snappy) ─► StarRocks (DW Fact-Dim, DBT) ─► ClickHouse (agregaciones / serving)
(operacional)        etl/extractor            etl/loader + dbt_vinanalytics        clickhouse/populate.py
                          │ Great Expectations (fail-fast) en ambas fronteras (quality/)
                          └────────── orquestado por Apache Airflow (airflow/dags) ──────────┘
```

## 1. Servicios (docker-compose)

| Servicio | Imagen (fijada) | Puerto | Rol |
|---|---|---|---|
| pocketbase | `muchobien/pocketbase:0.22.21` | 8090 | Fuente operacional. |
| starrocks | `starrocks/allin1-ubuntu:3.3.5` | 9030 / 8030 | Data Warehouse OLAP (DBT). |
| clickhouse | `clickhouse/clickhouse-server:24.3` | 8123 / 9000 | Agregaciones / serving. |
| runner | `python:3.11-slim` + deps | — | ETL + DBT + GE + populador (larga vida). |
| airflow | `apache/airflow:2.9.3` + CLI Docker | 8080 | Orquestación (vía `docker exec` al runner). |
| flask | build local | 5000 | Dashboard + API pública. |

**Arquitectura de orquestación:** Airflow **no** ejecuta las etapas en su propio
entorno; cada tarea hace `docker exec vinanalytics-runner ...`. El `runner`
concentra todas las dependencias del pipeline (ETL, DBT, Great Expectations,
clickhouse-connect), por lo que **se evita el conflicto de pip** entre Airflow y
GE/DBT. El `runner` es de larga vida y comparte `stage/` entre etapas.

## 2. Levantar todo

```bash
docker compose up -d --build
```
- Dashboard/API: http://localhost:5000
- Airflow UI: http://localhost:8080  (usuario `admin`; la clave la genera
  `airflow standalone` al primer arranque)
- StarRocks (MySQL): `localhost:9030`  ·  ClickHouse HTTP: `localhost:8123`

Obtén la contraseña de Airflow (generada en el primer arranque):
```bash
docker compose exec airflow cat /opt/airflow/standalone_admin_password.txt
```

## 3. Correr el pipeline

### Opción A — orquestado por Airflow (recomendado)
1. Abre http://localhost:8080 (usuario `admin`, clave del archivo indicado en §2) y
   activa el DAG **`dag_pipeline_diario`**.
2. «Trigger DAG». Orden de tareas (fijo, Princ. IX):
   `ingesta → calidad_staging_ge → etl_carga_starrocks → dbt_run → dbt_test → calidad_dw_ge → poblar_clickhouse`.
3. Si una tarea de calidad (GE) falla, el DAG se **detiene** (fail-fast) y no se
   promueve nada aguas abajo. Tareas idempotentes con `retries=2`.

### Opción B — manual, paso a paso (en el runner, mismas etapas que el DAG)
```bash
docker compose exec runner python -m etl.extractor                 # ingesta → Parquet
docker compose exec runner python -m quality.run_quality --stage   # calidad previa (fail-fast)
docker compose exec runner python -m etl.loader                    # ETL → StarRocks
docker compose exec -w /app/dbt_vinanalytics runner dbt run  --profiles-dir .   # marts DBT
docker compose exec -w /app/dbt_vinanalytics runner dbt test --profiles-dir .   # tests DBT
docker compose exec runner python -m quality.run_quality --dw      # calidad posterior (fail-fast)
docker compose exec runner python -m clickhouse.populate           # agregaciones → ClickHouse
docker compose exec -w /app/dbt_vinanalytics runner dbt docs generate --profiles-dir .  # linaje
```

## 4. Datos de demostración (seeds)

Para poblar el Balanced Scorecard sin fuentes reales se incluyen **seeds
sintéticos** (excepción documentada al Princ. VI; **fuera del DAG productivo**):
```bash
docker compose exec runner python -m etl.pb_loader        # CSV winemag → PocketBase (fuente real)
docker compose exec runner python -m etl.bsc_generator    # SEED: BSC sintético → StarRocks
docker compose exec runner python -m etl.data_generator   # SEED: reseñas sintéticas → StarRocks
docker compose exec runner python -m clickhouse.populate  # refrescar agregaciones del dashboard
```

## 5. Serving del dashboard (ClickHouse con fallback)

El dashboard/API leen las agregaciones de **ClickHouse** (`serving.py`). Si
ClickHouse no está disponible o sus tablas están vacías, cada endpoint **cae
automáticamente a StarRocks** (su consulta original) — ningún dashboard queda en
blanco. Para desactivar el serving por ClickHouse: `CLICKHOUSE_ENABLED=0`.

## 6. Mapa a las specs operativas

| Componente | Paquete / CU-O |
|---|---|
| `etl/extractor.py` | `ingesta-datos` (OP1 · CU-O02) |
| `quality/` (GE + fail-fast) | `etl-calidad` (OP2 · CU-O04) |
| `etl/loader.py` + `dbt_vinanalytics/` | `etl-calidad` (OP2 · CU-O03) |
| `clickhouse/` + `serving.py` | `dashboards` (OP3 · CU-O05/06) |
| API pública (`app.py /api/v1/*`) | `api-publica` (OP4 · CU-O07) |
| `etl/ml_models.py` | `machine-learning` (OP8 · CU-O12) |
| `airflow/dags/dag_pipeline_diario.py` | orquestación (Princ. IX) |

## 7. Notas de dependencias y permisos

- **Sin conflicto de pip**: GE/DBT viven en el `runner` (`runner/Dockerfile`),
  separados de Airflow. La imagen de Airflow solo añade la **CLI de Docker** para
  hacer `docker exec` al runner. Versiones de imagen fijadas (sin `latest`, RT-17).
- **Socket de Docker**: Airflow monta `/var/run/docker.sock` para orquestar el
  runner. En **Docker Desktop (Windows/Mac)** funciona directamente. En hosts Linux,
  el usuario `airflow` puede necesitar pertenecer al grupo del socket (p. ej.
  `group_add: ["<gid_de_docker>"]` en el servicio `airflow`).
- **Alternativa sin Airflow**: la **Opción B** ejecuta exactamente las mismas
  etapas con `docker compose exec runner ...`, útil si no se desea exponer el socket.
