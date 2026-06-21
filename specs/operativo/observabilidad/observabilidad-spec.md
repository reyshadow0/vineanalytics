# observabilidad · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** DevOps
> - **Paquete:** `observabilidad`
> - **Objetivo operativo (OP):** OP7 — Monitorear disponibilidad, latencia e infraestructura.
> - **Objetivos de origen (OT/OE):** OT5 (Migrar/expandir a nube global con contenedores) y OT6 (CI/CD multi-región) → OE3 (Expansión Continua sobre Infraestructura Cloud de Alta Disponibilidad).
> - **Casos de uso (CU-O):** CU-O11 (Monitorear uptime y latencia).
> - **Modelo Fact-Dim que toca (matriz §9.8):** `Fact_Disponibilidad`, `Dim_Mercado` (y `Dim_Tiempo`).

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Monitorear de forma continua la **disponibilidad (uptime)**, la **latencia** y la
salud de la **infraestructura** por región, registrando mediciones en
`Fact_Disponibilidad` y disparando señales cuando se incumplen los SLO, para sostener
un uptime > 99.9% y baja latencia global (OE3).

## 2. Contexto

Es la capa de salud operativa: recolecta métricas de todos los servicios (ingesta,
ETL, API, dashboards) y de la infraestructura, las normaliza por `Dim_Mercado`/
`Dim_Tiempo` y las persiste en `Fact_Disponibilidad` (vía ETL OP2). Cuando uptime o
latencia cruzan su umbral, emite una señal a `alertas` (OP9). No realiza la
remediación (eso es de DevOps/respuesta a incidentes); su responsabilidad es
**medir, registrar y señalar**. Actor: **DevOps** y **Sistema**.

### Historias de usuario

**CU-O11 — Monitorear uptime y latencia**
- HU-01: *Como DevOps, quiero medir uptime y latencia por región en tiempo real, para
  saber si cumplimos el SLA de 99.9%.*
- HU-02: *Como Sistema, quiero registrar las mediciones en `Fact_Disponibilidad`, para
  alimentar reportes de disponibilidad y el BSC de procesos internos.*
- HU-03: *Como DevOps, quiero que se dispare una señal cuando uptime/latencia crucen
  el umbral, para reaccionar antes de afectar al cliente.*

## 3. Actores

| Actor | Participación |
|---|---|
| **DevOps** | Define SLO/umbrales, opera el monitoreo y atiende incidentes (CU-O11). |
| **Sistema (procesos automáticos)** | Recolecta métricas y registra `Fact_Disponibilidad`. |
| Paquetes monitoreados (`ingesta`, `etl-calidad`, `api-publica`, `dashboards`) | Emiten métricas/health. |
| Paquete `alertas` (OP9) | Recibe la señal de incumplimiento de SLO. |

## 4. Requisitos funcionales

**De CU-O11 (Monitorear uptime y latencia):**
- **RF-701** El sistema recolecta métricas de **uptime**, **latencia** e **incidentes**
  de cada servicio e infraestructura, por región.
- **RF-702** El sistema calcula uptime = tiempo_operativo / tiempo_total × 100 y
  latencia promedio por `Dim_Mercado`/`Dim_Tiempo`. *(§9.9)*
- **RF-703** El sistema registra las mediciones en `Fact_Disponibilidad` (uptime,
  latencia, incidentes, SLA).
- **RF-704** El sistema evalúa los umbrales/SLO (uptime < 99.9% o latencia > 200 ms) y
  **emite una señal** a `alertas` cuando se incumplen. *(RT-16)*
- **RF-705** El sistema expone health checks de cada componente del `docker-compose`.
- **RF-706** El sistema conserva el historial de incidentes para reporte y SLA.

## 5. Requisitos no funcionales

- **RNF-701 Cobertura:** monitorea todos los servicios del pipeline y la API.
- **RNF-702 Frecuencia:** muestreo continuo / de alta frecuencia (near real-time).
- **RNF-703 Bajo impacto:** la recolección no degrada el rendimiento monitoreado.
- **RNF-704 Reproducibilidad:** stack de observabilidad en contenedor. *(RT-17)*
- **RNF-705 Retención:** historial suficiente para SLA mensual y tendencias.

## 6. Reglas de negocio

- **RN-801** SLO de disponibilidad: uptime > 99.9% mensual; latencia < 200 ms
  promedio por región. *(BSC, OE3)*
