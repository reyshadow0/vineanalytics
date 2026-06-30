# Verificación de cobertura operativa — CU-O01 … CU-O16

> **Auditoría de solo lectura.** No se modificó ni ejecutó código; no se levantó Docker.
> Cada estado se respalda con evidencia real (`ruta:línea · función/endpoint`).
> Fuentes de verdad: `.specify/memory/constitution.md`, `specs/operativo/**`, código del repo.
> Fecha: 2026-06-29.

**Leyenda:** ✅ Implementado (lógica real y verificable) · 🟡 Parcial (existe pero incompleto / salta capas / sin persistencia / fuera del DAG) · ❌ Ausente (sin evidencia).

---

## 1. Tabla de cobertura

| CU-O | Descripción | OP | Paquete | Evidencia (archivo:línea · función/endpoint) | Estado | Notas |
|---|---|---|---|---|---|---|
| **CU-O01** | Registrar fuente de datos externa | OP1 | ingesta-datos | `etl/pb_loader.py:81` `upload()` (sube reseñas a la colección `wine_reviews`); `config.py:4` `POCKETBASE_COLLECTION` | ❌ | No existe catálogo de **fuentes** con metadatos (`tipo`, `frecuencia`, `formato`, `endpoint`), ni dedup de fuentes, ni validación de conectividad/esquema al alta, ni asociación a `Dim_Catador_Sumiller`/`Dim_Mercado`. `pb_loader` carga los **datos**, no registra la fuente. |
| **CU-O02** | Ingestar datos (reseñas, precios, puntuaciones) | OP1 | ingesta-datos | `etl/extractor.py:42` `extract()`; escribe Parquet en `etl/extractor.py:101`; tarea DAG `airflow/dags/dag_pipeline_diario.py:58` `ingesta` | 🟡 | Aterriza PocketBase→`stage/wine_raw.parquet` (snappy por defecto de pandas/pyarrow) e idempotente por sobrescritura total. **Faltan:** validación de esquema en aterrizaje, **deduplicación** previa, particionado por `fuente`/`fecha_ingesta`, área `rejects/`, umbral 5 % (RN-204) y **reporte de ingesta** (leídas/cargadas/rechazadas/duplicadas, RF-110). Solo una colección fija. |
| **CU-O03** | Ejecutar pipeline ETL | OP2 | etl-calidad | `dbt_vinanalytics/models/staging/stg_resena.sql:1`, `marts/fct_resena.sql:11`, `marts/fct_precio_mercado.sql:12`, `marts/fct_puntuacion.sql`; `_schema.yml` (tests); tareas `dbt_run`/`dbt_test` `airflow/dags/dag_pipeline_diario.py:76,82` | ✅ | Modelos DBT versionados con materialización (`view`/`table`) y tests (`unique`,`not_null`,`relationships`,`accepted_values`) + 2 tests singulares de dominio. **Caveat:** la carga base a StarRocks (`fact_resenas`+dims) es imperativa en `etl/transformer.py` + `etl/loader.py:56` (TRUNCATE+INSERT), que DBT reutiliza como `source` — ver regla B. |
| **CU-O04** | Validar calidad de datos | OP2 | etl-calidad | `quality/run_quality.py:34` `main()` (exit 1 fail-fast en `:59`); `quality/ge_staging.py:42` `validar_staging()`; `quality/ge_dw.py:60` `validar_dw()`; tareas `calidad_staging_ge`/`calidad_dw_ge` `airflow/dags/dag_pipeline_diario.py:64,88` | ✅ | Gate previo (staging) y posterior (DW) con Great Expectations: unicidad de clave, no-nulos, dominios (`puntaje∈[80,100]`, `precio>0.01`, `moneda='USD'`). `exit≠0` corta el DAG vía `docker exec`. |
| **CU-O05** | Construir dashboard de cliente | OP3 | dashboards | rutas `app.py:315` `/dashboard`, `app.py:310` `/vinos`, `app.py:748` `/balanced-scorecard`; lectura ClickHouse `serving.py:76` `kpis()` con fallback (`app.py:333`) | 🟡 | Dashboards **genéricos** (vino + BSC + inteligencia) leen de ClickHouse con fallback a StarRocks (capa correcta). **Faltan:** construcción **por cliente**, versionado (`BORRADOR→publicable`, RF-303), filtros por `Dim_Cliente`/`Dim_Plan` y aislamiento multi-tenant (RNF-302). |
| **CU-O06** | Publicar dashboard a la cuenta | OP3 | dashboards | acceso por rol `auth.py:9` `login_required`, `auth.py:20` `admin_required`; rutas `/dashboard`,`/admin` `app.py:315,322` | ❌ | No hay publicación a una **cuenta** concreta, ni permisos por `Dim_Plan`, ni registro/versionado de publicaciones, ni el **bloqueo por calidad previa** (RN-401/RF-305). Solo control de acceso genérico por rol. |
| **CU-O07** | Atender solicitud de la API pública | OP4 | api-publica | `app.py:1002` `require_api_key` (401), rate-limit 429 `app.py:996-1016`; endpoints `/api/v1/vinos` `app.py:1028`, `/api/v1/mercados` `app.py:1062`, `/api/v1/precios` `app.py:1084`, `/api/v1/scorecard` `app.py:1095`; OpenAPI `app.py:1123` `/api/v1/openapi.json`; `/api-docs` `app.py:1152` | ✅ | Autenticación por API key, rate limiting (60/min), contrato OpenAPI 3.0 versionado `/v1`, sirve de ClickHouse con fallback (`serving.py:173` `v1_mercados`). **Gap de sub-requisito:** cada llamada se cuenta **en memoria** (`_api_metrics` `app.py:999`), **no se persiste** en `Fact_Consumo_API` (RF-405/RN-504); esa tabla solo se llena sintéticamente (`etl/bsc_generator.py:397`). |
| **CU-O08** | Registrar cuenta y suscripción | OP5 | suscripciones | `models.py:10` gestiona `usuarios_sistema` (usuarios internos); `dim_cliente`/`fact_suscripcion` poblados en `etl/bsc_generator.py:296,306` | ❌ | No hay alta de **cuenta de cliente B2B + suscripción** en PocketBase, ni dedup (RN-601), ni ciclo de vida `Dim_Estado_Suscripcion`, ni eventos a `Fact_Suscripcion`. `models.py` administra usuarios de la app (admin/analista/gerente), no clientes. Los datos comerciales son **sintéticos**. |
| **CU-O09** | Ejecutar campaña de captación | OP6 | captacion-conversion | `db/bsc_setup.py:185` DDL `fact_campana`/`dim_campana`; poblado sintético `etl/bsc_generator.py:333-348` | ❌ | Solo existen la tabla y datos sintéticos. No hay módulo de **ejecución** de campañas (configurar, programar, lanzar, capturar impresiones/clics/gasto/leads desde un canal). |
| **CU-O10** | Registrar conversión del embudo | OP6 | captacion-conversion | DDL `fact_conversion` `db/bsc_setup.py:200`; poblado sintético `etl/bsc_generator.py:351-371` | ❌ | No hay registro de conversión con etapa/fuente/resultado, **modelo de atribución** (RF-606), ni entrega del alta a `suscripciones` (RF-608). Solo seed sintético. |
| **CU-O11** | Monitorear uptime y latencia | OP7 | observabilidad | `observabilidad/monitor.py` (`probar_servicios`/`consolidar`/`persistir_disponibilidad`/`evaluar_slo`); tarea `observabilidad` `airflow/dags/dag_pipeline_diario.py`; healthchecks Docker `docker-compose.yml:23,44`; `tests/test_alertas.py` | ✅ | **(Sesión OP7/OP8/OP9, 2026-06-29)** Sonda real de uptime/latencia de StarRocks/ClickHouse/PocketBase, `uptime=operativo/total×100`, persistencia **idempotente** en `fact_disponibilidad` por región (DELETE período+INSERT), incidentes con duración/región en PocketBase (RF-706) y **señal de SLO** a `alertas` (RN-802). Pendiente: stack Prometheus/Grafana y arranque end-to-end en Docker. |
| **CU-O12** | Ejecutar modelo de ML programado | OP8 | machine-learning | `etl/ml_inference.py` (`inferir`/`churn_predicciones`/`precio_predicciones`); modelos `etl/ml_models.py`; tarea `ml_inferencia` `airflow/dags/dag_pipeline_diario.py`; `tests/test_alertas.py` | ✅ | **(Sesión OP7/OP8/OP9, 2026-06-29)** Inferencia **programada** (tarea del DAG) con **gate de calidad** (sello CU-O04 → `BLOQUEADA_POR_CALIDAD`, RN-901), persistencia de predicciones con **versión+features+score** (`predicciones_ml`, RF-805) **idempotente** por (corrida, entidad) (RNF-802) y **señales** de churn alto/precio anómalo a `alertas` (RN-903/904). Falta arranque end-to-end en Docker. |
| **CU-O13** | Generar alerta (churn/precio) | OP9 | alertas | `models_alertas.py` (`generar_alerta`/`clasificar`/dedup/ciclo de vida) + `alertas/alert_engine.py`; tarea `alertas` `airflow/dags/dag_pipeline_diario.py`; `tests/test_alertas.py` | ✅ | **(Sesión OP7/OP8/OP9, 2026-06-29)** Bus `senales_alerta`, **generación/registro** de la alerta con clasificación tipo/severidad/causa (RF-903/904), **enrutamiento** por responsable (RF-905), **deduplicación** por `clave` anti-tormenta (RF-906/RN-1004) y **ciclo de vida** (RF-907). Consume CU-O11 (uptime/latencia) y CU-O12 (churn/precio) + detección propia z-score. Pendiente: emisores OP1/OP4/OP6 y reintento de notificación externa. |
| **CU-O14** | Registrar onboarding y ticket | OP10 | customer-success | `models_customer_success.py` (`iniciar_onboarding`/`avanzar_onboarding`/`abrir_ticket`/`transicionar_ticket`/`registrar_satisfaccion`/`vincular_retencion`); colecciones `onboarding`/`tickets`/`acciones_retencion` en `db/pb_setup.py`; endpoints `/onboarding*`, `/tickets*`, `/clientes/<id>/soporte`, `/clientes/<id>/retencion`; disparo de onboarding al alta en `app.py::clientes` (POST); `tests/test_customer_success.py` | ✅ | **(Sesión OP10, 2026-06-29)** Onboarding (estado/pasos, idempotente RN-1104) y tickets de soporte asociados a una **cuenta existente** (`clientes` de CU-O08): clasificación, ciclo de vida `ABIERTO→EN_PROCESO→RESUELTO→CERRADO` con `REABIERTO` (RN-1101), tiempos de primera respuesta/resolución (RF-1003) y NPS (RF-1004). Alerta de churn (OP9) **prioriza y vincula** una acción de retención (RN-1103). Persistencia 100 % PocketBase (no salta capas). Pendiente: `speckit-analyze` y arranque end-to-end en Docker. |
| **CU-O15** | Consultar uso por cliente | OP10 | customer-success | modelo DBT `dbt_vinanalytics/models/serving/agg_uso_cliente.sql` (agrega `fact_uso_plataforma`×`dim_cliente`); DDL `clickhouse/aggregations.sql` + transporte `clickhouse/populate.py` (`agg_uso_cliente`); lectores `serving.uso_por_cliente`/`uso_clientes`; endpoints `/api/uso/<cid>` y `/api/uso` (fallback a la vista DBT en StarRocks); `tests/test_customer_success.py` | ✅ | **(Sesión OP10, 2026-06-29)** Consulta de **uso/adopción por cliente** (sesiones, dashboards, funciones, **frecuencia**, adopción %, NPS) leyendo la **agregación** `agg_uso_cliente` de ClickHouse (RN-1102), nunca los eventos crudos (verificado en test, Esc-1106). Acompaña la prioridad de retención si hay churn vivo (RF-1006). Princ. VI: agregación declarativa en DBT con tests. Pendiente: suite GE de `Fact_Uso_Plataforma` y arranque en Docker. |
| **CU-O16** | Generar reporte operativo diario | OP11 | reportes-operativos | `reportes/reporte_diario.py` `generar()` (gate calidad + consolida + archiva); `serving.reporte_diario_fuentes()` (solo ClickHouse); modelo DBT `serving/agg_reporte_diario.sql`; tarea final DAG `reporte_diario` `airflow/dags/dag_pipeline_diario.py`; endpoints `/api/reporte-diario`, `/reporte-diario` | ✅ | **(Sesión OP11, 2026-06-29)** Reporte diario consolida ingesta+API+uso+incidentes por `Dim_Tiempo` desde ClickHouse (RN-1202), con gate del sello de calidad (RF-1104 → `BLOQUEADO_SIN_CALIDAD`), trazabilidad por sección (RN-1204), archivo por fecha reproducible (RN-1205) y último paso del DAG (RN-1203). Cubierto por `tests/test_reportes.py` (8 pruebas). Falta arranque end-to-end en Docker. |

