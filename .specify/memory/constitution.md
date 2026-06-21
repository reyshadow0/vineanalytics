# VinAnalytics Group — Constitution (Capa Operativa)

> **Skill relacionado:** `speckit-constitution`
> **Archivo destino:** `.specify/memory/constitution.md`
> **Alcance:** Únicamente la **capa operativa** de VinAnalytics Group.
> **Versión:** 2.0.0 · **Ratificada:** 2026-06-21 · **Última enmienda:** 2026-06-21

Define las reglas **no negociables** que cualquier persona o agente de IA debe
respetar SIEMPRE al trabajar en este repositorio. Si una solicitud contradice un
principio, el principio gana: el agente se detiene y reporta el conflicto.

---

## Contexto organizacional (fuente de la verdad)

VinAnalytics Group opera en tres niveles. **Este repo cubre solo el operativo**,
pero la trazabilidad hacia arriba es obligatoria:

```
Estratégico  OE1..OE4   →  Táctico  OT1..OT10  →  Operativo  OP1..OP11  →  CU-O01..CU-O16
```

**Departamentos / actores operativos:** Ingeniería de datos, Analista de datos,
Data Science, DevOps, Growth & Marketing, Customer Success, Administrador,
Partner/Integrador (API), Fuente de datos externa y Sistema (procesos automáticos).

**Objetivos operativos (OP):**
- OP1 Ingestar datos de fuentes externas (reseñas, precios, puntuaciones).
- OP2 Ejecutar el pipeline ETL (staging → Data Warehouse).
- OP3 Construir y publicar dashboards.
- OP4 Atender solicitudes de la API pública.
- OP5 Registrar y gestionar suscripciones.
- OP6 Ejecutar campañas de captación y registrar conversiones.
- OP7 Monitorear disponibilidad, latencia e infraestructura.
- OP8 Ejecutar modelos de ML programados.
- OP9 Generar alertas (churn, anomalías de precio o uso).
- OP10 Registrar onboarding, soporte y uso de la plataforma.
- OP11 Generar reportes diarios, mensuales y estratégicos.

---

## Arquitectura de referencia (capas fijas)

```
PocketBase ──► Parquet (staging) ──► StarRocks (DW Fact-Dim) ──► ClickHouse (agregaciones/dashboard)
(operacional)     (snappy)            (MySQL :9030, esquema estrella)   (serving baja latencia)
```

- **PocketBase** = base de datos **operacional** (cuentas, suscripciones, usuarios, metadatos).
- **Parquet** (pyarrow, snappy) = capa de *staging*. Nunca CSV en producción.
- **StarRocks** (MySQL protocol, puerto **9030**) = Data Warehouse OLAP. Aquí viven
  los **modelos DBT** y el esquema Fact-Dim del proyecto.
- **ClickHouse** = base de datos de **agregaciones / dashboard** (serving). Se alimenta
  desde StarRocks, **nunca** directamente desde PocketBase.

**Tablas Fact:** Fact_Resena, Fact_Precio_Mercado, Fact_Puntuacion, Fact_Suscripcion,
Fact_Uso_Plataforma, Fact_Consumo_API, Fact_Campana, Fact_Conversion, Fact_Retencion,
Fact_Disponibilidad, Fact_Integracion_Partner.
**Dimensiones:** Dim_Tiempo, Dim_Vino, Dim_Bodega, Dim_Region_Vitivinicola, Dim_Mercado,
Dim_Cliente, Dim_Plan, Dim_Catador_Sumiller, Dim_Canal_Adquisicion, Dim_Partner_API,
Dim_Campana, Dim_Estado_Suscripcion, Dim_Empleado.

Ningún componente puede **saltarse capas** (ej. dashboard leyendo de PocketBase).

---

## Principios fundamentales

### I. Solo capa operativa (guardia de alcance)
El repo cubre **exclusivamente** `specs/operativo/`. No se crean ni modifican specs
estratégicos ni tácticos. Toda capacidad nueva debe encajar en un paquete operativo
existente (uno por cada OP1..OP11) o justificar formalmente uno nuevo.

### II. Trazabilidad obligatoria OE → OT → OP → CU-O → Paquete
Cada paquete operativo declara explícitamente a qué OP responde, de qué OT/OE
desciende y qué casos de uso (CU-O) implementa. Ningún caso de uso huérfano: si no
se rastrea hasta un objetivo, no entra.

