# machine-learning · Checklist — Definición de Terminado (speckit-checklist)

> Paquete: `machine-learning` · OP8 · CU-O12. No se integra hasta marcar todos los
> ítems. Verifica contra [machine-learning-spec.md](machine-learning-spec.md) y la
> [constitución](../../../.specify/memory/constitution.md).

---

## 1. Spec y trazabilidad (obligatorio)

- [ ] Spec validado contra la constitución sin conflictos. *(RT-18)*
- [ ] Bloque de trazabilidad completo: OP8, OT8/OE4, CU-O12. *(RT-19)*
- [ ] Historias de usuario y modelo Fact-Dim (`Fact_Retencion`, `Fact_Precio_Mercado`, `Dim_Cliente`) declarados. *(Princ. IV)*
- [ ] `speckit-analyze` sin inconsistencias con `000-general`, `etl-calidad`, `alertas`, `customer-success`.

## 2. Calidad y alcance (obligatorio)

- [ ] **Inferencia solo sobre DW validado por CU-O04** (features no sucias). *(Princ. V, RN-901, RNF-804)*
- [ ] Cada predicción registra **versión de modelo** y fecha. *(RN-902, RF-805)*
- [ ] Confirmado que el paquete **no entrena** (entrenamiento es CU-T08, táctico). *(RN-906)*

## 3. Capas y serving (obligatorio)

- [ ] Features leídas de **StarRocks**; predicciones servidas a dashboards **solo vía ClickHouse**. *(RT-01, RT-02, RN-905)*
- [ ] Linaje de features y predicciones documentado en `dbt docs`. *(Princ. VII, RT-14)*

## 4. Orquestación y reproducibilidad (obligatorio)

- [ ] Inferencia programada como DAG **Airflow** idempotente. *(Princ. IX, RNF-803, RNF-802)*
- [ ] **`docker compose up` levanta** el runner de ML; imagen con versión fija. *(Princ. VIII, RT-17)*

## 5. Funcionalidad (criterios de aceptación)

- [ ] CA-801 churn → probabilidad/riesgo con versión.
- [ ] CA-802 precios → recomendación por mercado/vino.
- [ ] CA-803 sin DW validado, corrida bloqueada.
- [ ] CA-804 churn alto / precio anómalo disparan alerta.
- [ ] CA-805 predicciones servidas vía ClickHouse.
- [ ] CA-806 reejecución idempotente.

## 6. Observabilidad y alertas

- [ ] Eventos de churn alto / precio anómalo llegan a `alertas` (OP9). *(RN-903, RN-904, RT-16)*
- [ ] Métricas de corrida expuestas a `observabilidad` (OP7). *(RF-807)*
