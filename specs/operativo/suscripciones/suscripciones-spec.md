# suscripciones · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Administrador (de plataforma)
> - **Paquete:** `suscripciones`
> - **Objetivo operativo (OP):** OP5 — Registrar y gestionar suscripciones de clientes.
> - **Objetivos de origen (OT/OE):** OT4 (Integraciones con marketplaces/partners) → OE2 (Escalabilidad Comercial vía APIs y ecosistemas).
> - **Casos de uso (CU-O):** CU-O08 (Registrar cuenta y suscripción del cliente).
> - **Modelo Fact-Dim que toca (matriz §9.8):** `Fact_Suscripcion`, `Dim_Cliente`, `Dim_Plan` (y `Dim_Estado_Suscripcion`).

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Registrar y gestionar **cuentas y suscripciones** de clientes (plan, monto, periodo,
estado) en la capa **operacional PocketBase**, garantizando deduplicación de cuentas
y validación de plan/facturación, para alimentar `Fact_Suscripcion` (MRR/ARR) y
habilitar el control de acceso de dashboards (OP3) y API (OP4).

## 2. Contexto

Es la base comercial del SaaS: el alta de cuenta y suscripción vive en **PocketBase**
(operacional). Cada evento de suscripción (alta, upgrade, downgrade, pausa,
cancelación) se proyecta luego al DW como `Fact_Suscripcion` (vía ETL OP2) para
calcular MRR/ARR. El estado de la suscripción (`Dim_Estado_Suscripcion`) gobierna si
un cliente puede recibir dashboards (RN-402 de `dashboards`) o consumir la API según
su cuota. Actor principal: **Administrador**.

### Historias de usuario

**CU-O08 — Registrar cuenta y suscripción del cliente**
- HU-01: *Como Administrador, quiero registrar una cuenta de cliente con su plan,
  monto y periodo, para activar su suscripción.*
- HU-02: *Como Administrador, quiero que el sistema rechace cuentas duplicadas, para
  mantener un padrón de clientes limpio.*
- HU-03: *Como Administrador, quiero gestionar el ciclo de vida (prueba, activa, en
  pausa, cancelada), para reflejar la realidad comercial y habilitar/cortar acceso.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Administrador** | Registra y gestiona cuentas y suscripciones (CU-O08). |
| **Cliente empresarial** | Titular de la cuenta/suscripción. |
| **Sistema** | Calcula vigencia, proyecta eventos a `Fact_Suscripcion` (vía ETL). |
| Paquetes `dashboards`/`api-publica` | Consumen plan/estado para autorizar acceso. |

## 4. Requisitos funcionales

**De CU-O08 (Registrar cuenta y suscripción):**
- **RF-501** El sistema registra una **cuenta de cliente** (`Dim_Cliente`: tipo,
  tamaño, segmento, mercado) en PocketBase.
- **RF-502** El sistema registra una **suscripción** con `Dim_Plan` (básico /
  profesional / enterprise), `monto`, `moneda`, `periodo` (mensual/anual) y fecha de
  inicio.
- **RF-503** El sistema **deduplica cuentas** (p. ej. por identificador fiscal/email
  corporativo) y rechaza altas duplicadas. *(RT-09)*
- **RF-504** El sistema valida el plan y los datos de facturación antes de activar.
- **RF-505** El sistema gestiona el **ciclo de vida** vía `Dim_Estado_Suscripcion`
  (prueba → activa → en pausa → cancelada) con upgrades/downgrades.
- **RF-506** El sistema emite eventos de suscripción consumibles por el ETL para
  poblar `Fact_Suscripcion` (MRR/ARR, upgrades, downgrades).
- **RF-507** El sistema expone el plan/estado vigente para que `dashboards` (RN-402) y
  `api-publica` (cuota) autoricen acceso.

## 5. Requisitos no funcionales

- **RNF-501 Consistencia:** el estado de la suscripción es la fuente de verdad de
  acceso; cambios se reflejan de inmediato.
- **RNF-502 Operacional en PocketBase:** las cuentas/suscripciones residen en la capa
  operacional; al DW llegan solo vía ETL. *(RT-01)*
- **RNF-503 Auditoría:** todo cambio de estado/plan queda con historial y fecha.
- **RNF-504 Reproducibilidad:** PocketBase y la lógica corren en contenedor. *(RT-17)*
- **RNF-505 Seguridad:** datos de facturación protegidos; sin números de tarjeta en claro.

## 6. Reglas de negocio

- **RN-601** No se admiten cuentas duplicadas; un alta repetida se rechaza con el id
  existente. *(RT-09, RT-10)*
- **RN-602** Una suscripción debe tener plan válido y datos de facturación completos
  para pasar a `activa`. *(RF-504)*
