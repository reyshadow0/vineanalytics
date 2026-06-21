# reportes-operativos · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Administrador
> - **Paquete:** `reportes-operativos`
> - **Objetivo operativo (OP):** OP11 — Generar reportes diarios, mensuales y estratégicos (alcance operativo: el reporte diario).
> - **Objetivos de origen (OT/OE):** OT7 (Consolidar el Data Warehouse unificado para BI) → OE4 (Inteligencia de Negocio Centralizada).
> - **Casos de uso (CU-O):** CU-O16 (Generar reporte operativo diario).
> - **Modelo Fact-Dim que toca (matriz §9.8):** `Fact_Uso_Plataforma`, `Fact_Consumo_API`, `Dim_Tiempo`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Generar de forma automatizada el **reporte operativo diario** consolidando las
métricas del día (ingesta, consumo de API, uso de la plataforma, incidentes y
alertas) a partir de las **agregaciones de ClickHouse**, para dar visibilidad
operativa al Administrador y alimentar la consolidación táctica/estratégica.

## 2. Contexto

Es el cierre del flujo operativo: una vez que el pipeline (ingesta → calidad → ETL →
calidad → agregaciones) finaliza, este paquete consolida el día en un **reporte diario
operativo** leyendo agregaciones de **ClickHouse** (provenientes de
`Fact_Uso_Plataforma`, `Fact_Consumo_API`, e incidentes/alertas) por `Dim_Tiempo`. El
reporte se publica al Administrador y queda disponible para los reportes mensuales y
estratégicos (esos niveles superiores quedan fuera del repo). Actor: **Administrador**
y **Sistema** (generación programada).

### Historias de usuario

**CU-O16 — Generar reporte operativo diario**
- HU-01: *Como Administrador, quiero un reporte diario con ingesta, API, uso e
  incidentes, para conocer el estado operativo de la plataforma cada día.*
- HU-02: *Como Sistema, quiero generar el reporte automáticamente al cierre del DAG,
  para no depender de generación manual.*
- HU-03: *Como Administrador, quiero que el reporte se construya solo sobre datos
  validados por calidad, para confiar en sus cifras.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Administrador** | Consume el reporte diario y configura su contenido (CU-O16). |
| **Sistema (procesos automáticos)** | Genera el reporte al cierre del pipeline. |
| Paquetes fuente (`ingesta`, `api-publica`, `customer-success`, `observabilidad`, `alertas`) | Aportan las métricas consolidadas. |

## 4. Requisitos funcionales

**De CU-O16 (Generar reporte operativo diario):**
- **RF-1101** El sistema genera el **reporte diario** consolidando, por `Dim_Tiempo`
  (día): ingesta (lotes, filas, rechazos), consumo de API (`Fact_Consumo_API`:
  llamadas, latencia, errores), uso (`Fact_Uso_Plataforma`: sesiones, funciones) e
  incidentes/alertas del día.
- **RF-1102** El sistema lee **solo agregaciones de ClickHouse**. *(RT-01, RT-02)*
- **RF-1103** El sistema genera el reporte **automáticamente** al cierre del DAG
  (tras la fase de agregaciones).
- **RF-1104** El sistema **verifica que el día reportado pasó las validaciones de
  calidad** (CU-O04) antes de publicar el reporte. *(RT-15)*
- **RF-1105** El sistema entrega el reporte en formato consumible (p. ej. tablero +
  export) y lo archiva con su fecha.
- **RF-1106** El sistema deja el reporte disponible como insumo para la consolidación
  mensual/estratégica (fuera del alcance operativo).

## 5. Requisitos no funcionales

- **RNF-1101 Puntualidad:** el reporte del día queda disponible dentro de la ventana
  acordada tras el cierre del pipeline.
- **RNF-1102 Consistencia:** las cifras del reporte coinciden con las agregaciones de
  ClickHouse (única fuente).
- **RNF-1103 Reproducibilidad:** la generación corre en contenedor, orquestada por
  Airflow. *(RT-17)*
- **RNF-1104 Trazabilidad:** cada métrica del reporte enlaza a su Fact/agregación de origen.
- **RNF-1105 Auditoría:** los reportes se archivan y son reproducibles por fecha.

## 6. Reglas de negocio

- **RN-1201** El reporte se construye **solo** sobre datos validados por calidad
  (CU-O04); un día con calidad fallida no produce reporte definitivo. *(RT-15, RT-07)*
