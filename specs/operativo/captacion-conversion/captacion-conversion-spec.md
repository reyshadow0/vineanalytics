# captacion-conversion · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Growth & Marketing
> - **Paquete:** `captacion-conversion`
> - **Objetivo operativo (OP):** OP6 — Ejecutar campañas de captación automatizadas y registrar conversiones.
> - **Objetivos de origen (OT/OE):** OT1 (Automatización de marketing con IA) y OT2 (Optimizar el embudo con analítica predictiva) → OE1 (Penetración de Mercado Digital y Adquisición Automatizada).
> - **Casos de uso (CU-O):** CU-O09 (Ejecutar campaña de captación automatizada) y CU-O10 (Registrar conversión del embudo).
> - **Modelo Fact-Dim que toca (matriz §9.8):**
>   - CU-O09 → `Fact_Campana`, `Dim_Canal_Adquisicion`.
>   - CU-O10 → `Fact_Conversion`, `Dim_Cliente`, `Dim_Mercado`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Ejecutar **campañas de captación automatizadas** por región/canal y **registrar las
conversiones** del embudo (lead → oportunidad → cliente), alimentando `Fact_Campana`
y `Fact_Conversion` para medir CAC, tasa de conversión y atribución, en apoyo a la
adquisición internacional automatizada (OE1).

## 2. Contexto

Es el motor de crecimiento: ejecuta campañas transfronterizas (CU-O09) sobre
`Dim_Canal_Adquisicion` (orgánico, pago, referido, marketplace) por `Dim_Mercado`, y
registra cada conversión (CU-O10) atribuyéndola a su campaña/canal. Los eventos se
proyectan al DW como `Fact_Campana` y `Fact_Conversion` (vía ETL OP2) para calcular
CAC y tasa de conversión. Una conversión que culmina en alta genera la cuenta en OP5
(`suscripciones`). Actor: **Growth & Marketing** y **Sistema**.

### Historias de usuario

**CU-O09 — Ejecutar campaña de captación automatizada**
- HU-01: *Como Growth & Marketing, quiero lanzar una campaña automatizada por región y
  canal, para captar leads internacionales sin equipos de venta locales.*
- HU-02: *Como Sistema, quiero registrar impresiones, clics, gasto y leads de cada
  campaña, para medir su rendimiento y CAC.*

**CU-O10 — Registrar conversión del embudo**
- HU-03: *Como Sistema, quiero registrar cada conversión con su etapa, fuente y
  resultado, atribuyéndola a la campaña/canal, para medir la tasa de conversión.*
- HU-04: *Como Growth & Marketing, quiero un reporte de conversión por mercado/canal,
  para optimizar la inversión y reducir el CAC.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Growth & Marketing** | Configura y lanza campañas; analiza conversión (CU-O09). |
| **Sistema (procesos automáticos)** | Ejecuta campañas y registra eventos/conversiones (CU-O09, CU-O10). |
| **Cliente empresarial (prospecto)** | Recibe la campaña y avanza en el embudo. |
| Paquete `suscripciones` (OP5) | Recibe la conversión que culmina en alta. |

## 4. Requisitos funcionales

**De CU-O09 (Ejecutar campaña de captación automatizada):**
- **RF-601** El sistema permite configurar una campaña con `Dim_Campana` (campaña,
  región, segmento), `Dim_Canal_Adquisicion` y presupuesto.
- **RF-602** El sistema **ejecuta la campaña de forma automatizada** según su
  programación.
- **RF-603** El sistema registra métricas de campaña en `Fact_Campana` (impresiones,
  clics, gasto, leads).
- **RF-604** El sistema deduplica leads para no contar dos veces el mismo prospecto. *(RT-09)*

**De CU-O10 (Registrar conversión del embudo):**
- **RF-605** El sistema registra cada conversión en `Fact_Conversion` con etapa
  (lead/oportunidad/cliente), fuente, resultado, `Dim_Cliente` y `Dim_Mercado`.
- **RF-606** El sistema **atribuye** la conversión a su campaña/canal de origen.
- **RF-607** El sistema calcula insumos para CAC y tasa de conversión (gasto/leads,
  conversiones/leads) consumibles por el DW.
- **RF-608** El sistema entrega la conversión que culmina en alta a `suscripciones`
  (OP5) para crear cuenta/suscripción.

## 5. Requisitos no funcionales

- **RNF-601 Automatización:** las campañas corren sin intervención manual una vez
  programadas. *(OT1)*
- **RNF-602 Atribución consistente:** modelo de atribución único y documentado. *(RF-606)*
- **RNF-603 Operacional:** eventos de campaña/conversión se registran en la capa
  operacional y llegan al DW vía ETL. *(RT-01)*
- **RNF-604 Reproducibilidad:** el orquestador de campañas corre en contenedor. *(RT-17)*
- **RNF-605 Privacidad:** datos de prospectos tratados conforme a normativa.

## 6. Reglas de negocio

