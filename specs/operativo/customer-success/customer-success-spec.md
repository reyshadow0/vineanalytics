# customer-success · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Customer Success
> - **Paquete:** `customer-success`
> - **Objetivo operativo (OP):** OP10 — Registrar onboarding, soporte y uso de la plataforma.
> - **Objetivos de origen (OT/OE):** OT9 (Operar un programa de Customer Success y retención) → OE1 (Adquisición/retención; reducir churn).
> - **Casos de uso (CU-O):** CU-O14 (Registrar onboarding y ticket de soporte) y CU-O15 (Consultar uso de la plataforma por cliente).
> - **Modelo Fact-Dim que toca (matriz §9.8):**
>   - CU-O14 → `Dim_Cliente`, `Dim_Tiempo`.
>   - CU-O15 → `Fact_Uso_Plataforma`, `Dim_Cliente`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Registrar el **onboarding** y los **tickets de soporte** de cada cliente, y permitir
**consultar el uso/adopción** de la plataforma por cuenta, para impulsar la
satisfacción (NPS), la adopción (≥ 70%) y la retención (churn < 4%), cerrando el
ciclo con las alertas de churn de OP9. Es el brazo operativo del programa de
retención (OE1).

## 2. Contexto

Customer Success opera el día a día de la relación con el cliente: registra el
onboarding y la atención de soporte (CU-O14) en la capa operacional, y consulta el
**uso/adopción** del cliente (CU-O15) leyendo agregaciones de **ClickHouse**
(provenientes de `Fact_Uso_Plataforma`). Recibe **alertas de churn** (OP9) para
priorizar la acción de retención. No entrena modelos ni calcula agregaciones; consume
lo que el pipeline produce. Actor: **Customer Success** (con Analista en consultas).

### Historias de usuario

**CU-O14 — Registrar onboarding y ticket de soporte**
- HU-01: *Como Customer Success, quiero registrar el onboarding de una cuenta nueva,
  para asegurar su activación y adopción inicial.*
- HU-02: *Como Customer Success, quiero registrar y clasificar tickets de soporte con
  sus tiempos, para medir la calidad de atención y la satisfacción.*

**CU-O15 — Consultar uso de la plataforma por cliente**
- HU-03: *Como Customer Success, quiero consultar el uso/adopción por cliente
  (sesiones, funciones, frecuencia), para detectar cuentas en riesgo y actuar.*
- HU-04: *Como Analista de datos, quiero ver el uso agregado por cuenta, para apoyar
  decisiones de retención y upsell.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Customer Success** | Registra onboarding/tickets; consulta uso; ejecuta retención (CU-O14, CU-O15). |
| **Analista de datos** | Consulta uso agregado por cuenta (CU-O15). |
| **Cliente empresarial** | Sujeto del onboarding, soporte y uso. |
| Paquetes `alertas` (OP9) / `machine-learning` (OP8) | Proveen alertas/predicciones de churn. |

## 4. Requisitos funcionales

**De CU-O14 (Registrar onboarding y ticket de soporte):**
- **RF-1001** El sistema registra el **onboarding** de una cuenta (`Dim_Cliente`,
  `Dim_Tiempo`): pasos, estado y fecha.
- **RF-1002** El sistema registra **tickets de soporte** con clasificación, prioridad,
  tiempos (apertura/resolución) y satisfacción.
- **RF-1003** El sistema calcula tiempos de atención (primera respuesta, resolución) y
  permite seguimiento del ticket.
- **RF-1004** El sistema captura señales de satisfacción (NPS) asociadas a la cuenta.

**De CU-O15 (Consultar uso de la plataforma por cliente):**
- **RF-1005** El sistema permite **consultar el uso/adopción** por cliente leyendo
  agregaciones de **ClickHouse** (sesiones, dashboards vistos, funciones, frecuencia)
  desde `Fact_Uso_Plataforma`. *(RT-01, RT-02)*
- **RF-1006** El sistema relaciona la consulta de uso con las **alertas de churn**
  (OP9) para priorizar cuentas en riesgo.
- **RF-1007** El sistema expone el reporte de adopción/soporte por cuenta.

## 5. Requisitos no funcionales

- **RNF-1001 Operacional:** onboarding y tickets residen en la capa operacional
  (PocketBase); el uso se consulta agregado en ClickHouse. *(RT-01)*
- **RNF-1002 Tiempo de respuesta de soporte:** apoyar el objetivo de responder el 95%
  de solicitudes en < 24 h. *(documento §2.3)*
- **RNF-1003 Privacidad:** datos de cliente y soporte protegidos.
- **RNF-1004 Reproducibilidad:** componentes en contenedor. *(RT-17)*
- **RNF-1005 Adopción/retención:** apoyar adopción ≥ 70% y churn < 4% (BSC cliente).

## 6. Reglas de negocio

