# alertas · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Sistema (procesos automáticos)
> - **Paquete:** `alertas`
> - **Objetivo operativo (OP):** OP9 — Generar alertas (churn, anomalías de precio o uso).
> - **Objetivos de origen (OT/OE):** OT8 (Modelos de ML) → OE4 (Inteligencia de Negocio Centralizada); soporta también OE3 (alta disponibilidad) al alertar incidentes de infraestructura.
> - **Casos de uso (CU-O):** CU-O13 (Generar alerta: churn / anomalía de precio).
> - **Modelo Fact-Dim que toca (matriz §9.8):** `Fact_Retencion`, `Fact_Precio_Mercado`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

**Centralizar la generación de alertas** operativas a partir de umbrales y detección
de anomalías: fuga de clientes (churn), anomalías de precio o de uso, fallos de
ingesta, caídas de uptime y errores de API. Cada alerta se clasifica por tipo,
severidad y causa, se registra y se notifica al responsable, para reaccionar antes de
que el problema afecte al negocio.

## 2. Contexto

Es el punto único de alertas del nivel operativo (regla transversal RT-16). Recibe
**señales** de otros paquetes: `machine-learning` (churn alto, precio anómalo),
`observabilidad` (caída de uptime, latencia), `ingesta-datos` (fallo de ingesta),
`api-publica` (pico de errores) y `captacion-conversion` (caída de conversión).
Aplica reglas de umbral / detección de anomalías sobre `Fact_Retencion` y
`Fact_Precio_Mercado` (y consume señales ya calculadas), genera la alerta, la
clasifica y la **enruta** al responsable. Actor: **Sistema**.

### Historias de usuario

**CU-O13 — Generar alerta (churn / anomalía de precio)**
- HU-01: *Como Sistema, quiero generar una alerta cuando la probabilidad de churn de
  un cliente supere el umbral, para que Customer Success actúe a tiempo.*
- HU-02: *Como Sistema, quiero generar una alerta cuando un precio de mercado quede
  fuera de rango, para detectar errores de fuente o eventos de mercado.*
- HU-03: *Como Sistema, quiero clasificar cada alerta por tipo, severidad y causa y
  enrutarla al responsable, para una respuesta ordenada.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Sistema (procesos automáticos)** | Evalúa umbrales, genera, clasifica y enruta alertas (CU-O13). |
| Paquetes emisores (`machine-learning`, `observabilidad`, `ingesta-datos`, `api-publica`, `captacion-conversion`) | Envían señales. |
| **Customer Success / DevOps / Ingeniería de datos** | Reciben y atienden la alerta según tipo. |

## 4. Requisitos funcionales

**De CU-O13 (Generar alerta):**
- **RF-901** El sistema **detecta anomalías y evalúa umbrales** sobre churn
  (`Fact_Retencion`) y precios (`Fact_Precio_Mercado`).
- **RF-902** El sistema **recibe señales** de otros paquetes (uptime, ingesta, API,
  conversión) y las normaliza como alertas.
- **RF-903** El sistema **clasifica** cada alerta por **tipo** (churn, precio, uso,
  ingesta, uptime, API, conversión), **severidad** (info/warning/critical) y **causa**.
- **RF-904** El sistema **registra** cada alerta (tipo, severidad, causa, origen,
  timestamp, estado).
- **RF-905** El sistema **enruta/notifica** la alerta al responsable según tipo
  (Customer Success, DevOps, Ingeniería de datos).
- **RF-906** El sistema **deduplica** alertas equivalentes y soporta agrupación para
  evitar tormentas de alertas. *(RT-09)*
- **RF-907** El sistema gestiona el ciclo de vida de la alerta (abierta → reconocida →
  resuelta / silenciada).

## 5. Requisitos no funcionales

- **RNF-901 Latencia de alerta:** una señal sobre umbral genera alerta en near
  real-time.
- **RNF-902 Fiabilidad:** ninguna señal de incumplimiento se pierde (entrega garantizada).
- **RNF-903 Anti-ruido:** deduplicación/agrupación para evitar fatiga de alertas. *(RF-906)*
- **RNF-904 Reproducibilidad:** el servicio de alertas corre en contenedor. *(RT-17)*
- **RNF-905 Trazabilidad:** toda alerta enlaza a su señal/origen y, si aplica, a la
  Fact que la motivó.

## 6. Reglas de negocio

- **RN-1001** Toda condición transversal RT-16 (fallo de ingesta, caída de uptime,
  error de API) **debe** generar alerta. *(Princ. X)*
- **RN-1002** Churn por encima del umbral genera alerta `critical` dirigida a Customer
  Success (acción de retención, OP10). *(enlaza RN-903 de ML)*
