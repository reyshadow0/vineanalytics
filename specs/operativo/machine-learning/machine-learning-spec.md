# machine-learning · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Data Science
> - **Paquete:** `machine-learning`
> - **Objetivo operativo (OP):** OP8 — Ejecutar modelos de ML programados.
> - **Objetivos de origen (OT/OE):** OT8 (Desarrollar modelos de ML: churn, precios dinámicos, segmentación) → OE4 (Inteligencia de Negocio Centralizada).
> - **Casos de uso (CU-O):** CU-O12 (Ejecutar modelo de ML programado: churn/precio).
> - **Modelo Fact-Dim que toca (matriz §9.8):** `Fact_Retencion`, `Fact_Precio_Mercado`, `Dim_Cliente`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Ejecutar de forma **programada** los modelos de ML en producción (predicción de
**churn** y de **precios dinámicos**), leyendo features del DW StarRocks, generando
**scores/predicciones** y persistiéndolos para que `alertas` (OP9) y los dashboards
los consuman. Implementa la inferencia operativa de la inteligencia de negocio (OE4).

## 2. Contexto

Es la ejecución operativa (inferencia programada), **no** el entrenamiento/ajuste de
modelos, que es táctico (CU-T08). Lee features desde el DW (`Fact_Retencion`,
`Fact_Uso_Plataforma`, `Fact_Precio_Mercado`, `Dim_Cliente`), aplica el modelo
vigente y escribe predicciones (probabilidad de churn, precio recomendado) que se
proyectan al DW y se sirven en ClickHouse. Las predicciones que cruzan umbrales
disparan alertas (CU-O13). Actor: **Sistema** (orquestado), supervisado por
**Data Science**.

### Historias de usuario

**CU-O12 — Ejecutar modelo de ML programado (churn/precio)**
- HU-01: *Como Data Scientist, quiero ejecutar el modelo de churn programado sobre los
  clientes activos, para obtener su probabilidad de cancelación.*
- HU-02: *Como Data Scientist, quiero ejecutar el modelo de precios dinámicos por
  mercado, para recomendar precios según tendencia y demanda.*
- HU-03: *Como Sistema, quiero registrar features, scores y versión del modelo en cada
  corrida, para trazabilidad y para alimentar alertas y dashboards.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Data Scientist** | Define el modelo en producción, umbrales y features (CU-O12). |
| **Sistema (procesos automáticos)** | Ejecuta la inferencia programada (Airflow). |
| Paquete `etl-calidad` (OP2) | Provee el DW con las features. |
| Paquete `alertas` (OP9) | Consume predicciones que cruzan umbral (churn alto, precio anómalo). |

## 4. Requisitos funcionales

**De CU-O12 (Ejecutar modelo de ML programado):**
- **RF-801** El sistema ejecuta **inferencia programada** (DAG Airflow) de los modelos
  vigentes (churn y precios dinámicos).
- **RF-802** El sistema lee **features** del DW StarRocks (`Fact_Retencion`,
  `Fact_Uso_Plataforma`, `Fact_Precio_Mercado`, `Dim_Cliente`). *(RT-01)*
- **RF-803** El modelo de **churn** produce, por `Dim_Cliente`, una probabilidad de
  cancelación y un nivel de riesgo.
- **RF-804** El modelo de **precios** produce, por `Dim_Mercado`/`Dim_Vino`, un precio
  recomendado y la tendencia.
- **RF-805** El sistema persiste las **predicciones/scores** con la **versión del
  modelo** y la fecha (reproducibilidad).
- **RF-806** El sistema expone las predicciones para `alertas` (umbral) y para los
  dashboards (vía ClickHouse).
- **RF-807** El sistema registra métricas de la corrida (nº de registros, duración,
  distribución de scores).

## 5. Requisitos no funcionales

- **RNF-801 Reproducibilidad:** cada predicción referencia versión de modelo y de
  features; el runner corre en contenedor. *(RT-17)*
- **RNF-802 Idempotencia:** reejecutar una corrida no duplica predicciones. *(RT-11)*
- **RNF-803 Programación:** inferencia en ventana batch (p. ej. diaria) vía Airflow.
- **RNF-804 Calidad de features:** las features provienen de un DW que pasó GE (CU-O04).
- **RNF-805 Madurez:** objetivo ≥ 6 modelos en producción (BSC aprendizaje). *(referencia)*

## 6. Reglas de negocio

- **RN-901** La inferencia solo corre sobre un DW validado por calidad (CU-O04);
  features sucias no se usan. *(RT-05, RNF-804)*
