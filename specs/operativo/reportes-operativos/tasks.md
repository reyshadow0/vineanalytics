# reportes-operativos · Tareas (speckit-tasks)

> Paquete: `reportes-operativos` · OP11 · CU-O16. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [reportes-operativos-spec.md](reportes-operativos-spec.md).
>
> **Estado (2026-06-29):** CU-O16 implementado. Evidencia entre paréntesis.

---

## A. CU-O16 — Generar reporte operativo diario

- [x] **T-01** Contenido y formato del reporte (secciones: ingesta, API, uso, incidentes). *(RF-1101, RF-1105)* — `reportes/reporte_diario.py::consolidar` + `TRAZABILIDAD`.
- [x] **T-02** Conectar el generador a ClickHouse en modo solo lectura. *(RF-1102, RN-1202)* — `serving.reporte_diario_fuentes()` (solo ClickHouse, sin fallback).
- [x] **T-03** Gate de calidad del día (verificar sello CU-O04). *(RF-1104, RN-1201)* — `reporte_diario._gate_calidad` → `models_dashboards.calidad_vigente`.
- [x] **T-04** Consolidación de métricas por `Dim_Tiempo` (`Fact_Uso_Plataforma`, `Fact_Consumo_API`, incidentes, alertas). *(RF-1101)* — modelo DBT `serving/agg_reporte_diario.sql`.
- [x] **T-05** Generación automática al cierre del DAG (último paso). *(RF-1103, RN-1203)* — tarea `reporte_diario` en `airflow/dags/dag_pipeline_diario.py`.
- [x] **T-06** Archivado por fecha y reproducibilidad. *(RF-1105, RN-1205)* — `reporte_diario.archivar` → `reportes/archivo/reporte_diario_<fecha>.json`; `consolidar` determinista.
- [x] **T-07** Trazabilidad de cada cifra a su agregación de origen. *(RN-1204)* — campo `trazabilidad` por sección (test `test_trazabilidad_por_seccion`).
- [x] **T-08** Reporte disponible como insumo para consolidación mensual/estratégica. *(RF-1106)* — JSON archivado + registro PocketBase `reportes_operativos` (`models_reportes`).

## B. Pruebas (incluye casos de error)

- [x] **T-09** Reporte nominal se genera al cierre del DAG desde ClickHouse y se archiva. *(CA-1201, CA-1202, Esc-1201)* — `tests/test_reportes.py::test_reporte_nominal_publicado_con_cifras`, `::test_archiva_por_fecha`.
- [x] **T-10** Día con calidad fallida → `BLOQUEADO_SIN_CALIDAD`, sin reporte definitivo. *(CA-1203, Esc-1202)* — `::test_sin_sello_calidad_queda_bloqueado`, `::test_ultima_calidad_fallida_bloquea`, `::test_sello_vencido_bloquea`.
- [x] **T-11** Intento de calcular desde StarRocks/PocketBase es rechazado. *(Esc-1203, RN-1202)* — lectura solo-ClickHouse: sin agregaciones → `FALLIDO` (no se lee otra capa). `::test_sin_agregaciones_clickhouse_es_fallido`.
- [x] **T-12** Cifra inconsistente con ClickHouse se detecta por trazabilidad. *(Esc-1204, RN-1204)* — `trazabilidad` enlaza cada sección a su agregación/Fact. `::test_trazabilidad_por_seccion`.
- [x] **T-13** Regenerar el reporte de una fecha produce las mismas cifras. *(CA-1205, Esc-1205)* — `consolidar` determinista. `::test_reproducibilidad_cifras_identicas`.

## C. Orquestación, contenedores y cierre

- [x] **T-14** Tarea de reporte como **último paso** del `dag_pipeline_diario`. *(RN-1203, RT-03)* — `... >> agregaciones >> reporte_diario`.
- [x] **T-15** Evento de generación (éxito/fallo) a `observabilidad`/`alertas`. *(salidas §8)* — `reporte_diario._emitir_evento` (log `[INFO]/[ALERTA]`) + registro PocketBase.
- [x] **T-16** Contenedorizar el generador (versión fija). *(RNF-1103, RT-17)* — corre en el contenedor `runner` (imagen fija `runner/Dockerfile`, bind `.:/app`); no requiere imagen nueva.
- [ ] **T-17** Verificar arranque con `docker compose up`. *(RT-17)* — **pendiente**: requiere Docker (este entorno no lo levanta; ver nota de la auditoría). Validado a nivel de código/compilación.
- [x] **T-18** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
