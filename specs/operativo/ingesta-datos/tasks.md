# ingesta-datos · Tareas (speckit-tasks)

> Paquete: `ingesta-datos` · OP1 · CU-O01, CU-O02. Tareas atómicas, ordenadas por
> dependencia. Marca `[x]` al completar. Cada tarea cita su RF/RN/CA de
> [ingesta-datos-spec.md](ingesta-datos-spec.md).

---

## A. CU-O01 — Registrar fuente de datos externa

- [x] **T-01** Definir y crear la colección PocketBase `fuentes_externas` con los campos del modelo (plan §3). *(RF-101, RF-103)* — `etl/source_catalog.py::ensure_schema`.
- [x] **T-02** Implementar validación de conectividad de la fuente al registrar/habilitar. *(RF-102)* — `_validar_conectividad` (colección PB de origen existe).
- [x] **T-03** Implementar validación de esquema mínimo según `tipo` (reseñas/precios/puntuaciones). *(RF-102)* — `ESQUEMA_MINIMO` + `validar_metadatos`.
- [x] **T-04** Asociar la fuente a `Dim_Mercado` y/o `Dim_Catador_Sumiller`. *(RF-103)* — campos `mercado`/`catador`.
- [x] **T-05** Implementar guardia anti-duplicados (`tipo + endpoint + formato`) que devuelva el id existente. *(RF-104, RN-202, CA-102)* — `registrar_fuente` → `FuenteDuplicada`.
- [x] **T-06** Implementar transiciones de estado de fuente (REGISTRADA→HABILITADA/DESHABILITADA/RECHAZADA). *(§9, RF-105)*
- [x] **T-07** Prueba: alta nominal deja la fuente `HABILITADA` y asociada a su Dim. *(CA-101, Esc-101)* — `tests/test_ingesta.py`.
- [x] **T-08** Prueba: alta duplicada es rechazada con id existente. *(CA-102, Esc-102)*

## B. CU-O02 — Ingestar datos (reseñas, precios, puntuaciones)

- [~] **T-09** Conector base por fuente activa (lee de PocketBase). *(RF-106, RN-201)* — `ingesta.leer_coleccion_pocketbase` + guardia RN-201 en `ingestar_fuente`. **Modo full** (sobrescritura idempotente); el cursor incremental queda pendiente.
- [x] **T-10** Implementar validación de esquema por registro con desvío a `rejects/`. *(RF-107)* — `_motivo_rechazo` + `escribir_rechazos`.
- [x] **T-11** Implementar el cálculo de % de rechazo y el corte por umbral (5% → `FALLIDA`). *(RN-204, CA-105)*
- [x] **T-12** Implementar verificación de dominios mínimos: `precio>0`, `puntaje∈[80,100]`, fecha no futura, `moneda` ISO-4217. *(RN-205)*
- [x] **T-13** Implementar deduplicación por clave natural por tipo de fuente. *(RF-108, RN-203)*
- [x] **T-14** Implementar el escritor **Parquet snappy** particionado por `fuente`/`fecha_ingesta` (pyarrow). *(RF-109, RNF-101, CA-103)*
- [x] **T-15** Garantizar idempotencia: reejecutar la misma ventana no duplica filas. *(RNF-102, RN-203, CA-104)*
- [x] **T-16** Generar el reporte de ingesta (leídas/cargadas/rechazadas/duplicadas/estado). *(RF-110, CA-106)*
- [x] **T-17** Emitir métricas/eventos para `observabilidad` y `alertas`. *(RNF-105, RT-16)* — `_emitir_evento` (`[INFO]`/`[ALERTA]`).
- [x] **T-18** Prueba: ingesta nominal aterriza Parquet snappy particionado y deja lote `COMPLETADA`. *(CA-103, Esc-103)*
- [x] **T-19** Prueba: lote con 2% inválido → `PARCIAL` con `rejects/`; lote con 12% → `FALLIDA` + alerta. *(Esc-104, Esc-105)*
- [x] **T-20** Prueba: reejecución idempotente no incrementa filas en staging. *(CA-104, Esc-106)*

## C. Orquestación, contenedores y cierre

- [x] **T-21** Tarea Airflow `ingesta` en `dag_pipeline_diario`, **antes** de calidad, con `retries`/`retry_delay`. *(RNF-106, RT-03, CA-107)* — la tarea existente ahora ejecuta CU-O01+CU-O02 vía `etl.extractor`.
- [~] **T-22** Manejar fuente caída: reintentos (`retries=2` del DAG) y, al agotarlos, `FALLIDA`. *(Esc-107)* — `extractor` aborta con `exit 1` si PocketBase no responde; la alerta de `FALLIDA` por umbral está cubierta.
- [x] **T-23** Imágenes con versión fija ya presentes; la ingesta reutiliza el `runner` (sin contenedor nuevo). *(RNF-106, RT-17)*
- [ ] **T-24** Verificar arranque con `docker compose up` y ejecución end-to-end de la ingesta. *(CA-107, RT-17)* — **pendiente de stack vivo en esta sesión.**
- [x] **T-25** Validar el spec contra la constitución y actualizar el [checklist.md](checklist.md). *(RT-18, RT-19)*
