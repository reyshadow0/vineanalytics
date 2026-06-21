# Prompt — Especificación e implementación de la capa operativa de VinAnalytics

Pega este prompt en Claude (o tu agente) dentro del repo, con la constitución ya
guardada en `.specify/memory/constitution.md`. Cubre los 3 puntos de la tarea:
(1) construcción ya hecha en la constitución, (2) especificación operativa,
(3) generación del sistema operativo.

Adjunta SIEMPRE tu archivo `Desarrollo_Empresarial_VinAnalytics.md` como contexto:
de ahí salen los objetivos, departamentos, casos de uso y modelo Fact-Dim reales.

---

## PROMPT

Eres un agente de Spec-Driven Development trabajando en **VinAnalytics Group**.
Antes de generar nada, lee y respeta `.specify/memory/constitution.md` (reglas no
negociables) y el documento adjunto `Desarrollo_Empresarial_VinAnalytics.md`
(fuente de objetivos, departamentos, casos de uso y modelo Fact-Dim).

### Reglas de alcance
- Genera ÚNICAMENTE la rama `specs/operativo/`. No toques estratégico ni táctico.
- TODO debe ser trazable: cada paquete declara su OP, su OT/OE de origen, sus CU-O
  y su departamento responsable. No inventes casos de uso: usa los del documento.

### Stack real (capas fijas, no saltar capas)
PocketBase (operacional) → Parquet (staging, snappy) → StarRocks (DW Fact-Dim, MySQL :9030,
modelos DBT) → ClickHouse (agregaciones / dashboard). Calidad con Great Expectations,
linaje con dbt docs, orquestación con Apache Airflow (DAG), todo en Docker.

### Estructura a generar (un paquete por objetivo operativo)
```
specs/
└── operativo/
    ├── 000-general/
    │   ├── operativo-general-spec.md   (visión operativa, arquitectura, flujo de datos)
    │   ├── glossary.md                  (Fact_*, Dim_*, términos del dominio)
    │   └── rules.md                     (reglas operativas transversales)
    ├── ingesta-datos/          # OP1  · CU-O01, CU-O02 · Ingeniería de datos
    ├── etl-calidad/            # OP2  · CU-O03, CU-O04 · Ingeniería de datos
    ├── dashboards/             # OP3  · CU-O05, CU-O06 · Analista de datos
    ├── api-publica/            # OP4  · CU-O07          · Sistema / Partner
    ├── suscripciones/          # OP5  · CU-O08          · Administrador
    ├── captacion-conversion/   # OP6  · CU-O09, CU-O10  · Growth & Marketing
    ├── observabilidad/         # OP7  · CU-O11          · DevOps
    ├── machine-learning/       # OP8  · CU-O12          · Data Science
    ├── alertas/                # OP9  · CU-O13          · Sistema
    ├── customer-success/       # OP10 · CU-O14, CU-O15  · Customer Success
    └── reportes-operativos/    # OP11 · CU-O16          · Administrador
```
Cada paquete (excepto 000-general) contiene exactamente:
`<paquete>-spec.md`, `plan.md`, `tasks.md`, `checklist.md`.

### Contenido obligatorio de cada `<paquete>-spec.md` (plantilla de 13 secciones)
Encabeza con un bloque de trazabilidad: **Nivel** (operativo), **Departamento**,
**Paquete**, **Objetivo operativo (OP)**, **Objetivos de origen (OT/OE)** y
**Casos de uso (CU-O)**. Luego:

1. Objetivo
2. Contexto
3. Actores
4. Requisitos funcionales (RF-XXX) — uno o varios por cada CU-O del paquete
5. Requisitos no funcionales (RNF-XXX)
6. Reglas de negocio (RN-XXX)
7. Entradas
8. Salidas
9. Estados posibles
10. Escenarios (formato Dado / Cuando / Entonces, incluyendo casos de error)
11. Criterios de aceptación (CA-XXX, medibles y verificables)
12. Dependencias (otros paquetes, capas o tablas Fact/Dim)
13. Fuera de alcance

Añade también, por cada CU-O del paquete, una o más **historias de usuario**:
"Como [rol/departamento], quiero [acción], para [beneficio]."
Indica el modelo Fact-Dim que toca cada caso (según la matriz 9.8 del documento).

### Archivos de apoyo por paquete
- `plan.md` (speckit-plan): arquitectura del paquete, herramientas, modelo de datos,
  secuencia de implementación y riesgos.
- `tasks.md` (speckit-tasks): tareas atómicas numeradas y marcables `[ ]`, ordenadas por dependencia.
- `checklist.md` (speckit-checklist): Definición de Terminado. Incluye SIEMPRE: spec validado
  contra la constitución, tests DBT pasando, suite Great Expectations pasando, linaje
  documentado, contenedores levantando con `docker compose up`.

### Reglas de salida (specs)
- En español, concretos y accionables, sin relleno.
- Usa nombres reales del dominio y del esquema Fact-Dim del documento.
- Si pones diagramas, que NO sean miniaturas ni alargados: tamaño legible y proporciones normales.
- Crea los archivos en disco con esa estructura exacta y muéstrame el árbol final.

---

## PUNTO 3 — Generar el sistema operativo (después de aprobar las specs)

Una vez validadas las specs, genera el sistema operativo mínimo funcional, en
contenedores, siguiendo estrictamente las specs (no programes lo que no está especificado):

1. `docker-compose.yml` con PocketBase, StarRocks, ClickHouse, Apache Airflow y runner DBT/GE.
2. **Ingesta** (OP1): conector de fuente externa + carga a Parquet (pyarrow/snappy).
3. **ETL** (OP2): extracción desde PocketBase/Parquet → transformación → StarRocks.
4. **Calidad** (OP2/CU-O04): suites Great Expectations con fail-fast.
5. **Modelos DBT** sobre StarRocks: Fact-Dim del documento + tests DBT + dbt docs (linaje).
6. **Agregaciones** en ClickHouse para dashboard (MRR, churn, uptime, conversión, etc.).
7. **Orquestación** (Apache Airflow): un DAG con el orden ingesta → calidad → ETL → calidad → agregaciones.
8. README operativo: cómo levantar todo y cómo correr el pipeline.

Mantén el orden del flujo de datos. Empieza por `000-general/` y `ingesta-datos/`.
