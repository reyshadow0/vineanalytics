# 000-general · Especificación operativa general — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Ingeniería de datos (coordina), con DevOps, Analista de datos, Data Science, Growth & Marketing, Customer Success y Administrador como consumidores.
> - **Paquete:** `000-general` (paquete transversal de la capa operativa).
> - **Objetivo operativo (OP):** transversal a OP1..OP11 (no implementa un OP único; fija el marco común).
> - **Objetivos de origen (OT/OE):** transversal a OE1..OE4 y OT1..OT10 (ver matriz §2).
> - **Casos de uso (CU-O):** marco común para CU-O01..CU-O16 (no implementa ninguno por sí solo).

Este documento es la **base normativa operativa**. Cada paquete (`ingesta-datos`,
`etl-calidad`, `dashboards`, …) hereda de aquí la arquitectura, el glosario
([glossary.md](glossary.md)) y las reglas transversales ([rules.md](rules.md)).
Si un paquete contradice este documento o la
[constitución](../../../.specify/memory/constitution.md), gana la constitución.

---

## 1. Objetivo

Establecer la visión, la arquitectura de referencia, el flujo de datos y el marco
de trazabilidad **comunes a toda la capa operativa** de la plataforma VinAnalytics,
de modo que los once paquetes operativos (OP1..OP11) compartan un mismo stack, un
mismo glosario Fact-Dim y unas mismas reglas de negocio transversales, sin saltarse
capas ni duplicar definiciones.

## 2. Contexto

VinAnalytics Group es una empresa de inteligencia de datos para el mercado
vitivinícola internacional. La organización opera en tres niveles
(estratégico → táctico → operativo). **Este repositorio cubre exclusivamente el
nivel operativo**: la ejecución diaria de la plataforma (ingesta, ETL, dashboards,
API, suscripciones, campañas, observabilidad, ML, alertas, soporte y reportes).

La trazabilidad ascendente es obligatoria. Mapa OE → OT → OP por paquete:

| Paquete operativo | OP | OT de origen | OE de origen | CU-O |
|---|---|---|---|---|
| `ingesta-datos` | OP1 | OT7 | OE4 | CU-O01, CU-O02 |
| `etl-calidad` | OP2 | OT7 | OE4 | CU-O03, CU-O04 |
| `dashboards` | OP3 | OT7 | OE4 | CU-O05, CU-O06 |
| `api-publica` | OP4 | OT3, OT4 | OE2 | CU-O07 |
| `suscripciones` | OP5 | OT4 | OE2 | CU-O08 |
| `captacion-conversion` | OP6 | OT1, OT2 | OE1 | CU-O09, CU-O10 |
| `observabilidad` | OP7 | OT5, OT6 | OE3 | CU-O11 |
| `machine-learning` | OP8 | OT8 | OE4 | CU-O12 |
| `alertas` | OP9 | OT8 | OE4 | CU-O13 |
| `customer-success` | OP10 | OT9 | OE1 | CU-O14, CU-O15 |
| `reportes-operativos` | OP11 | OT7 | OE4 | CU-O16 |

## 3. Actores

| Actor | Rol operativo |
|---|---|
| Ingeniero de datos | Registra fuentes, opera ingesta, ETL y el Data Warehouse. |
| Analista de datos | Construye y publica dashboards sobre las agregaciones. |
| Data Scientist | Ejecuta y monitorea modelos de ML programados. |
| DevOps | Opera la infraestructura, despliegues y observabilidad. |
| Growth & Marketing | Ejecuta campañas y registra conversiones. |
| Customer Success | Registra onboarding, soporte y consulta el uso. |
| Administrador | Gestiona cuentas, suscripciones y reportes operativos. |
| Partner / Integrador (API) | Consume la API pública. |
| Fuente de datos externa | Provee reseñas, precios y puntuaciones. |
| Sistema (procesos automáticos) | Ejecuta ETL, calidad, ML, alertas y agregaciones. |

## 4. Requisitos funcionales (transversales)

- **RF-G01** Todo paquete operativo debe declarar su bloque de trazabilidad
  (Nivel, Departamento, Paquete, OP, OT/OE, CU-O) al inicio de su `*-spec.md`.
- **RF-G02** Todo dataset que cruce una frontera de capa debe persistirse en el
  formato de esa capa: PocketBase (operacional), Parquet snappy (staging),
  StarRocks (DW Fact-Dim), ClickHouse (agregaciones). Nunca CSV en producción.
- **RF-G03** Ningún componente lee de una capa que no sea su origen inmediato
  (p. ej. el dashboard nunca lee de PocketBase ni de Parquet; lee de ClickHouse).
- **RF-G04** Toda transformación hacia StarRocks es un modelo DBT versionado
  (`.sql` + `schema.yml`); no se admite SQL imperativo suelto.
- **RF-G05** El flujo de datos se ejecuta como DAG de Airflow en el orden fijo
  `ingesta → calidad → ETL → calidad → agregaciones`.
- **RF-G06** Toda columna del esquema Fact-Dim debe ser rastreable hasta su origen
  (PocketBase o fuente externa) vía `dbt docs` (`sources`/`exposures`).

## 5. Requisitos no funcionales (transversales)

- **RNF-G01 Reproducibilidad:** todo el stack levanta con `docker compose up`
  usando imágenes con versión fijada (sin `latest`).
- **RNF-G02 Idempotencia:** ingesta, ETL, modelos DBT y tareas Airflow son
  idempotentes (reejecutar no duplica ni corrompe datos).
