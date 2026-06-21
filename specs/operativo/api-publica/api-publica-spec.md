# api-publica · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Sistema (procesos automáticos), con Partner/Integrador como consumidor
> - **Paquete:** `api-publica`
> - **Objetivo operativo (OP):** OP4 — Atender solicitudes de la API pública.
> - **Objetivos de origen (OT/OE):** OT3 (Diseñar y publicar APIs estables OpenAPI bajo SDD) y OT4 (Integraciones con marketplaces/partners) → OE2 (Escalabilidad Comercial vía APIs y ecosistemas).
> - **Casos de uso (CU-O):** CU-O07 (Atender solicitud de la API pública).
> - **Modelo Fact-Dim que toca (matriz §9.8):** `Fact_Consumo_API`, `Dim_Partner_API`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Atender solicitudes de la **API pública** de VinAnalytics de forma autenticada,
controlada por **rate limiting** y **versionada bajo contrato OpenAPI (SDD)**,
sirviendo datos desde las **agregaciones de ClickHouse**, y **registrar cada llamada**
(latencia, estado, partner) en `Fact_Consumo_API` para medir el ecosistema y los
ingresos vía API (OE2).

## 2. Contexto

Habilita la escalabilidad comercial: marketplaces, distribuidores e integradores
consumen los servicios sin equipos de venta. Cada solicitud se autentica (API key /
token de partner), se valida contra el rate limit del plan y se sirve desde
ClickHouse (nunca leyendo PocketBase/StarRocks para datos analíticos). El consumo se
registra en `Fact_Consumo_API` con su `Dim_Partner_API`. La API se diseña
**Specification-Driven** con contrato **OpenAPI** versionado. Actor principal:
**Sistema**; consumidor: **Partner/Integrador**.

### Historias de usuario

**CU-O07 — Atender solicitud de la API pública**
- HU-01: *Como Partner/Integrador, quiero consumir endpoints estables y versionados
  con mi API key, para integrar VinAnalytics en mi plataforma sin sorpresas.*
- HU-02: *Como Sistema, quiero autenticar y aplicar rate limiting por partner/plan,
  para proteger la plataforma y diferenciar por contrato.*
- HU-03: *Como Sistema, quiero registrar cada llamada (latencia, estado, partner) en
  `Fact_Consumo_API`, para medir consumo, errores e ingresos vía API.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Sistema (procesos automáticos)** | Autentica, limita, sirve y registra cada llamada (CU-O07). |
| **Partner / Integrador (API)** | Consume los endpoints públicos. |
| **Cliente empresarial** | Puede consumir la API con su propia credencial. |
| Paquete `suscripciones` (OP5) | Define el plan/cuota del consumidor. |
| Paquetes `observabilidad`/`alertas` | Reciben métricas y errores de la API. |

## 4. Requisitos funcionales

**De CU-O07 (Atender solicitud de la API pública):**
- **RF-401** El sistema expone endpoints REST con **contrato OpenAPI versionado**
  (`/v1/...`). *(OT3, SDD)*
- **RF-402** El sistema **autentica** cada solicitud mediante API key / token de
  partner y rechaza credenciales inválidas (401).
- **RF-403** El sistema aplica **rate limiting** por partner/plan y responde 429 al
  superar la cuota.
- **RF-404** El sistema sirve los datos desde **agregaciones ClickHouse**. *(RT-01, RT-02)*
- **RF-405** El sistema **registra cada llamada** en `Fact_Consumo_API` (timestamp,
  endpoint, `Dim_Partner_API`, latencia, código de estado, bytes).
- **RF-406** El sistema valida el esquema de entrada/salida contra el contrato OpenAPI
  y responde 400 ante peticiones malformadas.
- **RF-407** El sistema versiona la API (deprecación controlada; sin cambios rompientes
  dentro de una misma versión mayor).

## 5. Requisitos no funcionales

- **RNF-401 Latencia:** respuesta < 200 ms promedio por región. *(BSC, RNF-G05)*
- **RNF-402 Disponibilidad:** uptime > 99.9% mensual. *(BSC, RNF-G04)*
- **RNF-403 Seguridad:** credenciales nunca en claro; transporte cifrado (TLS).
- **RNF-404 Documentación:** 100% de endpoints con contrato OpenAPI documentado. *(OT3)*
- **RNF-405 Reproducibilidad:** el servicio de API corre en contenedor. *(RT-17)*
- **RNF-406 Trazabilidad:** toda llamada deja registro en `Fact_Consumo_API`.

## 6. Reglas de negocio

