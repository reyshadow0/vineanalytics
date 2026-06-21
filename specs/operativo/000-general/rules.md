# 000-general · Reglas operativas transversales — VinAnalytics Group

Reglas de negocio y técnicas **obligatorias para todos los paquetes** operativos.
Derivan de la [constitución](../../../.specify/memory/constitution.md) (principios
I–X) y del documento de negocio (§9.5.C "Nivel operativo"). Cada regla es
verificable en GE, DBT o en revisión de arquitectura.

---

## 1. Reglas de capas y flujo

- **RT-01** No saltar capas: `PocketBase → Parquet → StarRocks → ClickHouse`.
  Prohibido que un dashboard o reporte lea de PocketBase o de Parquet. *(Const. Arq., Princ. I)*
- **RT-02** ClickHouse se alimenta **solo** desde StarRocks, nunca desde PocketBase.
- **RT-03** Orden inmutable del DAG: `ingesta → calidad → ETL → calidad → agregaciones`. *(Princ. IX)*
- **RT-04** Nunca CSV en producción; el staging es **Parquet snappy**. *(Princ., Arq.)*

## 2. Reglas de calidad de datos (fail-fast)

- **RT-05** Todo dataset que cruce una frontera de capa tiene una suite Great
  Expectations: unicidad de clave, no-nulos en columnas críticas, dominios/rangos
  y conteo de filas razonable. *(Princ. V, CU-O04)*
- **RT-06** Rangos de dominio canónicos verificables: `points` ∈ [80, 100],
  `price > 0`, `moneda` en catálogo ISO-4217, fechas no futuras.
- **RT-07** Validación fallida **detiene** el pipeline; no se carga data sucia a
  StarRocks ni a ClickHouse. *(Princ. V, X)*
- **RT-08** Meta de calidad del DW: ≥ 98% de registros válidos (BSC procesos internos).

## 3. Reglas de deduplicación e idempotencia

- **RT-09** Deduplicación obligatoria de cuentas, fuentes y registros del ETL. *(Princ. X, §9.5.C)*
- **RT-10** Toda fuente externa se registra una sola vez en el catálogo; un alta
  duplicada (mismo tipo + endpoint + formato) se rechaza. *(CU-O01)*
- **RT-11** Ingesta, ETL, modelos DBT y tareas Airflow son idempotentes: reejecutar
  un lote no duplica filas (clave natural + ventana temporal). *(Princ. IX)*

## 4. Reglas de transformación y linaje

- **RT-12** Toda transformación a StarRocks es un modelo DBT versionado con
  materialización declarada (`view`/`table`/`incremental`). *(Princ. VI)*
- **RT-13** Tests DBT obligatorios en columnas clave: `unique`, `not_null`,
  `relationships`, `accepted_values`. *(Princ. VI)*
- **RT-14** Cada columna Fact-Dim se rastrea hasta su origen vía `sources`/`exposures`
  y se documenta en `dbt docs`. Nada sin procedencia. *(Princ. VII)*

## 5. Reglas de publicación y alertas

- **RT-15** No publicar un dashboard sin validación de calidad de datos previa
  (CU-O04 antes de CU-O05/CU-O06). *(Princ. X, §9.5.C)*
- **RT-16** Generar alerta ante: fallo de ingesta, caída de uptime bajo el SLA o
  errores de API por encima del umbral. *(Princ. X, CU-O13, §9.5.C)*

## 6. Reglas de reproducibilidad y gobernanza

- **RT-17** Todo el stack levanta con `docker compose up`; imágenes con versión
  fijada (sin `latest`). Si no arranca, no está terminado. *(Princ. VIII)*
- **RT-18** Spec-Driven Development: ninguna implementación sin `*-spec.md`
  validado; el código se ajusta al spec. *(Princ. III)*
- **RT-19** Trazabilidad obligatoria: cada paquete declara su OP, OT/OE, CU-O y
  departamento. Ningún CU-O huérfano. *(Princ. II, IV)*
- **RT-20** Ante conflicto entre una solicitud y una regla/constitución, **gana la
  norma**: el agente se detiene y reporta el conflicto. *(Const. Gobernanza)*

---

## Matriz regla → mecanismo de verificación

| Regla | Verificado por |
|---|---|
| RT-05, RT-06, RT-07, RT-08 | Suites Great Expectations (CU-O04) |
| RT-09, RT-10, RT-11 | GE (unicidad) + tests DBT `unique` + claves naturales |
| RT-12, RT-13, RT-14 | Tests DBT + `dbt docs generate` |
| RT-01..RT-04, RT-15, RT-17 | Revisión de arquitectura + `docker compose config` |
| RT-16 | Paquete `alertas` (CU-O13) |
| RT-18, RT-19, RT-20 | `speckit-analyze` + revisión de constitución |
