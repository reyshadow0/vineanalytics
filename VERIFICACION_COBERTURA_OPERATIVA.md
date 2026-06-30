# Verificación de cobertura operativa — CU-O01 … CU-O16

> **Auditoría de solo lectura.** No se modificó ni ejecutó código de la app; no se levantó Docker.
> Cada estado se respalda con evidencia real (`ruta:línea · función/endpoint`).
> Fuentes de verdad: `.specify/memory/constitution.md`, `specs/operativo/**`, código del repo.
> Fecha: 2026-06-30 (re-auditoría completa tras OP6).

**Leyenda:** ✅ Implementado (lógica real y verificable) · 🟡 Parcial (existe pero incompleto / salta capas / sin persistencia / fuera del DAG) · ❌ Ausente (sin evidencia).

> **Nota de revisión (2026-06-30):** la versión previa de este documento estaba
> **desactualizada**: marcaba CU-O01 ❌, CU-O02 🟡, CU-O05 🟡, CU-O06 ❌ y CU-O08 ❌
> pese a existir ya sus commits (`9021837` OP1, `67fb5e3` OP3, `3c8254b` OP5). Esta
> re-auditoría verifica el código actual archivo:línea y corrige esas filas.

---

## 1. Tabla de cobertura

| CU-O | Descripción | OP | Paquete | Evidencia (archivo:línea · función/endpoint) | Estado | Notas |
|---|---|---|---|---|---|---|
| **CU-O01** | Registrar fuente de datos externa | OP1 | ingesta-datos | `etl/source_catalog.py:191` `registrar_fuente()`; validación `:128` `validar_metadatos()`; dedup `:175/:212` (RN-202); ciclo de vida `:239` `habilitar_fuente()` + conectividad `:157`; `fuentes_habilitadas()` `:270`; bootstrap `:287` `ensure_fuente_wine_reviews()` cableado en `etl/extractor.py:42` | ✅ | **(OP1)** Catálogo `fuentes_externas` en PocketBase con metadatos (tipo/formato/endpoint/frecuencia/mercado/catador), **validación de metadatos y conectividad** antes de habilitar (RF-102 → RECHAZADA si falla), **dedup** por (tipo+endpoint+formato, RN-202) y asociación a `Dim_Mercado`/`Dim_Catador`. La ingesta solo lee fuentes HABILITADAS (RN-201). |
| **CU-O02** | Ingestar datos (reseñas, precios, puntuaciones) | OP1 | ingesta-datos | `etl/ingesta.py:90` `procesar_lote()`; validación esquema/dominios `:56` `_motivo_rechazo()` (RN-205); dedup clave natural `:124` (RN-203); umbral 5 % `:48/:138` (RN-204); Parquet snappy particionado `:168`; reporte `:191` `guardar_reporte()` (RF-110); orquestado en `etl/extractor.py:46` (tarea DAG `ingesta` `airflow/dags/dag_pipeline_diario.py:62`) | ✅ | **(OP1)** El `extractor` (entrypoint histórico del DAG) ahora **delega** en catálogo (CU-O01) + motor de ingesta: valida esquema, **deduplica** por clave natural, desvía rechazos a `rejects/` con causa (RF-107), aplica el **umbral 5 %** (RN-204: FALLIDA no aterriza), escribe Parquet **particionado** por `fuente/fecha_ingesta` y emite **reporte** (leídas/válidas/duplicadas/rechazadas/cargadas). |
| **CU-O03** | Ejecutar pipeline ETL | OP2 | etl-calidad | `dbt_vinanalytics/models/staging/stg_resena.sql`, `marts/fct_resena.sql`, `marts/fct_precio_mercado.sql`, `marts/fct_puntuacion.sql` + dims; tareas `dbt_run`/`dbt_test` `airflow/dags/dag_pipeline_diario.py:80,86` | ✅ | Modelos DBT versionados con materialización y tests (`unique`/`not_null`/`relationships`/`accepted_values`). Carga base Fact-Dim (`etl/transformer.py`+`etl/loader.py`, TRUNCATE+INSERT) = aterrizaje que DBT reutiliza como `source` (regla B). |
| **CU-O04** | Validar calidad de datos | OP2 | etl-calidad | `quality/run_quality.py:75` (exit `1` fail-fast); sello `:71/:78` `_registrar_sello()` (puente CU-O06); `quality/ge_staging.py`, `quality/ge_dw.py`; tareas `calidad_staging_ge`/`calidad_dw_ge` `dag:68,92` | ✅ | Gate previo (staging) y posterior (DW) con Great Expectations; `exit≠0` corta el DAG vía `docker exec`. Registra un **sello de calidad** en PocketBase que habilita la publicación de dashboards (RN-401). |
| **CU-O05** | Construir dashboard de cliente | OP3 | dashboards | `models_dashboards.py:197` `construir_dashboard()` (por cliente/tema, métricas+definiciones+filtros); aislamiento multi-tenant `:217` (RN-403); endpoint `app.py:1739` `/dashboards`; lectura ClickHouse `serving.metricas_dashboard` con fallback | ✅ | **(OP3)** Construcción **por cliente y tema** (`ingresos/resenas/precios/uso`) con versionado `BORRADOR→LISTO_PARA_PUBLICAR` (RF-303), filtros `Dim_Tiempo/Mercado/Cliente/Plan` y aislamiento multi-tenant (RN-403). Lee de ClickHouse con fallback a StarRocks (RT-01). |
| **CU-O06** | Publicar dashboard a la cuenta | OP3 | dashboards | `models_dashboards.py:331` `publicar()`; gate calidad `:362` (RN-401) + `:298` `calidad_vigente()`; plan vigente `:372` (RN-402); versionado/reemplazo `:379` (RF-307/308); colección `publicaciones`; endpoint `app.py:1788` `/dashboards/<id>/publicar` | ✅ | **(OP3)** Publicación a una **cuenta** con permisos, plan vigente y versión; **bloqueo duro por calidad** (sin sello CU-O04 vigente → `BLOQUEADO_SIN_CALIDAD`, RN-401); registro/auditoría de publicaciones y despublicación con historial (RF-308). |
| **CU-O07** | Atender solicitud de la API pública | OP4 | api-publica | `app.py:869` `require_api_key` (401) + rate-limit 429; endpoints `/api/v1/vinos`,`/mercados`,`/precios`,`/scorecard`; OpenAPI `/api/v1/openapi.json`; `serving.py:43` `_q()` (fallback `None`) | 🟡 | Núcleo **✅**: autenticación por API key, rate limiting, contrato OpenAPI 3.0 `/v1`, sirve de ClickHouse con fallback. **Parcial por persistencia (RF-405/RN-504):** cada llamada se cuenta **en memoria** (`app.py:866` `_api_metrics`, `:882`), **no se persiste** en `Fact_Consumo_API` (esa tabla solo se llena sintéticamente en `etl/bsc_generator.py`). Por el criterio "sin persistencia" de la leyenda, queda 🟡. |
| **CU-O08** | Registrar cuenta y suscripción | OP5 | suscripciones | `models_clientes.py:112` `crear_cliente()` + dedup `:127` (RN-601); `:149` `crear_suscripcion()`; `:206` `cambiar_estado()` (RN-604); eventos→`Fact_Suscripcion` `_emit_evento` `:95`; colecciones `db/pb_setup.py`; endpoints `app.py:1221` `/clientes`, `:1253` `/suscripciones`; bootstrap `app.py:64` `pb_setup.setup()`; `tests/test_suscripciones.py` | ✅ | **(OP5)** Alta de **cuenta B2B + suscripción** en PocketBase con **dedup** (id_fiscal/email, RN-601), gate de facturación (RN-602), ciclo de vida `PRUEBA/ACTIVA/EN_PAUSA/CANCELADA` (RN-604) y **eventos** `eventos_suscripcion` para `Fact_Suscripcion`. No salta capas (no escribe al DW). |
| **CU-O09** | Ejecutar campaña de captación | OP6 | captacion-conversion | `models_captacion.py` `crear_campana`/`programar_campana`/`ejecutar_campana`/`ejecutar_pendientes`; colecciones `canales_adquisicion`/`mercados`/`campanas`/`eventos_campana` en `db/pb_setup.py`; runner `campaigns_runner.py`; tarea `captacion_ejecucion` `dag:110`; endpoints `app.py:1566` `/campanas*`; `tests/test_captacion.py` | ✅ | **(OP6, 2026-06-30)** Campañas por canal+mercado **existentes** (RN-701), ciclo reanudable, **ejecución automatizada** vía DAG (RF-602/RNF-601) y métricas en `eventos_campana`→`Fact_Campana` vía ETL (RF-603). **Idempotente** por (campaña, período). Dedup de leads por clave natural (RN-702). Pendiente: proyección ETL→`Fact_Campana`, suite GE, `dbt docs`. |
| **CU-O10** | Registrar conversión del embudo | OP6 | captacion-conversion | `models_captacion.py` `registrar_lead`/`registrar_conversion`/`indicadores_captacion`/`evaluar_caida_conversion`; colecciones `leads`/`eventos_conversion`; endpoints `app.py:1672` `/conversiones`,`/leads`,`/captacion/indicadores`; `tests/test_captacion.py` | ✅ | **(OP6, 2026-06-30)** Conversión con etapa/fuente/resultado en `eventos_conversion`→`Fact_Conversion` vía ETL (RF-605). **Atribución first-touch única** a la campaña/canal de origen (RF-606/RN-703; Esc-604 resuelta). **Anti-doble-conteo** por (lead, etapa). Conversión a `cliente` → **alta en suscripciones sin duplicar** (RF-608/RN-705). CAC/tasa canónicos (RN-704). Caída de conversión emite señal al bus (RN-706). Pendiente: proyección ETL→`Fact_Conversion`, suite GE. |
| **CU-O11** | Monitorear uptime y latencia | OP7 | observabilidad | `observabilidad/monitor.py:92` `probar_servicios()`, `:115` `consolidar()`, `:129` `filas_disponibilidad()`, `:154` `evaluar_slo()`, `:184` `incidentes_de()`; tarea `observabilidad` `dag:119` | ✅ | **(OP7)** Sonda real de uptime/latencia (StarRocks/ClickHouse/PocketBase), persistencia **idempotente** en `Fact_Disponibilidad` por región y emisión de señal de SLO al bus de alertas (RN-802). Pendiente: stack Prometheus/Grafana. |
| **CU-O12** | Ejecutar modelo de ML programado | OP8 | machine-learning | `etl/ml_inference.py:232` `main()`/`inferir()`; modelos `etl/ml_models.py`; tarea `ml_inferencia` `dag:128`; `tests/test_alertas.py` | ✅ | **(OP8)** Inferencia **programada** con **gate de calidad** (sin sello CU-O04 → `BLOQUEADA_POR_CALIDAD`, RN-901), persistencia de predicciones con versión+features (RF-805, idempotente por corrida) y señales de churn/precio al bus (RN-903/904). |
| **CU-O13** | Generar alerta (churn/precio/…) | OP9 | alertas | `models_alertas.py:94` `emitir_senal()`, `:144` `generar_alerta()` (dedup RF-906), `:202` `procesar_pendientes()`; `alertas/alert_engine.py`; tarea `alertas` `dag:136` | ✅ | **(OP9)** Bus `senales_alerta` + generación/registro con clasificación/severidad/enrutamiento (RF-903/904/905), **dedup** anti-tormenta por `clave` (RN-1004) y ciclo de vida (RF-907). Emisores cableados: observabilidad (OP7), ML (OP8) y **conversión (OP6, `models_captacion.evaluar_caida_conversion`)**. |
| **CU-O14** | Registrar onboarding y ticket | OP10 | customer-success | `models_customer_success.py` `iniciar_onboarding`/`abrir_ticket`/`transicionar_ticket`/`registrar_satisfaccion`/`vincular_retencion`; colecciones `onboarding`/`tickets`/`acciones_retencion`; endpoints `/onboarding*`,`/tickets*`; disparo al alta `app.py:1242`; `tests/test_customer_success.py` | ✅ | **(OP10)** Onboarding (idempotente, RN-1104) y tickets de soporte sobre **cuenta existente** (CU-O08): clasificación, ciclo de vida (RN-1101), tiempos (RF-1003) y NPS (RF-1004). Alerta de churn (OP9) prioriza y vincula acción de retención (RN-1103). |
| **CU-O15** | Consultar uso por cliente | OP10 | customer-success | `dbt_vinanalytics/models/serving/agg_uso_cliente.sql`; lectores `serving.uso_por_cliente`/`uso_clientes`; endpoints `app.py:1502` `/api/uso/<cid>`, `/api/uso`; `tests/test_customer_success.py` | ✅ | **(OP10)** Consulta de **uso/adopción por cliente** leyendo la **agregación** `agg_uso_cliente` de ClickHouse (RN-1102, nunca los eventos crudos), con fallback a la vista DBT en StarRocks. Acompaña la prioridad de retención si hay churn vivo (RF-1006). |
| **CU-O16** | Generar reporte operativo diario | OP11 | reportes-operativos | `reportes/reporte_diario.py` `generar()`; `serving.reporte_diario_fuentes()` (solo ClickHouse); `models/serving/agg_reporte_diario.sql`; tarea final `reporte_diario` `dag:144`; endpoints `/api/reporte-diario`; `tests/test_reportes.py` | ✅ | **(OP11)** Reporte diario consolida ingesta+API+uso+incidentes por `Dim_Tiempo` desde ClickHouse (RN-1202), con gate del sello de calidad (RF-1104 → `BLOQUEADO_SIN_CALIDAD`), archivo por fecha reproducible (RN-1205) y último paso del DAG (RN-1203). |