- **RN-802** Incumplir un SLO genera señal a `alertas` (caída de uptime / latencia
  elevada). *(RT-16, CU-O13)*
- **RN-803** Las mediciones se registran en `Fact_Disponibilidad` y llegan al DW vía
  ETL; el dashboard de disponibilidad las lee agregadas en ClickHouse. *(RT-01)*
- **RN-804** Un fallo de ingesta o un pico de errores de API reportado por otro
  paquete también se refleja como incidente. *(enlaza ingesta/api)*
- **RN-805** La observabilidad **mide y señala**, no remedia; la respuesta a
  incidentes es responsabilidad de DevOps.

## 7. Entradas

- **Métricas de servicios** (ingesta, ETL, API, dashboards): health, latencia, errores.
- **Métricas de infraestructura** (contenedores, recursos).
- **Definición de SLO/umbrales** por región.

## 8. Salidas

- **`Fact_Disponibilidad`** poblado (uptime, latencia, incidentes, SLA) vía ETL.
- **Señales** a `alertas` ante incumplimiento de SLO.
- **Historial de incidentes** y métricas para el reporte de disponibilidad.
- **Health checks** consumibles por el orquestador.

## 9. Estados posibles

**Servicio monitoreado:** `SALUDABLE` → `DEGRADADO` → `CAIDO` → `RECUPERADO`.
**SLO:** `EN_CUMPLIMIENTO` ↔ `EN_RIESGO` ↔ `INCUMPLIDO` (este último emite señal).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-701 (medición nominal):** *Dado* el stack operando, *cuando* el monitor
  muestrea, *entonces* calcula uptime/latencia por región y los registra en
  `Fact_Disponibilidad`. *(RF-702, RF-703)*
- **Esc-702 (caída de uptime — alerta):** *Dado* una región cuyo uptime cae por
  debajo de 99.9%, *cuando* se evalúa el SLO, *entonces* el estado pasa a
  `INCUMPLIDO` y se emite señal a `alertas`. *(RN-801, RN-802)*
- **Esc-703 (latencia elevada — alerta):** *Dado* una latencia promedio > 200 ms en
  una región, *cuando* se evalúa, *entonces* se emite señal a `alertas`. *(RN-801)*
- **Esc-704 (servicio caído):** *Dado* un health check fallido, *cuando* se detecta,
  *entonces* el servicio pasa a `CAIDO`, se registra incidente y se señala. *(RF-705)*
- **Esc-705 (recolección no intrusiva):** *Dado* alta frecuencia de muestreo, *cuando*
  recolecta, *entonces* no degrada el rendimiento del servicio monitoreado. *(RNF-703)*

## 11. Criterios de aceptación

- **CA-701** Uptime y latencia se calculan por región y se registran en `Fact_Disponibilidad`. *(RF-702, RF-703)*
- **CA-702** Incumplir uptime < 99.9% o latencia > 200 ms emite señal a `alertas`. *(RN-801, RN-802)*
- **CA-703** Existen health checks de cada componente del `docker-compose`. *(RF-705)*
- **CA-704** El historial de incidentes permite calcular el SLA mensual. *(RF-706, RNF-705)*
- **CA-705** El reporte/dashboard de disponibilidad lee agregados de ClickHouse. *(RN-803)*

## 12. Dependencias

- **Capas:** capa operacional/infra (métricas), StarRocks (`Fact_Disponibilidad` vía
  ETL), ClickHouse (agregaciones para el dashboard de disponibilidad).
- **Paquetes:** todos los servicios monitoreados; `alertas` (OP9, recibe señales);
  `etl-calidad` (OP2, modela `Fact_Disponibilidad`); `reportes-operativos` (OP11).
- **Tablas Fact/Dim:** `Fact_Disponibilidad`, `Dim_Mercado`, `Dim_Tiempo`.
- **Herramientas:** stack de observabilidad (p. ej. Prometheus/Grafana), Docker.

## 13. Fuera de alcance

- Remediación automática / autoscaling (responsabilidad de DevOps; aquí solo se mide).
- CI/CD y despliegues en sí (CU-T06, nivel táctico).
- Generación de alertas multi-tipo (la lógica de alerta vive en OP9 / `alertas`; aquí
  se emite la señal de incumplimiento de SLO).
- Dashboards estratégicos de salud (nivel estratégico, fuera del repo).