---

## 2. Resumen cuantitativo

> Actualizado en la sesión OP10 (2026-06-29): CU-O14 y CU-O15 pasan de ❌ a ✅
> (ver §1). Sesiones previas: OP7/OP8/OP9 (CU-O11/12/13) y OP11 (CU-O16).

- **✅ Implementados: 9/16** — CU-O03, CU-O04, CU-O07, CU-O11, CU-O12, CU-O13, CU-O14, CU-O15, CU-O16
- **🟡 Parciales: 2/16** — CU-O02, CU-O05
- **❌ Ausentes: 5/16** — CU-O01, CU-O06, CU-O08, CU-O09, CU-O10

**Cobertura plena:** 9/16 = **56.25 %**.
**Cobertura efectiva** (parciales ponderados al 50 %): (9 + 1)/16 = 10/16 = **62.5 %**.

El núcleo del **pipeline de datos OP1→OP3** (ingesta → calidad → ETL/DBT → calidad → agregaciones → serving/API) está operativo. Los objetivos de **negocio/SaaS** (OP5, OP6, OP10, OP11) y la **gestión de fuentes/publicación/alertas** (OP1-CU-O01, OP3-CU-O06, OP9) carecen de lógica funcional: sus tablas Fact-Dim existen pero se llenan con **datos sintéticos** (`etl/bsc_generator.py`), no con los casos de uso reales.