- **RNF-G03 Fail-fast de calidad:** una validación Great Expectations fallida
  detiene el pipeline antes de cargar a StarRocks o ClickHouse.
- **RNF-G04 Disponibilidad:** objetivo de uptime de la plataforma > 99.9% mensual.
- **RNF-G05 Latencia de serving:** las consultas de dashboard sobre ClickHouse
  responden en < 200 ms promedio por región.
- **RNF-G06 Trazabilidad:** todo artefacto enlaza a su OP/OT/OE y CU-O.

## 6. Reglas de negocio (transversales)

Las reglas detalladas viven en [rules.md](rules.md). Las invariantes mínimas:

- **RN-G01** No se publica un dashboard sin validación de calidad de datos previa
  (CU-O04 antes de CU-O05/CU-O06).
- **RN-G02** Deduplicación obligatoria de cuentas, fuentes y registros del ETL.
- **RN-G03** Toda ingesta, caída de uptime o error de API que supere su umbral
  genera una alerta (CU-O13).
- **RN-G04** No se programa ninguna implementación sin un `*-spec.md` validado
  (Spec-Driven Development).

## 7. Entradas

- Fuentes externas: reseñas de sumilleres, precios de mercado, puntuaciones de
  catadores y tendencias geográficas.
- PocketBase: cuentas, suscripciones, usuarios, metadatos y catálogo de fuentes.
- Especificaciones de cada paquete (`*-spec.md`, `plan.md`, `tasks.md`).

## 8. Salidas

- Capa de staging Parquet (snappy) poblada por la ingesta.
- Data Warehouse StarRocks con el esquema Fact-Dim del dominio.
- Agregaciones en ClickHouse que sirven dashboards, API y reportes.
- Documentación de linaje (`dbt docs`) y suites de calidad (GE).

## 9. Estados posibles (del flujo operativo global)

`INACTIVO` → `INGESTANDO` → `VALIDANDO_STAGING` → `TRANSFORMANDO_ETL` →
`VALIDANDO_DW` → `AGREGANDO` → `DISPONIBLE`. Cualquier fallo de validación lleva a
`BLOQUEADO_POR_CALIDAD`; cualquier fallo técnico, a `FALLIDO` (con alerta).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-G01 (flujo nominal):** *Dado* un DAG diario, *cuando* la ingesta, ambas
  validaciones y el ETL terminan sin error, *entonces* ClickHouse queda con
  agregaciones frescas y el estado global es `DISPONIBLE`.
- **Esc-G02 (calidad falla):** *Dado* un lote en staging, *cuando* la suite GE
  falla, *entonces* el DAG se detiene en `BLOQUEADO_POR_CALIDAD`, no se carga a
  StarRocks y se emite alerta. (RNF-G03, RN-G03)
- **Esc-G03 (salto de capa prohibido):** *Dado* un nuevo componente, *cuando*
  intenta leer dashboards directamente de PocketBase, *entonces* la revisión de
  arquitectura lo rechaza por violar RF-G03.

## 11. Criterios de aceptación

- **CA-G01** El árbol `specs/operativo/` contiene un paquete por cada OP1..OP11 más
  `000-general/`, y cada paquete (salvo `000-general`) tiene exactamente
  `*-spec.md`, `plan.md`, `tasks.md`, `checklist.md`.
- **CA-G02** Cada `*-spec.md` incluye su bloque de trazabilidad completo y las 13
  secciones de la plantilla.
- **CA-G03** No existe ninguna referencia a CU-O huérfano: cada CU-O del documento
  está asignado a exactamente un paquete (ver matriz §2).
- **CA-G04** `docker compose config` valida sin imágenes `latest`.

## 12. Dependencias

- [constitución](../../../.specify/memory/constitution.md) (norma superior).
- [glossary.md](glossary.md) y [rules.md](rules.md) de este mismo paquete.
- Documento de negocio `Desarrollo_Empresarial_VinAnalytics.md` (fuente de OE/OT/OP,
  actores, CU-O y matriz Fact-Dim §9.3–§9.8).

## 13. Fuera de alcance

- Specs estratégicos (CU-E*) y tácticos (CU-T*): prohibidos por la constitución.
- Implementación concreta de cada OP (vive en su paquete, no aquí).
- Decisiones de negocio de nivel estratégico (precios, mercados, alianzas).

---

## Arquitectura de referencia (capas fijas)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  PocketBase  │ ──► │   Parquet    │ ──► │      StarRocks       │ ──► │  ClickHouse  │
│ (operacional)│     │  (staging,   │     │ (DW Fact-Dim, OLAP,  │     │(agregaciones │
│ cuentas,     │     │   snappy)    │     │  MySQL :9030, DBT)   │     │  / dashboard)│
│ suscripciones│     │              │     │                      │     │  serving     │
└──────────────┘     └──────────────┘     └──────────────────────┘     └──────────────┘
        │                    ▲
        │  fuentes externas  │
        └─ reseñas / precios ┘
           puntuaciones
```

## Flujo de datos (DAG de Airflow, orden fijo)

```
[ingesta] ──► [calidad: GE staging] ──► [ETL/transformación DBT] ──► [calidad: GE/tests DW] ──► [agregaciones ClickHouse]
   OP1               CU-O04                   OP2 / CU-O03                  CU-O04                    OP3 base
    │                  │ fail-fast               │                           │ fail-fast               │
    └── alerta ────────┴── alerta ───────────────┴───────────────────────────┴── alerta ───────────────┘  (OP9 / CU-O13)
```
