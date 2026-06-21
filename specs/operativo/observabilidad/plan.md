# observabilidad · Plan de implementación (speckit-plan)

> Paquete: `observabilidad` · OP7 · CU-O11 · DevOps.
> Spec fuente: [observabilidad-spec.md](observabilidad-spec.md). Marco:
> [000-general](../000-general/operativo-general-spec.md).

---

## 1. Arquitectura del paquete

```
ingesta · etl-calidad · api-publica · dashboards · infraestructura
        │ métricas / health / latencia / errores
        ▼
┌──────────────────────────────┐   uptime/latencia por región
│  Recolector + evaluador SLO   │ ─────────────► Fact_Disponibilidad (vía ETL)
│  (CU-O11)                     │
│  - calcula uptime/latencia    │   SLO incumplido
│  - evalúa umbrales            │ ─────────────► alertas (OP9)
└──────────────┬───────────────┘
               ▼
   dashboard de disponibilidad (lee agregado de ClickHouse)
```

## 2. Herramientas y componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| Recolección de métricas | **Prometheus** (o equivalente) | Scrapear métricas/health (RF-701). |
| Visualización operativa | **Grafana** | Tableros de salud para DevOps. |
| Evaluador de SLO | Reglas de alerta | Evaluar umbrales y señalar (RF-704). |
| Registro analítico | Emisor a `Fact_Disponibilidad` | Persistir mediciones (RF-703). |
| Empaquetado | **Docker** | Stack de observabilidad contenedorizado. |

## 3. Modelo de datos

- **Mediciones → `Fact_Disponibilidad`**: `timestamp` → `Dim_Tiempo`, `mercado` →
  `Dim_Mercado`, `servicio`, `uptime_pct`, `latencia_ms`, `incidentes`, `sla`.
- **Health checks:** endpoint por servicio del `docker-compose`.
- **SLO:** uptime > 99.9% mensual; latencia < 200 ms promedio (§9.9, BSC).

## 4. Secuencia de implementación

1. Instrumentar cada servicio con métricas/health checks. *(RF-701, RF-705)*
2. Desplegar el recolector (Prometheus) y la visualización (Grafana). *(RF-701)*
3. Implementar el cálculo de uptime/latencia por región. *(RF-702)*
4. Implementar el registro en `Fact_Disponibilidad`. *(RF-703)*
5. Configurar reglas de SLO y la señal a `alertas`. *(RF-704, RN-802)*
6. Conservar historial de incidentes para SLA. *(RF-706)*
7. Contenedorizar y validar bajo impacto. *(RNF-703, RNF-704)*

## 5. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Punto ciego de monitoreo | SLO incumplido sin detección | Cobertura total (RNF-701). |
| Recolección intrusiva | Degradación del servicio | Muestreo de bajo impacto (RNF-703). |
| Falsos positivos/negativos en SLO | Ruido o ceguera | Umbrales calibrados (RN-801). |
| Confundir medir con remediar | Responsabilidad difusa | RN-805: solo mide y señala. |

## 6. Trazabilidad de cumplimiento constitucional

- OE3 (alta disponibilidad) → RN-801. Princ. X (alertas operativas) → RF-704, RN-802.
- Arquitectura de capas → RN-803. Princ. VIII (Docker) → §2, paso 7.
