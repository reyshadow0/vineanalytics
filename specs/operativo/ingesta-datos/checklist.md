# ingesta-datos · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `ingesta-datos` · OP1 · CU-O01, CU-O02. El paquete **no se integra**
> hasta marcar todos los ítems. Verifica contra
> [ingesta-datos-spec.md](ingesta-datos-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

> **Estado de esta iteración (2026-06-29):** implementados CU-O01 y CU-O02.
> Evidencia de código y pruebas offline (sin Docker) en `tests/test_ingesta.py`
> (`python -m tests.test_ingesta` → todas OK). Los ítems que dependen del stack
> vivo (GE/DBT/`docker compose up`/`speckit-analyze`) quedan marcados como
> pendientes de ejecución E2E y se anotan explícitamente.

## 1. Spec y trazabilidad (obligatorio)

- [x] Spec validado contra la constitución (Princ. I–X) sin conflictos abiertos. *(RT-18)* — reconciliación documentada de RN-205 (precio>0 aplica a `precios`; en `reseñas` price=0 es sentinela de desconocido, coherente con `quality/ge_staging.py`).
- [x] Bloque de trazabilidad completo: Nivel, Departamento, Paquete, OP1, OT7/OE4, CU-O01/CU-O02. *(RT-19)*
- [x] Cada CU-O del paquete tiene ≥ 1 historia de usuario y su modelo Fact-Dim declarado. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias entre spec, plan, tasks y `000-general`. *(no ejecutado en esta sesión)*

## 2. Calidad de datos (obligatorio)

- [x] Validación de esquema y dominios en el aterrizaje (no-nulos por `tipo`, `puntaje∈[80,100]`, `precio>0` en `precios`, fecha no futura, `moneda` ISO-4217). *(RN-205)* — `etl/ingesta.py::_motivo_rechazo`. La **suite GE profunda** (CU-O04) corre aguas abajo en el DAG sobre el mismo `wine_raw.parquet` (`quality/ge_staging.py`, intacto).
- [x] Fail-fast verificado: un lote con > 5% de rechazos termina `FALLIDA`, no aterriza y emite alerta. *(RN-204, CA-105)* — `procesar_lote` + `_emitir_evento`; prueba `test_cu_o02_umbral_y_parcial`.
- [x] Deduplicación verificada por clave natural en los tres tipos de fuente. *(RN-203)* — claves por `tipo` en `source_catalog.CLAVE_NATURAL_DEFAULT`; `procesar_lote` es agnóstico al tipo; reseñas probado E2E (3→3).

## 3. Transformación y linaje (obligatorio)

- [ ] **Tests DBT pasando** en los modelos de staging que consumen el Parquet — aguas abajo con `etl-calidad`; no ejecutado live en esta sesión. *(Princ. VI)* — **verificado** que el staging generado es consumible por el `Transform` existente (`test_downstream_transformer`).
- [ ] **Linaje documentado**: el staging aparece como `source` en `dbt docs` y se rastrea hasta `Fact_Resena`/`Fact_Precio_Mercado`/`Fact_Puntuacion`. *(Princ. VII, RT-14)* *(sin cambios en linaje; pendiente para precios/puntuaciones)*
- [x] Confirmado que la ingesta **no** transforma a Fact-Dim ni carga StarRocks. *(RN-206, RT-01)* — `ingesta.py`/`source_catalog.py` solo hablan con PocketBase y Parquet.

## 4. Formato y staging (obligatorio)

- [x] Staging escrito en **Parquet snappy**, particionado por `fuente`/`fecha_ingesta`, verificado con pyarrow. *(RNF-101, CA-103)* — `escribir_staging_particionado`; prueba comprueba codec `SNAPPY` y ruta `fuente=.../fecha_ingesta=...`.
- [x] Sin CSV en el flujo de producción. *(RT-04)* — toda salida es `to_parquet(compression="snappy")`.
- [x] Idempotencia verificada: reejecución de una ventana no duplica filas. *(RNF-102, CA-104)* — sobrescritura de partición + dedup; prueba 3→3.

## 5. Orquestación y contenedores (obligatorio)

- [x] Tarea `ingesta` integrada en `dag_pipeline_diario`, **antes** de calidad, con `retries`/`retry_delay`. *(RT-03, CA-107)* — la tarea `ingesta` (`python -m etl.extractor`) ahora ejecuta CU-O01+CU-O02; `retries=2`/`retry_delay=2min` en `default_args`; orden `ingesta >> calidad_staging`.
- [ ] **`docker compose up` levanta** conector + PocketBase + Airflow; imágenes con versión fija (sin `latest`). *(Princ. VIII, RT-17)* — imágenes ya fijadas (audit regla E ✅); la ingesta reutiliza el `runner` existente (no requiere contenedor nuevo). **E2E con stack vivo no ejecutado en esta sesión.**
- [ ] `docker compose config` válido. *(sin cambios en docker-compose.yml)*

## 6. Funcionalidad (criterios de aceptación)

- [x] CA-101 alta válida → fuente `HABILITADA` (= `ACTIVA`) y asociada a su Dim (`mercado`/`catador`). — `test_cu_o01_catalogo`.
- [x] CA-102 alta duplicada rechazada con id existente. — `FuenteDuplicada.detalle.id_existente`.
- [x] CA-103 ingesta produce Parquet snappy particionado.
- [x] CA-104 reejecución idempotente sin filas extra.
- [x] CA-105 lote con > 5% rechazo → `FALLIDA` + alerta.
- [x] CA-106 reporte de ingesta generado por lote. — `guardar_reporte` → `stage/ingesta/_reportes/<fuente>_<fecha>.json`.
- [ ] CA-107 ingesta corre en el DAG dentro de `docker compose up`. — DAG cableado; **E2E con `docker compose up` pendiente en esta sesión.**

## 7. Observabilidad y alertas

- [x] Métricas/logs estructurados emitidos para `observabilidad` (OP7). *(RNF-105)* — `_emitir_evento` imprime el reporte como JSON (`[INFO]`/`[ALERTA]`).
- [x] Evento de fallo de ingesta llega a `alertas` (OP9). *(RT-16)* — en `FALLIDA` se emite línea `[ALERTA]`; el registro/enrutamiento persistente es de CU-O13 (paquete `alertas`).