- **RN-501** Sin credencial válida no hay respuesta de datos (401). *(RF-402)*
- **RN-502** El consumo se limita a la cuota del plan del partner; excederla devuelve 429. *(RF-403)*
- **RN-503** Los datos servidos provienen **solo de ClickHouse**; prohibido leer de
  StarRocks/PocketBase para servir la API. *(RT-01, RT-02)*
- **RN-504** Toda llamada (exitosa o fallida) se registra en `Fact_Consumo_API`. *(RF-405)*
- **RN-505** Un pico de errores de API por encima del umbral genera alerta. *(RT-16, CU-O13)*
- **RN-506** Cambios rompientes requieren nueva versión mayor; nunca dentro de `/v1`. *(RF-407)*

## 7. Entradas

- **Solicitudes HTTP** del partner (endpoint, parámetros, credencial).
- **Agregaciones ClickHouse** (datos a servir).
- **Metadatos de partner/plan/cuota** (PocketBase, vía `suscripciones`).
- **Contrato OpenAPI** versionado.

## 8. Salidas

- **Respuestas de la API** (datos analíticos, JSON conforme a OpenAPI).
- **Registros en `Fact_Consumo_API`** (llamadas, latencia, errores, partner).
- **Logs y métricas** para observabilidad; eventos de error para alertas.

## 9. Estados posibles

**Solicitud:** `RECIBIDA` → `AUTENTICANDO` → `VERIFICANDO_CUOTA` → `SIRVIENDO` →
`REGISTRADA`. Rutas de error: `RECHAZADA_AUTH` (401), `RECHAZADA_CUOTA` (429),
`RECHAZADA_ESQUEMA` (400), `ERROR_SERVIDOR` (5xx, con alerta).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-401 (llamada nominal):** *Dado* un partner con API key válida y cuota
  disponible, *cuando* llama a `/v1/precios`, *entonces* el sistema sirve desde
  ClickHouse, responde 200 y registra la llamada en `Fact_Consumo_API`. *(RF-404, RF-405)*
- **Esc-402 (credencial inválida — error):** *Dado* una API key revocada, *cuando*
  llama, *entonces* el sistema responde 401 y registra el intento. *(RN-501)*
- **Esc-403 (cuota excedida — error):** *Dado* un partner que superó su cuota,
  *cuando* llama, *entonces* el sistema responde 429. *(RN-502)*
- **Esc-404 (petición malformada — error):** *Dado* un payload que viola el contrato,
  *cuando* llega, *entonces* el sistema responde 400. *(RF-406)*
- **Esc-405 (pico de errores — alerta):** *Dado* un despliegue defectuoso, *cuando*
  los 5xx superan el umbral, *entonces* se genera alerta (CU-O13). *(RN-505)*
- **Esc-406 (capa incorrecta — error):** *Dado* un endpoint nuevo, *cuando* intenta
  leer de StarRocks/PocketBase, *entonces* la revisión lo rechaza. *(RN-503)*

## 11. Criterios de aceptación

- **CA-401** Endpoints expuestos con contrato OpenAPI `/v1` documentado al 100%. *(RF-401, RNF-404)*
- **CA-402** Solicitud autenticada y dentro de cuota responde 200 desde ClickHouse. *(RF-402, RF-404)*
- **CA-403** Credencial inválida → 401; cuota excedida → 429; payload inválido → 400. *(RN-501, RN-502, RF-406)*
- **CA-404** Toda llamada queda registrada en `Fact_Consumo_API` con latencia y estado. *(RF-405, RN-504)*
- **CA-405** Latencia < 200 ms promedio verificada. *(RNF-401)*
- **CA-406** Pico de errores genera alerta. *(RN-505)*

## 12. Dependencias

- **Capas:** ClickHouse (datos), PocketBase (partner/plan/cuota), StarRocks (origen de
  `Fact_Consumo_API` vía ETL, no para servir).
- **Paquetes:** `suscripciones` (OP5, plan/cuota); `etl-calidad` (OP2, modela
  `Fact_Consumo_API`); `observabilidad` (OP7) y `alertas` (OP9).
- **Tablas Fact/Dim:** `Fact_Consumo_API`, `Dim_Partner_API`.
- **Herramientas:** framework API (p. ej. FastAPI), OpenAPI, gateway de rate limiting, Docker.

## 13. Fuera de alcance

- Alta/gestión comercial de partners y planes (es OP5 / `suscripciones`).
- Modelado de `Fact_Consumo_API` en el DW (es OP2 / `etl-calidad`).
- Diseño estratégico/táctico del ecosistema de APIs (CU-T03/CU-T04, fuera del repo).
- Construcción de dashboards de consumo (OP3); aquí solo se registra el consumo.