- **RN-902** Toda predicción registra la **versión del modelo** que la generó. *(RF-805)*
- **RN-903** Predicción de churn por encima del umbral de riesgo dispara alerta y
  acción de retención (Customer Success, OP10). *(RT-16, CU-O13)*
- **RN-904** Precio recomendado fuera del rango esperado se marca anómalo y dispara
  alerta. *(RT-16, CU-O13)*
- **RN-905** Las predicciones se sirven a dashboards **solo vía ClickHouse**; el modelo
  no escribe directamente a la capa de serving del cliente. *(RT-01, RT-02)*
- **RN-906** Este paquete **no entrena** modelos (eso es CU-T08, táctico); solo ejecuta
  el modelo vigente. *(alcance)*

## 7. Entradas

- **Features del DW StarRocks** (retención, uso, precios, cliente).
- **Modelo vigente** (artefacto versionado) y umbrales.
- **Programación** (DAG Airflow).

## 8. Salidas

- **Predicciones de churn** (probabilidad, riesgo) por cliente.
- **Precios recomendados** por mercado/vino (con tendencia).
- **Registro de predicciones** (features, score, versión, fecha).
- **Eventos** para `alertas`; predicciones agregadas en ClickHouse para dashboards.

## 9. Estados posibles

**Corrida de inferencia:** `PROGRAMADA` → `CARGANDO_FEATURES` → `INFIRIENDO` →
`PERSISTIENDO` → `COMPLETADA`. Rutas de error: `BLOQUEADA_POR_CALIDAD` (features no
validadas), `FALLIDA` (error de ejecución, con alerta).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-801 (churn nominal):** *Dado* un DW validado, *cuando* corre la inferencia de
  churn, *entonces* genera probabilidad por cliente, la persiste con versión y la
  expone para alertas/dashboards. *(RF-803, RF-805)*
- **Esc-802 (precio nominal):** *Dado* features de precios, *cuando* corre el modelo
  de precios, *entonces* recomienda precio por mercado/vino con su tendencia. *(RF-804)*
- **Esc-803 (features sin calidad — error):** *Dado* un DW que no pasó GE, *cuando* se
  intenta la inferencia, *entonces* la corrida queda `BLOQUEADA_POR_CALIDAD` y no se
  ejecuta. *(RN-901)*
- **Esc-804 (churn alto — alerta):** *Dado* un cliente con probabilidad de churn sobre
  el umbral, *cuando* se evalúa, *entonces* se dispara alerta y acción de retención. *(RN-903)*
- **Esc-805 (precio anómalo — alerta):** *Dado* un precio recomendado fuera de rango,
  *cuando* se evalúa, *entonces* se marca anómalo y se alerta. *(RN-904)*
- **Esc-806 (reejecución idempotente):** *Dado* una corrida ya ejecutada, *cuando* se
  reejecuta, *entonces* no se duplican predicciones. *(RNF-802)*

## 11. Criterios de aceptación

- **CA-801** La inferencia de churn produce probabilidad y riesgo por cliente, con versión. *(RF-803, RF-805)*
- **CA-802** La inferencia de precios produce precio recomendado por mercado/vino. *(RF-804)*
- **CA-803** Sin DW validado (CU-O04), la corrida se bloquea. *(RN-901, Esc-803)*
- **CA-804** Churn sobre umbral y precio anómalo disparan alerta. *(RN-903, RN-904)*
- **CA-805** Las predicciones se sirven a dashboards vía ClickHouse. *(RN-905)*
- **CA-806** Reejecución idempotente sin duplicar predicciones. *(RNF-802)*

## 12. Dependencias

- **Capas:** StarRocks (features de entrada), ClickHouse (predicciones para serving).
- **Paquetes:** `etl-calidad` (OP2, DW + sello CU-O04); `alertas` (OP9, consume
  umbrales); `customer-success` (OP10, acción de retención); `dashboards` (OP3).
- **Tablas Fact/Dim:** `Fact_Retencion`, `Fact_Precio_Mercado`, `Fact_Uso_Plataforma`,
  `Dim_Cliente`, `Dim_Mercado`, `Dim_Vino`.
- **Herramientas:** runtime de ML (scikit-learn/equivalente), registro de modelos,
  Airflow, Docker.

## 13. Fuera de alcance

- **Entrenamiento y ajuste** de modelos (es CU-T08, nivel táctico).
- Cálculo de agregaciones y construcción de dashboards (OP2/OP3).
- Lógica de generación de alertas (vive en OP9 / `alertas`; aquí se emite el evento).
- Deep Learning (NLP/OCR) salvo que un modelo vigente lo incorpore; el alcance operativo
  es la inferencia programada de churn y precios.
