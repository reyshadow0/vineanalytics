# machine-learning · Tareas (speckit-tasks)

> Paquete: `machine-learning` · OP8 · CU-O12. Tareas atómicas ordenadas por
> dependencia. Marca `[x]` al completar. Citan RF/RN/CA de
> [machine-learning-spec.md](machine-learning-spec.md).

---

## A. CU-O12 — Ejecutar modelo de ML programado (churn/precio)

- [ ] **T-01** Definir el contrato de features y el registro de modelos vigentes (versión + artefacto). *(RF-802, RF-805)*
- [ ] **T-02** Implementar el gate de calidad: inferir solo sobre DW validado por CU-O04. *(RN-901)*
- [ ] **T-03** Implementar la lectura de features desde StarRocks. *(RF-802, RT-01)*
- [ ] **T-04** Implementar el runner de **churn** (probabilidad + nivel de riesgo por `Dim_Cliente`). *(RF-803)*
- [ ] **T-05** Implementar el runner de **precios** (precio recomendado + tendencia por `Dim_Mercado`/`Dim_Vino`). *(RF-804)*
- [ ] **T-06** Persistir predicciones con versión de modelo y fecha. *(RF-805, RN-902)*
- [ ] **T-07** Exponer predicciones a dashboards (DW→ClickHouse) y a `alertas`. *(RF-806, RN-905)*
- [ ] **T-08** Registrar métricas de la corrida (registros, duración, distribución de scores). *(RF-807)*
- [ ] **T-09** Garantizar idempotencia de la corrida. *(RNF-802)*

## B. Alertas y pruebas (incluye casos de error)

- [ ] **T-10** Emitir alerta ante churn sobre umbral (acción de retención en OP10). *(RN-903)*
- [ ] **T-11** Emitir alerta ante precio recomendado fuera de rango. *(RN-904)*
- [ ] **T-12** Prueba: inferencia de churn produce probabilidad/riesgo con versión. *(CA-801, Esc-801)*
- [ ] **T-13** Prueba: inferencia de precios produce recomendación por mercado/vino. *(CA-802, Esc-802)*
- [ ] **T-14** Prueba: DW sin calidad → corrida `BLOQUEADA_POR_CALIDAD`. *(CA-803, Esc-803)*
- [ ] **T-15** Prueba: churn alto y precio anómalo disparan alerta. *(CA-804, Esc-804, Esc-805)*
- [ ] **T-16** Prueba: reejecución idempotente sin duplicar predicciones. *(CA-806, Esc-806)*

## C. Orquestación, contenedores y cierre

- [ ] **T-17** Programar el DAG de inferencia en Airflow (ventana batch). *(RNF-803)*
- [ ] **T-18** Confirmar que el paquete **no entrena** (solo ejecuta el modelo vigente). *(RN-906)*
- [ ] **T-19** Contenedorizar el runner en `docker-compose.yml` (versión fija). *(RNF-801, RT-17)*
- [ ] **T-20** Verificar arranque con `docker compose up`. *(RT-17)*
- [ ] **T-21** Validar spec contra constitución y completar [checklist.md](checklist.md). *(RT-18, RT-19)*