---

## 3. Lista de huecos priorizada

### Bloqueantes de entrega (núcleo del pipeline OP1–OP2 incompleto)

1. **CU-O02 — Ingesta sin dedup/rejects/reporte 🟡.** Falta: validación de esquema en aterrizaje, deduplicación por clave natural (RN-203), particionado `fuente`/`fecha_ingesta`, área `rejects/`, umbral 5 % (RN-204) y reporte de ingesta.
   → *Recomendación:* añadir a `etl/extractor.py` una función `_validar_y_deduplicar(df)` + escritura particionada (`pyarrow.dataset`/`partition_cols`) y emitir un dict-reporte; crear `etl/ingesta_report.py`.

2. **CU-O01 — Catálogo de fuentes ❌.** No hay registro de fuentes externas.
   → *Recomendación:* colección PocketBase `data_sources` + módulo `etl/source_catalog.py` (`registrar_fuente()`, dedup por `tipo+endpoint+formato`, validación de conectividad/esquema, asociación a `Dim_Mercado`/`Dim_Catador_Sumiller`).

### Alto impacto de negocio (OP5/OP6/OP10/OP11 ausentes)

3. **CU-O08 — Alta de cuenta/suscripción ❌.** → `models_clientes.py` + endpoints `/clientes` y `/suscripciones` sobre PocketBase, con dedup (RN-601), `Dim_Estado_Suscripcion` y emisión de evento a `Fact_Suscripcion`.
4. **CU-O09 / CU-O10 — Campañas y conversión ❌.** → `etl/campaigns.py` (config + ejecución programada en Airflow, métricas a `Fact_Campana`) y `etl/conversions.py` (registro + atribución única a `Fact_Conversion`, hand-off a suscripciones).
5. **CU-O14 / CU-O15 — Customer Success ✅ (sesión OP10, 2026-06-29).** Hecho: colecciones `onboarding`/`tickets`/`acciones_retencion` en PocketBase (`models_customer_success.py`) + `serving.uso_por_cliente()` que lee `agg_uso_cliente` (Fact_Uso_Plataforma agregado) de ClickHouse y endpoint `/api/uso/<id_cliente>`.
6. **CU-O16 — Reporte operativo diario ❌.** → `reportes/reporte_diario.py` (consolida ClickHouse por `Dim_Tiempo`, verifica sello de calidad del día) + tarea final en el DAG tras `poblar_clickhouse` + archivo por fecha.

