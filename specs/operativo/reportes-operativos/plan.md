# reportes-operativos · Plan de implementación (speckit-plan)

> Paquete: `reportes-operativos` · OP11 · CU-O16 · Administrador.
> Spec fuente: [reportes-operativos-spec.md](reportes-operativos-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
DAG pipeline diario:  ingesta → calidad → ETL → calidad → agregaciones ──┐
                                                                          ▼
                                              ┌──────────────────────────────┐
   sello calidad CU-O04 (etl-calidad) ───────►│  Generador de reporte diario  │
                                              │  (CU-O16)                     │
   agregaciones ClickHouse ───────────────────►│  - consolida ingesta/API/uso  │
   (Fact_Uso_Plataforma, Fact_Consumo_API)    │  - incidentes/alertas del día │
                                              └──────────────┬───────────────┘
                                                             ▼
                                        reporte diario (tablero + export) archivado
                                                             │
                                                             ▼
                                     insumo para consolidación mensual/estratégica
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Generador de reporte | Servicio de reporting + export | Consolidar y publicar (CU-O16). |
| Fuente de datos | **ClickHouse** | Única fuente de cifras (RN-1202). |
| Gate de calidad | Verificador del sello CU-O04 | Bloquear si el día no pasó calidad (RF-1104). |
| Orquestación | **Apache Airflow** | Generar al cierre del DAG (RN-1203). |
| Archivo de reportes | Almacenamiento por fecha | Auditoría/reproducibilidad (RN-1205). |
| Empaquetado | **Docker** | Generador contenedorizado. |

## 3. Modelo de datos

- **Lectura (ClickHouse):** agregaciones diarias por `Dim_Tiempo`:
  `Fact_Uso_Plataforma` (sesiones, funciones), `Fact_Consumo_API` (llamadas, latencia,
  errores), disponibilidad/incidentes, alertas del día.
- **Reporte:** documento/tablero con secciones (ingesta, API, uso, incidentes,
  alertas), `fecha`, `version`, `calidad_ok`, enlaces de trazabilidad a cada agregación.

## 4. Secuencia de implementación

1. Definir el contenido y formato del reporte diario. *(RF-1101, RF-1105)*
2. Conectar el generador a ClickHouse (solo lectura). *(RF-1102, RN-1202)*
3. Implementar el gate de calidad del día (sello CU-O04). *(RF-1104, RN-1201)*
4. Implementar la consolidación de métricas por `Dim_Tiempo`. *(RF-1101)*
5. Programar la generación al cierre del DAG (último paso). *(RF-1103, RN-1203)*
6. Implementar el archivado por fecha y la reproducibilidad. *(RF-1105, RN-1205)*
7. Añadir trazabilidad de cada cifra a su agregación de origen. *(RN-1204)*
8. Dejar el reporte como insumo para niveles superiores. *(RF-1106)*
9. Contenedorizar y validar. *(RNF-1103)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Reporte sobre datos sin calidad | Cifras no confiables | Gate CU-O04 (RN-1201). |
| Lectura de capa incorrecta | Salto de capa | Solo ClickHouse (RN-1202). |
| Cifras inconsistentes | Pérdida de confianza | Trazabilidad por métrica (RN-1204). |
| Generación manual/tardía | Falta de puntualidad | Automatización en Airflow (RN-1203, RNF-1101). |

## 6. Trazabilidad de cumplimiento constitucional

- Princ. X / RT-15 (no publicar sin calidad) → RF-1104, RN-1201.
- Arquitectura de capas → RN-1202. Princ. IX (Airflow) / VIII (Docker) → §2, pasos 5 y 9.