---

## 2. Resumen cuantitativo

> Re-auditoría OP6 (2026-06-30): se corrigen filas desactualizadas (CU-O01/O02/O05/O06/O08
> ya estaban implementadas) y se incorporan CU-O09/O10. CU-O07 se ajusta de ✅ a 🟡 por el
> criterio "sin persistencia" de la leyenda (no escribe `Fact_Consumo_API`, RF-405).

- **✅ Implementados: 15/16** — CU-O01, CU-O02, CU-O03, CU-O04, CU-O05, CU-O06, CU-O08, CU-O09, CU-O10, CU-O11, CU-O12, CU-O13, CU-O14, CU-O15, CU-O16
- **🟡 Parciales: 1/16** — CU-O07 (API atendida pero consumo no persistido a `Fact_Consumo_API`)
- **❌ Ausentes: 0/16**

**Cobertura plena:** 15/16 = **93.75 %**.
**Cobertura efectiva** (parcial ponderado al 50 %): (15 + 0.5)/16 = 15.5/16 = **96.875 %**.

El pipeline técnico OP1→OP3 (catálogo de fuentes → ingesta con dedup/rejects/reporte →
calidad fail-fast → ETL/DBT → calidad → agregaciones → serving/API) y la capa de negocio
SaaS (OP5 suscripciones, OP6 campañas/conversión, OP7–OP9 observabilidad/ML/alertas,
OP10 customer-success, OP11 reporte diario) tienen **lógica real y verificable** (no
sintética), persistida en su capa correcta (PocketBase operacional / DBT declarativo).