- **RN-1003** Precio fuera de rango esperado genera alerta de anomalía dirigida a
  Ingeniería de datos / análisis de mercado. *(enlaza RN-904 de ML)*
- **RN-1004** Las alertas se deduplican; eventos equivalentes no generan ruido
  repetido. *(RF-906, RT-09)*
- **RN-1005** Toda alerta queda registrada y auditable con su estado. *(RF-904, RF-907)*
- **RN-1006** Las señales/lecturas provienen del pipeline (DW/agregaciones), no de
  saltos de capa. *(RT-01)*

## 7. Entradas

- **Predicciones de ML** (churn, precio) de OP8.
- **Señales de SLO** de `observabilidad` (OP7).
- **Eventos de fallo** de `ingesta-datos` (OP1), `api-publica` (OP4),
  `captacion-conversion` (OP6).
- **Umbrales/reglas** configurables por tipo.

## 8. Salidas

- **Alertas** clasificadas (tipo, severidad, causa) registradas.
- **Notificaciones** enrutadas al responsable.
- **Historial de alertas** y su ciclo de vida (auditable).
- **Reporte de alertas** consumible por `reportes-operativos` (OP11).

## 9. Estados posibles

**Alerta:** `ABIERTA` → `RECONOCIDA` → `RESUELTA` (o `SILENCIADA`). Una alerta
duplicada se **agrupa** con la abierta en lugar de crear una nueva.

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-1001 (churn — alerta):** *Dado* una predicción de churn sobre el umbral,
  *cuando* llega la señal de ML, *entonces* se genera una alerta `critical` enrutada a
  Customer Success y se registra. *(RN-1002)*
- **Esc-1002 (precio anómalo — alerta):** *Dado* un precio fuera de rango, *cuando* se
  evalúa `Fact_Precio_Mercado`, *entonces* se genera alerta de anomalía a Ingeniería
  de datos. *(RN-1003)*
- **Esc-1003 (caída de uptime — alerta):** *Dado* una señal de SLO incumplido de
  `observabilidad`, *cuando* llega, *entonces* se genera alerta a DevOps. *(RN-1001)*
- **Esc-1004 (fallo de ingesta — alerta):** *Dado* un lote de ingesta `FALLIDA`,
  *cuando* llega el evento, *entonces* se genera alerta a Ingeniería de datos. *(RN-1001)*
- **Esc-1005 (tormenta de alertas — control):** *Dado* múltiples señales equivalentes,
  *cuando* llegan, *entonces* el sistema las deduplica/agrupa en una sola alerta
  abierta. *(RN-1004, Esc de error)*
- **Esc-1006 (señal perdida — error):** *Dado* un fallo de entrega, *cuando* ocurre,
  *entonces* el mecanismo de reintento garantiza que la alerta no se pierda. *(RNF-902)*

## 11. Criterios de aceptación

- **CA-1001** Churn sobre umbral genera alerta `critical` a Customer Success, registrada. *(RN-1002)*
- **CA-1002** Precio fuera de rango genera alerta de anomalía. *(RN-1003)*
- **CA-1003** Caída de uptime, fallo de ingesta y pico de errores de API generan alerta. *(RN-1001)*
- **CA-1004** Cada alerta se clasifica por tipo, severidad y causa, y se registra. *(RF-903, RF-904)*
- **CA-1005** Alertas equivalentes se deduplican/agrupan. *(RN-1004)*
- **CA-1006** El ciclo de vida (abierta→reconocida→resuelta/silenciada) funciona. *(RF-907)*

## 12. Dependencias

- **Capas:** StarRocks/ClickHouse (lecturas para detección), capa operacional (registro
  de alertas).
- **Paquetes (emisores):** `machine-learning` (OP8), `observabilidad` (OP7),
  `ingesta-datos` (OP1), `api-publica` (OP4), `captacion-conversion` (OP6).
- **Paquetes (consumidores):** `customer-success` (OP10), `reportes-operativos` (OP11).
- **Tablas Fact/Dim:** `Fact_Retencion`, `Fact_Precio_Mercado` (y referencias a las
  Fact que motivan otras alertas).
- **Herramientas:** motor de reglas/alertas, notificador, Docker.

## 13. Fuera de alcance

- **Cálculo** de las predicciones de churn/precio (es OP8 / `machine-learning`).
- **Medición** de uptime/latencia (es OP7 / `observabilidad`).
- Remediación de incidentes (responsabilidad de DevOps / Customer Success).
- Reportes consolidados (OP11); aquí solo se genera y registra la alerta.