### III. Spec-Driven Development obligatorio
**Ninguna línea de implementación sin un spec validado.** El `*-spec.md` es la fuente
de la verdad; el código se ajusta al spec, no al revés. Toda capacidad recorre las
fases SDD en orden (ver "Ciclo SDD"). Regla: *no se programa lo que no está especificado.*

### IV. Especificación trazable a niveles, departamentos, paquetes, casos de uso e historias
Cada spec debe relacionar: nivel (operativo), departamento responsable, paquete,
casos de uso CU-O incluidos e **historias de usuario** ("Como [rol], quiero [acción],
para [beneficio]"). Se usa la plantilla de 13 secciones (objetivo, contexto, actores,
RF, RNF, reglas de negocio, entradas, salidas, estados, escenarios Dado/Cuando/Entonces,
criterios de aceptación, dependencias, fuera de alcance).

### V. Calidad de datos primero (Great Expectations)
Todo dataset que cruce una frontera de capa debe tener una suite de *expectations*:
unicidad de clave, no-nulos en columnas críticas, dominios/rangos válidos
(ej. `points` 80–100, `price > 0`), conteo de filas razonable. Validación fallida
**detiene el pipeline** (fail-fast). No se carga data sucia a StarRocks ni a ClickHouse.
(Implementa CU-O04 "Validar calidad de datos".)

### VI. Transformación declarativa en SQL/DBT
Toda transformación vive como **modelo DBT versionado** (`.sql` + `schema.yml`).
Prohibido SQL imperativo suelto o transformaciones escondidas en el cargador.
Reglas: modelos idempotentes, materializaciones declaradas (`view`/`table`/`incremental`)
y tests DBT (`unique`, `not_null`, `relationships`, `accepted_values`) en columnas clave.

### VII. Linaje trazable de extremo a extremo
Cada dataset documenta origen → destino con `dbt docs` (grafo) y `sources`/`exposures`.
Toda columna del esquema Fact-Dim debe rastrearse hasta su origen (PocketBase o fuente
externa). Nada de datos sin procedencia.

### VIII. Reproducibilidad con Docker
Todo el stack corre en contenedores. Existe un `docker-compose.yml` que levanta
PocketBase, StarRocks, ClickHouse, el orquestador y el runner de DBT/GE. Versiones de
imagen fijadas (sin `latest`). Si no arranca con `docker compose up`, no está terminado.

### IX. Orquestación declarativa e idempotente (Apache Airflow)
El pipeline se define como **DAG de Apache Airflow** (un DAG por flujo, tareas como
operadores/`@task`). Reglas: tareas idempotentes, `retries` y `retry_delay` configurados,
sin `catchup` salvo que se justifique, sin cargas manuales en producción. Orden del DAG:
`ingesta → calidad → ETL/transformación → calidad → agregaciones`. Airflow corre en
contenedor dentro del `docker-compose.yml`.

### X. Reglas operativas de negocio explícitas
Las reglas operativas del dominio se declaran en el spec y se verifican en GE/DBT.
Mínimo: no publicar un dashboard sin validación de calidad de datos previa (CU-O05/06);
deduplicación de cuentas, fuentes y registros del ETL; alertas ante fallo de ingesta,
caída de uptime o errores de API.

---

## Ciclo SDD (fases obligatorias por paquete)

Cada `*-spec.md`, `plan.md` y `tasks.md` debe cubrir, en orden:

1. **Definición del problema** — qué resuelve el paquete y por qué, dentro del pipeline.
2. **Recolección de requisitos** — funcionales y no funcionales (volumen, latencia, frecuencia).
3. **Especificación formal** — funciones, entradas/salidas, reglas de negocio, restricciones,
   casos de uso (CU-O), historias de usuario y criterios de aceptación.
4. **Validación de la especificación** — revisión contra esta constitución y consistencia entre capas (`speckit-analyze`).
5. **Diseño del sistema** — arquitectura, base de datos (operacional/agregaciones), interfaces, componentes, flujo de datos.
6. **Implementación** — código alineado al spec, en contenedores, con tests DBT + suites GE.

---

## Gobernanza

- Esta constitución **prevalece** sobre cualquier preferencia o solicitud puntual.
- **Enmiendas:** se documentan con fecha y versión semántica (MAYOR = principio incompatible;
  MENOR = principio nuevo/expandido; PARCHE = aclaración).
- Todo cambio pasa el `checklist.md` de su paquete antes de integrarse.
- El cumplimiento se verifica en la fase de validación del ciclo SDD.