- **RN-701** Toda campaña pertenece a un `Dim_Canal_Adquisicion` y un `Dim_Mercado`. *(RF-601)*
- **RN-702** Deduplicación de leads obligatoria. *(RT-09, RF-604)*
- **RN-703** Toda conversión se atribuye a exactamente una campaña/canal de origen
  (sin doble atribución). *(RF-606, RNF-602)*
- **RN-704** CAC = gasto_marketing / nuevos_clientes; tasa de conversión =
  conversiones / leads × 100 (definiciones canónicas §9.9). *(RF-607)*
- **RN-705** Una conversión en etapa `cliente` debe originar un alta en `suscripciones`
  (OP5); no se duplica la cuenta. *(RF-608, enlaza RN-601)*
- **RN-706** Caída brusca de conversión sobre el umbral genera alerta. *(RT-16, CU-O13)*

## 7. Entradas

- **Configuración de campaña** (canal, mercado, segmento, presupuesto, programación).
- **Eventos de interacción** (impresiones, clics, leads) del canal.
- **Eventos del embudo** (avance de etapa, resultado).

## 8. Salidas

- **`Fact_Campana`** poblado (impresiones, clics, gasto, leads) vía ETL.
- **`Fact_Conversion`** poblado (etapa, fuente, resultado, atribución) vía ETL.
- **Insumos de CAC y tasa de conversión** para reportes/dashboards.
- **Conversión→alta** entregada a `suscripciones` (OP5).

## 9. Estados posibles

**Campaña:** `BORRADOR` → `PROGRAMADA` → `EN_EJECUCION` → `FINALIZADA` (o `PAUSADA`).
**Conversión (embudo):** `LEAD` → `OPORTUNIDAD` → `CLIENTE` (o `PERDIDO`).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-601 (campaña nominal):** *Dado* una campaña `PROGRAMADA` para España por canal
  pago, *cuando* llega su horario, *entonces* se ejecuta automáticamente y registra
  impresiones/clics/leads en `Fact_Campana`. *(RF-602, RF-603)*
- **Esc-602 (lead duplicado — control):** *Dado* un prospecto que llega dos veces,
  *cuando* se registra, *entonces* el sistema lo deduplica y cuenta un solo lead. *(RN-702)*
- **Esc-603 (conversión nominal):** *Dado* un lead que avanza a cliente, *cuando* se
  registra la conversión, *entonces* se guarda en `Fact_Conversion` atribuida a su
  campaña/canal y se entrega a `suscripciones`. *(RF-605, RF-608)*
- **Esc-604 (doble atribución — error):** *Dado* una conversión, *cuando* dos campañas
  reclaman el mismo lead, *entonces* el modelo de atribución asigna a una sola. *(RN-703)*
- **Esc-605 (alta duplicada — control):** *Dado* una conversión a cliente cuya cuenta
  ya existe, *cuando* se entrega a `suscripciones`, *entonces* no se crea cuenta
  duplicada. *(RN-705, RN-601)*
- **Esc-606 (caída de conversión — alerta):** *Dado* un mercado con conversión muy por
  debajo del umbral, *cuando* se detecta, *entonces* se genera alerta. *(RN-706)*

## 11. Criterios de aceptación

- **CA-601** Una campaña programada se ejecuta automáticamente y puebla `Fact_Campana`. *(RF-602, RF-603)*
- **CA-602** Los leads se deduplican. *(RN-702)*
- **CA-603** Cada conversión queda en `Fact_Conversion` atribuida a una campaña/canal. *(RF-605, RN-703)*
- **CA-604** CAC y tasa de conversión se calculan con las fórmulas canónicas. *(RN-704)*
- **CA-605** Una conversión a cliente origina un alta en `suscripciones` sin duplicar cuenta. *(RF-608, RN-705)*
- **CA-606** Caída de conversión sobre el umbral genera alerta. *(RN-706)*

## 12. Dependencias

- **Capas:** capa operacional (eventos), StarRocks (`Fact_Campana`, `Fact_Conversion`
  vía ETL), ClickHouse (agregaciones para reportes).
- **Paquetes:** `suscripciones` (OP5, recibe la conversión); `etl-calidad` (OP2,
  modela los hechos); `alertas` (OP9); `reportes-operativos` (OP11).
- **Tablas Fact/Dim:** `Fact_Campana`, `Fact_Conversion`, `Dim_Campana`,
  `Dim_Canal_Adquisicion`, `Dim_Cliente`, `Dim_Mercado`.
- **Herramientas:** orquestador de campañas (p. ej. integración tipo HubSpot/Marketo),
  Airflow para programación, Docker.

## 13. Fuera de alcance

- Segmentación predictiva avanzada / scoring de leads con ML (es OP8 / `machine-learning`,
  caso táctico CU-T02); aquí se ejecuta la campaña y se registran eventos.
- Cálculo de agregaciones y dashboards (OP2/OP3).
- Alta comercial detallada de la cuenta (OP5 / `suscripciones`).
- Diseño estratégico de campañas (CU-T01, nivel táctico, fuera del repo).