### Cierran flujos transversales

7. **CU-O13 — Subsistema de alertas 🟡.** Existe detección; falta emisión/registro/clasificación/enrutamiento/dedup/ciclo de vida.
   → *Recomendación:* `alerts/alert_engine.py` (tabla `alertas`, `generar_alerta(tipo,severidad,causa,origen)`, dedup, lifecycle) consumiendo señales de ML/observabilidad/ingesta/API.
8. **CU-O12 — ML programado 🟡.** Falta tarea de inferencia en el DAG y persistencia con versión.
   → *Recomendación:* `etl/ml_inference.py` que persista scores en `Fact_Retencion`/predicciones con `version_modelo`+fecha; añadir tarea `ml_inferencia` al DAG.
9. **CU-O11 — Observabilidad 🟡.** Solo healthchecks Docker. → recolector real de métricas + evaluación de SLO que escriba `Fact_Disponibilidad` y dispare CU-O13.
10. **CU-O06 — Publicación de dashboard ❌** y **CU-O05 🟡.** → registro de publicaciones por cuenta (cuenta+permisos+plan+versión) con **gate de calidad** (RN-401) y filtros por `Dim_Cliente`/`Dim_Plan`.
11. **CU-O07 — Persistir consumo de API.** El núcleo está ✅; falta escribir cada llamada en `Fact_Consumo_API` (RF-405) en lugar del contador en memoria (`app.py:999`).

