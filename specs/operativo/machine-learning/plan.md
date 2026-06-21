# machine-learning · Plan de implementación (speckit-plan)

> Paquete: `machine-learning` · OP8 · CU-O12 · Data Science.
> Spec fuente: [machine-learning-spec.md](machine-learning-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
StarRocks (DW, features validadas por CU-O04)
        │  lee features
        ▼
┌──────────────────────────────┐
│  Runner de inferencia (CU-O12)│  inferencia programada (Airflow)
│  - modelo churn (vigente)     │
│  - modelo precios (vigente)   │   predicciones + versión
│  - umbrales                   │ ─────────► registro de predicciones ─► ClickHouse (dashboards)
└──────────────┬───────────────┘                                    └─► alertas (OP9)
               ▼
   churn alto / precio anómalo  ─────────────────────────────────────────► alertas (OP9)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Runtime de inferencia | **scikit-learn** (o equivalente) | Aplicar modelos vigentes (RF-801). |
| Registro de modelos | Model registry (versión + artefacto) | Versionar modelo por predicción (RF-805). |
| Lectura de features | Conector StarRocks (:9030) | Cargar features del DW (RF-802). |
| Persistencia de predicciones | DW → ClickHouse | Servir predicciones (RF-806). |
| Orquestación | **Apache Airflow** | Programar inferencia idempotente (RNF-803). |
| Empaquetado | **Docker** | Runner contenedorizado. |

## 3. Modelo de datos

- **Features (entrada):** desde `Fact_Retencion`, `Fact_Uso_Plataforma`,
  `Fact_Precio_Mercado`, `Dim_Cliente`, `Dim_Mercado`, `Dim_Vino`.
- **Predicciones (salida):** `cliente_id`/`mercado_id`, `tipo_modelo` (churn|precio),
  `score`/`precio_recomendado`, `nivel_riesgo`/`tendencia`, `version_modelo`, `fecha`.
- **Umbrales:** churn ≥ umbral de riesgo; precio fuera de rango esperado.

## 4. Secuencia de implementación

1. Definir el contrato de features y el registro de modelos vigentes. *(RF-802, RF-805)*
2. Implementar el gate de calidad: solo inferir sobre DW validado (CU-O04). *(RN-901)*
3. Implementar el runner de churn (probabilidad + riesgo). *(RF-803)*
4. Implementar el runner de precios (recomendación + tendencia). *(RF-804)*
5. Persistir predicciones con versión y exponerlas (DW→ClickHouse). *(RF-805, RF-806)*
6. Emitir eventos a `alertas` ante umbrales. *(RN-903, RN-904)*
7. Registrar métricas de corrida; garantizar idempotencia. *(RF-807, RNF-802)*
8. Programar el DAG y contenedorizar. *(RNF-803, RNF-801)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Inferir sobre features sucias | Predicciones inválidas | Gate CU-O04 (RN-901). |
| Predicción sin versión | No reproducible | Versión obligatoria (RN-902). |
| Reproceso duplica predicciones | Métricas erróneas | Idempotencia (RNF-802). |
| Confundir inferencia con entrenamiento | Fuera de alcance | RN-906: solo ejecuta vigente. |
| Servir saltando capas | Salto de capa | Solo vía ClickHouse (RN-905). |

## 6. Trazabilidad de cumplimiento constitucional

- OT8/OE4 (ML) → §1. Princ. V (calidad de features) → RN-901, RNF-804.
- Princ. IX (Airflow) → §2, paso 8. Princ. VIII (Docker) → §2.
