# machine-learning · Tareas (speckit-tasks)

> Paquete: `machine-learning` · OP8 · CU-O12. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [machine-learning-spec.md](machine-learning-spec.md).

> **Sesión OP7/OP8/OP9 (2026-06-29).** Implementado `etl/ml_inference.py`: corrida
> programada que aplica un gate de calidad (sello CU-O04), reutiliza los modelos
> explicables de `etl/ml_models.py` (churn + precios), persiste predicciones con
> **versión de modelo + features + score** en PocketBase (`predicciones_ml`,
> idempotente por corrida+entidad) y **emite señales** a `alertas` ante churn alto
> (RN-903) y precio anómalo (RN-904). Tarea `ml_inferencia` en `dag_pipeline_diario`
> (tras el gate del DW). Cubierto por `tests/test_alertas.py`. Pendiente: arranque
> end-to-end en Docker.

---

## A. CU-O12 — Ejecutar modelo de ML programado (churn/precio)

- [x] **T-01** Definir el contrato de features y el registro de modelos vigentes (versión + artefacto). *(RF-802, RF-805)* — `VERSION_CHURN`/`VERSION_PRECIO` + features serializadas por predicción.
- [x] **T-02** Implementar el gate de calidad: inferir solo sobre DW validado por CU-O04. *(RN-901)* — `inferir()` usa `models_dashboards.calidad_vigente` → `BLOQUEADA_POR_CALIDAD`.
- [x] **T-03** Implementar la lectura de features desde StarRocks. *(RF-802, RT-01)* — `etl/ml_models.py` (`predecir_churn`/`precios_dinamicos`).
- [x] **T-04** Implementar el runner de **churn** (probabilidad + nivel de riesgo por `Dim_Cliente`). *(RF-803)* — `churn_predicciones()`.
- [x] **T-05** Implementar el runner de **precios** (precio recomendado + tendencia por `Dim_Mercado`/`Dim_Vino`). *(RF-804)* — `precio_predicciones()`.
- [x] **T-06** Persistir predicciones con versión de modelo y fecha. *(RF-805, RN-902)* — `_persistir_predicciones()` (colección `predicciones_ml`).
- [x] **T-07** Exponer predicciones a dashboards (DW→ClickHouse) y a `alertas`. *(RF-806, RN-905)* — señales a `alertas`; dashboards leen vía ClickHouse (RN-905; predicciones no escriben serving directo).
- [x] **T-08** Registrar métricas de la corrida (registros, duración, distribución de scores). *(RF-807)* — `metricas` en el reporte de `inferir()`.
- [x] **T-09** Garantizar idempotencia de la corrida. *(RNF-802)* — corrida determinista + upsert por (corrida, id_entidad).

## B. Alertas y pruebas (incluye casos de error)

- [x] **T-10** Emitir alerta ante churn sobre umbral (acción de retención en OP10). *(RN-903)* — señal `churn`/critical → Customer Success.
- [x] **T-11** Emitir alerta ante precio recomendado fuera de rango. *(RN-904)* — señal `precio` cuando |ajuste| ≥ `UMBRAL_PRECIO_PCT`.
- [x] **T-12** Prueba: inferencia de churn produce probabilidad/riesgo con versión. *(CA-801, Esc-801)* — `test_inferencia_persiste_con_version_y_emite_senales`.
- [x] **T-13** Prueba: inferencia de precios produce recomendación por mercado/vino. *(CA-802, Esc-802)* — misma prueba (4 predicciones).
- [x] **T-14** Prueba: DW sin calidad → corrida `BLOQUEADA_POR_CALIDAD`. *(CA-803, Esc-803)* — `test_sin_sello_calidad_bloquea_inferencia`.
- [x] **T-15** Prueba: churn alto y precio anómalo disparan alerta. *(CA-804, Esc-804, Esc-805)* — `test_cadena_churn_y_precio_generan_alerta_y_no_duplican`.
- [x] **T-16** Prueba: reejecución idempotente sin duplicar predicciones. *(CA-806, Esc-806)* — `test_reejecucion_idempotente_no_duplica_predicciones`.

## C. Orquestación, contenedores y cierre

- [x] **T-17** Programar el DAG de inferencia en Airflow (ventana batch). *(RNF-803)* — tarea `ml_inferencia` en `dag_pipeline_diario` (@daily).
- [x] **T-18** Confirmar que el paquete **no entrena** (solo ejecuta el modelo vigente). *(RN-906)* — solo inferencia; los modelos son explicables y vigentes.
- [x] **T-19** Contenedorizar el runner en `docker-compose.yml` (versión fija). *(RNF-801, RT-17)* — corre en el `runner` (imagen fija), como dbt/GE/reporte.
- [ ] **T-20** Verificar arranque con `docker compose up`. *(RT-17)* — pendiente arranque end-to-end.
- [x] **T-21** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