- **RN-1101** Un ticket sigue su ciclo: `abierto → en_proceso → resuelto → cerrado`;
  transiciones inválidas se rechazan.
- **RN-1102** El uso/adopción se consulta de **ClickHouse** (agregado de
  `Fact_Uso_Plataforma`); prohibido leer eventos crudos saltando capas. *(RT-01, RT-02)*
- **RN-1103** Una alerta de churn (OP9) sobre una cuenta **prioriza** una acción de
  retención y queda vinculada al seguimiento de la cuenta. *(enlaza RN-1002 de alertas)*
- **RN-1104** El onboarding debe registrarse para toda cuenta nueva creada en OP5. *(enlaza suscripciones)*
- **RN-1105** Las métricas de soporte (tiempos, NPS) son auditables y alimentan
  reportes y el BSC de cliente. *(RF-1003, RF-1004)*

## 7. Entradas

- **Cuenta nueva** desde `suscripciones` (OP5) → dispara onboarding.
- **Solicitudes de soporte** (tickets) del cliente.
- **Alertas/predicciones de churn** (OP9/OP8).
- **Agregaciones de uso** (ClickHouse) desde `Fact_Uso_Plataforma`.

## 8. Salidas

- **Registro de onboarding** y **tickets de soporte** (con tiempos y NPS).
- **Consulta/reporte de uso y adopción** por cliente.
- **Acciones de retención** vinculadas a alertas de churn.
- **Métricas** para reportes (OP11) y BSC de cliente.

## 9. Estados posibles

**Onboarding:** `PENDIENTE` → `EN_PROGRESO` → `COMPLETADO` (o `ESTANCADO`).
**Ticket:** `ABIERTO` → `EN_PROCESO` → `RESUELTO` → `CERRADO` (o `REABIERTO`).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-1101 (onboarding nominal):** *Dado* una cuenta nueva de OP5, *cuando* se inicia
  el onboarding, *entonces* se registran pasos y estado en la capa operacional. *(RF-1001, RN-1104)*
- **Esc-1102 (ticket nominal):** *Dado* una solicitud del cliente, *cuando* se abre un
  ticket, *entonces* se clasifica, se registran tiempos y sigue su ciclo de vida. *(RF-1002, RF-1003)*
- **Esc-1103 (consulta de uso):** *Dado* una cuenta, *cuando* Customer Success consulta
  su uso, *entonces* el sistema muestra sesiones/funciones/frecuencia desde ClickHouse. *(RF-1005)*
- **Esc-1104 (cuenta en riesgo — retención):** *Dado* una alerta de churn sobre una
  cuenta, *cuando* se recibe, *entonces* se prioriza una acción de retención vinculada
  a la cuenta. *(RN-1103, Esc)*
- **Esc-1105 (transición inválida — error):** *Dado* un ticket `CERRADO`, *cuando* se
  intenta pasarlo a `EN_PROCESO` sin reabrir, *entonces* el sistema rechaza la
  transición. *(RN-1101)*
- **Esc-1106 (salto de capa — error):** *Dado* la consulta de uso, *cuando* se intenta
  leer eventos crudos en vez de la agregación de ClickHouse, *entonces* la revisión lo
  rechaza. *(RN-1102)*

## 11. Criterios de aceptación

- **CA-1101** El onboarding de una cuenta nueva queda registrado con pasos y estado. *(RF-1001)*
- **CA-1102** Los tickets se registran con clasificación, tiempos y NPS, y siguen su ciclo. *(RF-1002, RF-1003, RN-1101)*
- **CA-1103** La consulta de uso por cliente lee agregaciones de ClickHouse. *(RF-1005, RN-1102)*
- **CA-1104** Una alerta de churn prioriza y vincula una acción de retención. *(RF-1006, RN-1103)*
- **CA-1105** Existe reporte de adopción/soporte por cuenta. *(RF-1007)*

## 12. Dependencias

- **Capas:** PocketBase (onboarding/tickets), ClickHouse (uso agregado de
  `Fact_Uso_Plataforma`), StarRocks (origen vía ETL).
- **Paquetes:** `suscripciones` (OP5, cuenta nueva); `alertas` (OP9) y
  `machine-learning` (OP8, churn); `etl-calidad` (OP2); `reportes-operativos` (OP11).
- **Tablas Fact/Dim:** `Fact_Uso_Plataforma`, `Dim_Cliente`, `Dim_Tiempo`.
- **Herramientas:** PocketBase, herramienta de tickets/CRM, ClickHouse, Docker.

## 13. Fuera de alcance

- Cálculo de las agregaciones de uso (OP2/OP3); aquí solo se consultan.
- Predicción de churn (OP8) y generación de la alerta (OP9); aquí se actúa sobre ella.
- Alta/gestión comercial de la suscripción (OP5).
- Programa táctico de retención y NPS estratégico (CU-T09 / nivel táctico).
