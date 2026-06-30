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

- [x] **Inferencia solo sobre DW validado por CU-O04** (features no sucias). *(Princ. V, RN-901, RNF-804)* — gate `calidad_vigente` antes de inferir.
- [x] Cada predicción registra **versión de modelo** y fecha. *(RN-902, RF-805)* — `version_modelo`+`fecha` en `predicciones_ml`.
- [x] Confirmado que el paquete **no entrena** (entrenamiento es CU-T08, táctico). *(RN-906)* — solo aplica modelos vigentes.

## 3. Capas y serving (obligatorio)

- [x] Features leídas de **StarRocks**; predicciones servidas a dashboards **solo vía ClickHouse**. *(RT-01, RT-02, RN-905)* — features de `ml_models` (StarRocks); predicciones no escriben serving del cliente.
- [ ] Linaje de features y predicciones documentado en `dbt docs`. *(Princ. VII, RT-14)* — pendiente `dbt docs`.

## 4. Orquestación y reproducibilidad (obligatorio)

- [x] Inferencia programada como DAG **Airflow** idempotente. *(Princ. IX, RNF-803, RNF-802)* — tarea `ml_inferencia` + upsert por corrida/entidad.
- [ ] **`docker compose up` levanta** el runner de ML; imagen con versión fija. *(Princ. VIII, RT-17)* — corre en el `runner` (imagen fija); falta arranque end-to-end.

## 5. Funcionalidad (criterios de aceptación)

- [x] CA-801 churn → probabilidad/riesgo con versión.
- [x] CA-802 precios → recomendación por mercado/vino.
- [x] CA-803 sin DW validado, corrida bloqueada.
- [x] CA-804 churn alto / precio anómalo disparan alerta.
- [x] CA-805 predicciones servidas vía ClickHouse. — RN-905 respetada (sin escritura directa al serving).
- [x] CA-806 reejecución idempotente.

## 6. Observabilidad y alertas

- [x] Eventos de churn alto / precio anómalo llegan a `alertas` (OP9). *(RN-903, RN-904, RT-16)* — bus `senales_alerta`.
- [x] Métricas de corrida expuestas a `observabilidad` (OP7). *(RF-807)* — `metricas` (registros, duración, distribución) en el reporte de la corrida.