- **RN-603** Solo cuentas con suscripción `activa` (o `prueba` vigente) reciben
  dashboards y consumo de API. *(RF-507, enlaza RN-402 de dashboards)*
- **RN-604** Las transiciones de estado válidas son
  `prueba → activa → en pausa → cancelada` (y `activa ↔ en pausa`); otras se rechazan. *(RF-505)*
- **RN-605** Cada cambio (alta, upgrade, downgrade, pausa, cancelación) genera un
  evento para `Fact_Suscripcion`. *(RF-506)*
- **RN-606** Las cuentas/suscripciones viven en PocketBase; el dashboard no las lee
  directamente para datos analíticos (los lee agregados en ClickHouse). *(RT-01)*

## 7. Entradas

- **Datos de cuenta** (cliente B2B: tipo, tamaño, segmento, mercado).
- **Datos de suscripción** (plan, monto, moneda, periodo, facturación).
- **Solicitudes de cambio** (upgrade/downgrade/pausa/cancelación).

## 8. Salidas

- **Cuenta y suscripción** persistidas en PocketBase con su estado.
- **Eventos de suscripción** para el ETL → `Fact_Suscripcion`.
- **Plan/estado vigente** expuesto a `dashboards` y `api-publica`.
- **Historial de cambios** (auditoría).

## 9. Estados posibles

**Suscripción (`Dim_Estado_Suscripcion`):** `PRUEBA` → `ACTIVA` → (`EN_PAUSA` ↔
`ACTIVA`) → `CANCELADA`. Alta inválida: `RECHAZADA`. Falta de pago: `EN_PAUSA` o
`CANCELADA` según política.

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-501 (alta nominal):** *Dado* un Administrador con datos completos, *cuando*
  registra una cuenta con plan profesional y facturación válida, *entonces* la
  suscripción queda `ACTIVA` y se emite el evento a `Fact_Suscripcion`. *(RF-502, RF-506)*
- **Esc-502 (cuenta duplicada — error):** *Dado* una cuenta ya existente, *cuando*
  se intenta registrarla de nuevo, *entonces* el sistema la rechaza con el id
  existente. *(RN-601, Esc)*
- **Esc-503 (facturación incompleta — error):** *Dado* una suscripción sin datos de
  facturación, *cuando* se intenta activar, *entonces* permanece sin activar y se
  notifica el faltante. *(RN-602)*
- **Esc-504 (transición inválida — error):** *Dado* una suscripción `CANCELADA`,
  *cuando* se intenta pasarla a `EN_PAUSA`, *entonces* el sistema rechaza la
  transición. *(RN-604)*
- **Esc-505 (corte de acceso):** *Dado* una suscripción que pasa a `CANCELADA`,
  *cuando* se actualiza el estado, *entonces* `dashboards` y `api-publica` dejan de
  autorizar acceso. *(RN-603)*
- **Esc-506 (upgrade):** *Dado* una cuenta `ACTIVA` en plan básico, *cuando* hace
  upgrade a enterprise, *entonces* se emite evento de upgrade a `Fact_Suscripcion`. *(RN-605)*

## 11. Criterios de aceptación

- **CA-501** Un alta válida deja la suscripción `ACTIVA` en PocketBase con su `Dim_Plan`. *(RF-502)*
- **CA-502** Un alta duplicada es rechazada con el id existente. *(RN-601)*
- **CA-503** Solo suscripciones con plan y facturación válidos se activan. *(RN-602)*
- **CA-504** Las transiciones de estado siguen las reglas; las inválidas se rechazan. *(RN-604)*
- **CA-505** Cada cambio genera un evento para `Fact_Suscripcion`. *(RN-605)*
- **CA-506** El plan/estado vigente está disponible para autorizar dashboards y API. *(RF-507)*

## 12. Dependencias

- **Capas:** PocketBase (cuentas/suscripciones), StarRocks (`Fact_Suscripcion` vía ETL).
- **Paquetes:** `etl-calidad` (OP2, modela `Fact_Suscripcion`); `dashboards` (OP3) y
  `api-publica` (OP4) consumen plan/estado; `customer-success` (OP10) y `reportes`.
- **Tablas Fact/Dim:** `Fact_Suscripcion`, `Dim_Cliente`, `Dim_Plan`, `Dim_Estado_Suscripcion`.
- **Herramientas:** PocketBase, Docker.

## 13. Fuera de alcance

- Cálculo de MRR/ARR y agregaciones (OP2/OP3); aquí solo se emiten eventos.
- Cobro/pasarela de pagos en detalle (se asume integración externa; aquí se valida).
- Campañas de captación que originan la cuenta (es OP6 / `captacion-conversion`).
- Reportes financieros estratégicos (nivel estratégico, fuera del repo).