- **RN-1202** Las cifras provienen **solo de ClickHouse** (agregaciones); prohibido
  leer de StarRocks/PocketBase directamente. *(RT-01, RT-02)*
- **RN-1203** El reporte diario se genera tras la fase de agregaciones del DAG
  (último paso del flujo). *(RT-03)*
- **RN-1204** Toda cifra del reporte es trazable a su Fact/agregación de origen. *(RNF-1104, RT-14)*
- **RN-1205** Los reportes se archivan por fecha y son reproducibles (auditoría). *(RNF-1105)*

## 7. Entradas

- **Agregaciones de ClickHouse**: uso (`Fact_Uso_Plataforma`), API
  (`Fact_Consumo_API`), disponibilidad/incidentes, alertas del día.
- **Sello de calidad** del día (CU-O04).
- **Configuración del reporte** (métricas, formato, destinatarios).

## 8. Salidas

- **Reporte operativo diario** (tablero + export) archivado por fecha.
- **Insumo** para la consolidación mensual/estratégica.
- **Eventos** de generación (éxito/fallo) para observabilidad.

## 9. Estados posibles

**Reporte diario:** `PENDIENTE` → `ESPERANDO_CALIDAD` → `GENERANDO` → `PUBLICADO`
(archivado). Ruta de error: `BLOQUEADO_SIN_CALIDAD` (el día no pasó CU-O04) y
`FALLIDO` (error de generación, con alerta).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-1201 (reporte nominal):** *Dado* un día cuyo pipeline cerró y pasó calidad,
  *cuando* termina la fase de agregaciones, *entonces* se genera el reporte diario
  desde ClickHouse y se publica/archiva. *(RF-1101, RF-1103)*
- **Esc-1202 (sin calidad — error):** *Dado* un día con validación de calidad fallida,
  *cuando* se intenta generar el reporte, *entonces* queda `BLOQUEADO_SIN_CALIDAD` y
  no se publica un reporte definitivo. *(RN-1201, RF-1104)*
- **Esc-1203 (salto de capa — error):** *Dado* una métrica nueva, *cuando* se intenta
  calcularla desde StarRocks/PocketBase, *entonces* la revisión lo rechaza. *(RN-1202)*
- **Esc-1204 (cifras inconsistentes — control):** *Dado* el reporte, *cuando* una cifra
  no coincide con la agregación de ClickHouse, *entonces* se detecta por trazabilidad y
  se corrige el origen. *(RNF-1102, RN-1204)*
- **Esc-1205 (reproducibilidad):** *Dado* un reporte archivado, *cuando* se regenera
  para la misma fecha, *entonces* produce las mismas cifras. *(RNF-1105, RN-1205)*

## 11. Criterios de aceptación

- **CA-1201** El reporte diario consolida ingesta, API, uso e incidentes por `Dim_Tiempo`. *(RF-1101)*
- **CA-1202** El reporte se genera automáticamente al cierre del DAG. *(RF-1103, RN-1203)*
- **CA-1203** Sin calidad vigente del día (CU-O04), el reporte se bloquea. *(RF-1104, RN-1201)*
- **CA-1204** Las cifras provienen solo de ClickHouse y son trazables a su origen. *(RN-1202, RN-1204)*
- **CA-1205** El reporte se archiva por fecha y es reproducible. *(RF-1105, RN-1205)*

## 12. Dependencias

- **Capas:** ClickHouse (agregaciones, única fuente del reporte), StarRocks/ETL (origen
  de las agregaciones).
- **Paquetes:** `etl-calidad` (OP2, sello CU-O04 + agregaciones); `ingesta-datos` (OP1),
  `api-publica` (OP4), `customer-success` (OP10), `observabilidad` (OP7), `alertas`
  (OP9) aportan métricas.
- **Tablas Fact/Dim:** `Fact_Uso_Plataforma`, `Fact_Consumo_API`, `Dim_Tiempo`
  (y referencias a incidentes/alertas).
- **Herramientas:** generador de reportes (tablero/export), Airflow, ClickHouse, Docker.

## 13. Fuera de alcance

- **Reportes mensuales y estratégicos** y el reporte ejecutivo global (nivel
  táctico/estratégico, fuera del repo); aquí solo el **reporte operativo diario**.
- Cálculo de las agregaciones en sí (es parte del pipeline OP2/OP3).
- Validación de calidad (CU-O04 / `etl-calidad`); aquí solo se verifica su sello.
- Visualización interactiva orientada al cliente final (es OP3 / `dashboards`).
