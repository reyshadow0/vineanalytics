# reportes-operativos · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `reportes-operativos` · OP11 · CU-O16. No se integra hasta marcar todos los
> ítems. Verifica contra
> [reportes-operativos-spec.md](reportes-operativos-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).
>
> **Estado (2026-06-29):** completo salvo el arranque Docker (requiere entorno
> con contenedores). Evidencia entre paréntesis.

---

## 1. Spec y trazabilidad (obligatorio)

- [x] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [x] Bloque de trazabilidad completo: OP11, OT7/OE4, CU-O16. *(RT-19)* — cabecera del spec.
- [x] Historias de usuario y modelo Fact-Dim (`Fact_Uso_Plataforma`, `Fact_Consumo_API`, `Dim_Tiempo`) declarados. *(Princ. IV)*
- [x] Consistencia con `000-general`, `etl-calidad`, paquetes fuente — lee del sello CU-O04 (`etl-calidad`) y de las agregaciones del pipeline.

## 2. Regla crítica de negocio (obligatorio)

- [x] **El reporte se construye solo sobre datos validados por calidad (CU-O04)**; día sin calidad → bloqueado. *(Princ. X, RT-15, RN-1201)* — `_gate_calidad`/`calidad_vigente`.
- [x] Verificado el bloqueo `BLOQUEADO_SIN_CALIDAD`. *(CA-1203, Esc-1202)* — 3 pruebas (sin sello / sello fallido / sello vencido).

## 3. Capas y trazabilidad de cifras (obligatorio)

- [x] Cifras leídas **solo de ClickHouse** (no StarRocks/PocketBase). *(RT-01, RT-02, RN-1202)* — `serving.reporte_diario_fuentes()` solo ClickHouse; sin agregaciones → `FALLIDO`.
- [x] Cada métrica es trazable a su Fact/agregación de origen. *(RN-1204, RNF-1104)* — campo `trazabilidad` por sección.
- [x] Linaje (`exposure`) del reporte documentado en `dbt docs`. *(Princ. VII, RT-14)* — `models/serving/_exposures.yml::reporte_operativo_diario`.

## 4. Orquestación y reproducibilidad (obligatorio)

- [x] Reporte generado como **último paso** del `dag_pipeline_diario`. *(Princ. IX, RN-1203, RT-03)* — `agregaciones >> reporte_diario`.
- [x] Reporte archivado por fecha y reproducible. *(RN-1205, RNF-1105)* — `archivar()` + `consolidar()` determinista.
- [~] **`docker compose up` levanta** el generador; imagen con versión fija. *(Princ. VIII, RT-17)* — corre en el `runner` (imagen fija); arranque end-to-end **pendiente de Docker**.

## 5. Funcionalidad (criterios de aceptación)

- [x] CA-1201 reporte consolida ingesta/API/uso/incidentes por `Dim_Tiempo`. — `agg_reporte_diario` + `consolidar`.
- [x] CA-1202 generación automática al cierre del DAG. — tarea `reporte_diario`.
- [x] CA-1203 sin calidad del día → bloqueado.
- [x] CA-1204 cifras solo de ClickHouse y trazables.
- [x] CA-1205 archivado por fecha y reproducible.

## 6. Observabilidad y alcance

- [x] Evento de generación (éxito/fallo) expuesto a `observabilidad`/`alertas`. *(§8)* — `_emitir_evento` (`[INFO]/[ALERTA]`).
- [x] Confirmado que reportes mensuales/estratégicos quedan **fuera** del alcance operativo. *(§13)* — solo reporte diario; insumo para niveles superiores.

---

## 7. Principio VI — refactor del SQL imperativo (deuda técnica saldada)

> Regla B de [VERIFICACION_COBERTURA_OPERATIVA.md](../../../VERIFICACION_COBERTURA_OPERATIVA.md).

- [x] Agregaciones de serving movidas a modelos DBT declarativos (`models/serving/agg_*.sql`) con tests (`_schema.yml`).
- [x] `clickhouse/populate.py` ya **no** calcula agregaciones: solo TRANSPORTA las vistas DBT a ClickHouse (TRUNCATE+INSERT, idempotente).
- [x] `app.py` ya **no** duplica la lógica de agregación: los fallbacks leen las vistas `agg_*` de StarRocks; el formateo de tarjetas BSC vive una sola vez en `serving.bsc_kpis_payload`/`bsc_series_payload`.
- [x] Resultados sin cambios: el SQL movido conserva las mismas expresiones/guardas/redondeos (ver tabla antes/después en la entrega de la sesión).
- [~] Validación `dbt run`/`dbt test` sobre StarRocks **pendiente de Docker** (no se levanta en este entorno; los modelos compilan estructuralmente y reutilizan el patrón de los marts existentes).