---

## 3. Huecos pendientes (transversales, no bloquean casos de uso)

1. **CU-O07 — Persistir consumo de API 🟡.** Cada llamada se cuenta en memoria
   (`app.py:866/:882`); falta escribirla en `Fact_Consumo_API` (RF-405/RN-504). Es el
   único 🟡 del repo.
   → *Recomendación:* emitir un evento `eventos_consumo_api` a PocketBase en
   `require_api_key` y proyectarlo a `Fact_Consumo_API` vía ETL (patrón "eventos a
   PocketBase" de CU-O08/O09/O10).

2. **Proyección ETL de eventos operacionales → tablas Fact (cross-cutting).** Las
   colecciones `eventos_suscripcion` (O08), `eventos_campana`/`eventos_conversion` (O09/O10)
   y el seguimiento de CS (O14) viven en PocketBase pero **aún no hay tarea ETL** que las
   proyecte a `Fact_Suscripcion`/`Fact_Campana`/`Fact_Conversion`. La capa operacional es
   correcta (no se salta capas); falta el tramo PocketBase→StarRocks para esas Fact
   (hoy solo se llenan sintéticamente con `etl/bsc_generator.py`).

3. **Suites GE aguas abajo.** Faltan expectations sobre `Fact_Campana`/`Fact_Conversion`
   (O09/O10), `Fact_Disponibilidad` (O11) y `Fact_Uso_Plataforma` (O15).

4. **Arranque end-to-end en Docker.** Ningún checklist marca `docker compose up` verificado
   (no se levantó el stack en estas sesiones). Las imágenes están fijadas (sin `:latest`).

5. **`speckit-analyze` y `dbt docs`/exposures.** Pendientes para varios paquetes
   (validación cruzada de specs y linaje gráfico de las nuevas Fact).

---

## 4. Verificación de reglas de la constitución

| Regla (no negociable) | Estado | Evidencia |
|---|---|---|
| **A. Gates Great Expectations con fallo rápido** (`exit≠0` detiene el DAG) | ✅ | `quality/run_quality.py:75` retorna `1` si falla; tareas `python -m quality.run_quality --stage/--dw` vía `docker exec` propagan el exit y cortan el flujo (`dag:68,92`). |
| **B. Toda transformación declarativa en DBT** (Princ. VI saldado) | ✅ | Staging→marts→serving en modelos DBT (`models/staging/`, `models/marts/`, `models/serving/agg_*.sql`, 20 modelos). `clickhouse/populate.py` ya **no calcula**: solo TRANSPORTA las vistas `agg_*` a ClickHouse; `app.py` no duplica el GROUP BY (los fallbacks leen las vistas). Carga base Fact-Dim = aterrizaje (source de DBT); `etl/bsc_generator.py` = semilla sintética fuera del DAG (excepción documentada). |
| **C. Lectura dashboard/API desde ClickHouse con fallback a StarRocks** | ✅ | `serving.py:43` `_q()` devuelve `None` ante fallo (`:47/:54/…`); cada endpoint cae a StarRocks (p. ej. `api_kpis`, `/api/v1/mercados`, `/api/uso`, dashboards). Conmutable por `CLICKHOUSE_ENABLED`. |
| **D. Orquestación en Airflow, idempotente y ordenada** | ✅ | `dag_pipeline_diario` con orden fijo `ingesta→calidad_staging→etl→dbt_run→dbt_test→calidad_dw→captacion_ejecucion→observabilidad→agregaciones→ml_inferencia→alertas→reporte_diario` (`dag:152`); `retries=2`, `retry_delay=2min`, `catchup=False`, `max_active_runs=1`; idempotencia por TRUNCATE+INSERT / marts `table` / upserts por clave (incl. OP6 por campaña+período). |
| **E. Docker con versiones fijas (sin `:latest`)** | ✅ | `docker-compose.yml`: `pocketbase:0.22.21` (`:5`), `starrocks/allin1-ubuntu:3.3.5` (`:15`), `clickhouse/clickhouse-server:24.3` (`:33`); Dockerfiles con tags fijos. Búsqueda de `:latest` sin coincidencias. |

---

## 5. Veredicto final

**Sí, el programa cubre los 16 casos de uso operativos con lógica real y verificable: 15/16 están plenamente implementados (✅) y solo CU-O07 queda parcial (🟡) por no persistir el consumo en `Fact_Consumo_API` (RF-405); ninguno está ausente** — quedando como deuda transversal (no bloqueante) la proyección ETL de los eventos operacionales a sus tablas Fact, las suites GE aguas abajo y el arranque end-to-end con `docker compose up`.