---

## 4. Verificación de reglas de la constitución

| Regla (no negociable) | Estado | Evidencia |
|---|---|---|
| **A. Gates Great Expectations con fallo rápido** (`exit≠0` detiene el DAG) | ✅ | `quality/run_quality.py:59` retorna `1` si falla; el DAG ejecuta `python -m quality.run_quality --stage/--dw` vía `docker exec`, que propaga el exit code y corta el flujo: `airflow/dags/dag_pipeline_diario.py:64,88,100`. |
| **B. Toda transformación declarativa en DBT** (sin SQL imperativo suelto) | ✅ | **(Sesión OP11/Princ. VI, 2026-06-29)** Las **agregaciones** de serving se movieron a modelos DBT declarativos con tests: `dbt_vinanalytics/models/serving/agg_*.sql` (vino, BSC kpis/series, tendencia de precio, reporte diario). `clickhouse/populate.py` ya **no** calcula: solo TRANSPORTA las vistas DBT a ClickHouse; `app.py` ya **no** duplica el GROUP BY (los fallbacks leen las vistas `agg_*`). Carga técnica que permanece (justificada): (1) la carga base Fact-Dim `etl/transformer.py`+`etl/loader.py` es el **aterrizaje** que DBT usa como `source` (DBT no ingiere Parquet→StarRocks); (2) `etl/bsc_generator.py` es **semilla sintética** fuera del DAG (excepción documentada). El tramo declarativo cubre ahora `stg_*→fct_*→agg_*`. Validación `dbt run/test` pendiente de Docker. |
| **C. Lectura dashboard/API desde ClickHouse con fallback a StarRocks** | ✅ | `serving.py:23` `_get_client()` / `:43` `_q()` leen ClickHouse y devuelven `None` ante fallo; cada endpoint cae a StarRocks, p. ej. `app.py:333-336` (`api_kpis`), `app.py:1066-1069` (`/api/v1/mercados`). Conmutable por `CLICKHOUSE_ENABLED` (`config.py:23`). |
| **D. Orquestación en Airflow, idempotente y en orden correcto** | ✅ | DAG `dag_pipeline_diario` con orden fijo `ingesta>>calidad_staging>>etl>>dbt_run>>dbt_test>>calidad_dw>>agregaciones` (`airflow/dags/dag_pipeline_diario.py:100`); `retries=2`, `retry_delay=2min`, `catchup=False`, `max_active_runs=1` (`:39-53`); idempotencia por TRUNCATE+INSERT / marts `table`. *Nota:* solo orquesta OP1–OP3; ML, alertas y reportes (OP8/OP9/OP11) no están en el DAG. |
| **E. Docker con versiones fijas (sin `:latest`)** | ✅ | `docker-compose.yml`: `pocketbase:0.22.21` (`:5`), `starrocks/allin1-ubuntu:3.3.5` (`:15`), `clickhouse/clickhouse-server:24.3` (`:33`); `runner/Dockerfile` `python:3.11-slim`; `airflow/Dockerfile` `apache/airflow:2.9.3-python3.11`; `Dockerfile` `python:3.13-slim`. Búsqueda de `:latest` sin coincidencias. |

---

## 5. Veredicto final

**No, el programa no cubre los 16 casos de uso operativos: solo 3/16 están plenamente implementados (CU-O03, CU-O04, CU-O07), 5 son parciales y 8 están ausentes (~18.75 % pleno / ~34 % efectivo).** Está sólido el **pipeline técnico de datos OP1→OP3** (ETL/DBT + calidad fail-fast + serving ClickHouse/fallback + API pública + orquestación Airflow con imágenes fijas), pero **la capa de negocio del SaaS es sintética, no funcional**: las tablas Fact-Dim de suscripciones, campañas, conversión, uso, disponibilidad y consumo de API se rellenan con `etl/bsc_generator.py`, sin los casos de uso que el documento exige.

**Bloquean la entrega (huecos ❌ de objetivos completos):** **CU-O01** (sin catálogo de fuentes, OP1 incompleto), **CU-O06** (sin publicación con gate de calidad, OP3 incompleto), **CU-O08** (sin alta de cuentas/suscripciones, OP5 sin lógica), **CU-O09/CU-O10** (OP6 sin lógica), **CU-O14/CU-O15** (OP10 sin lógica) y **CU-O16** (OP11 sin reporte diario). Además, regularizar la **regla B** (mover la transformación base y las agregaciones a DBT) es necesario para cumplir la constitución.
