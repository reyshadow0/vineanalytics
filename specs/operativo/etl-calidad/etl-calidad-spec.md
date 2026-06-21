# etl-calidad · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Ingeniería de datos
> - **Paquete:** `etl-calidad`
> - **Objetivo operativo (OP):** OP2 — Ejecutar el pipeline ETL (staging → Data Warehouse).
> - **Objetivos de origen (OT/OE):** OT7 (Consolidar el Data Warehouse unificado para BI) → OE4 (Inteligencia de Negocio Centralizada).
> - **Casos de uso (CU-O):** CU-O03 (Ejecutar pipeline ETL) y CU-O04 (Validar la calidad de los datos).
> - **Modelo Fact-Dim que toca (matriz §9.8):**
>   - CU-O03 → Staging Parquet → StarRocks (todo el esquema Fact-Dim).
>   - CU-O04 → Todas las Fact (control de calidad) + sus Dim.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Transformar los datos crudos del **staging Parquet** (poblado por `ingesta-datos`,
OP1) y los datos operacionales de **PocketBase** en el esquema dimensional
**Fact-Dim de StarRocks**, mediante **modelos DBT** versionados, y **validar la
calidad** de cada dataset con **Great Expectations** en modo **fail-fast** antes y
después de la carga. Es el corazón del pipeline: convierte data aterrizada en un
Data Warehouse confiable y trazable.

## 2. Contexto

Ocupa los dos eslabones centrales del flujo
(`ingesta → calidad → ETL → calidad → agregaciones`). La validación de calidad
**previa** (sobre staging) y **posterior** (sobre el DW) corresponden a CU-O04; la
transformación declarativa de staging/PocketBase a Fact-Dim en StarRocks corresponde
a CU-O03 vía modelos DBT (`stg_* → dim_* / fct_*`). El paquete consume lo aterrizado
por `ingesta-datos` y entrega un DW listo para que `dashboards`, `machine-learning`
y `reportes-operativos` lo agreguen en ClickHouse. Departamento: **Ingeniería de datos**.

### Historias de usuario

**CU-O03 — Ejecutar pipeline ETL**
- HU-01: *Como Ingeniero de datos, quiero ejecutar modelos DBT que transformen el
  staging Parquet en el esquema Fact-Dim de StarRocks, para tener un DW consultable.*
- HU-02: *Como Sistema, quiero que el ETL sea idempotente e incremental, para
  reprocesar sin duplicar hechos ni romper dimensiones.*
- HU-03: *Como Ingeniero de datos, quiero un reporte de ejecución del ETL (modelos
  corridos, filas, errores, duración), para auditar cada corrida.*

**CU-O04 — Validar la calidad de los datos**
- HU-04: *Como Ingeniero de datos, quiero suites Great Expectations sobre staging y
  sobre el DW, para detectar nulos, duplicados y rangos inválidos antes de servir.*
- HU-05: *Como Sistema, quiero que una validación fallida detenga el pipeline
  (fail-fast), para no cargar datos sucios a StarRocks ni a ClickHouse.*
- HU-06: *Como Ingeniero de datos, quiero un reporte de calidad con el detalle de
  expectativas fallidas, para corregir el origen.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Ingeniero de datos** | Define modelos DBT y suites GE; opera y audita el ETL (CU-O03, CU-O04). |
| **Sistema (procesos automáticos)** | Ejecuta el DAG: validación → ETL → validación. |
| Paquete `ingesta-datos` (OP1) | Provee el staging Parquet de entrada. |
| Paquetes `dashboards`/`machine-learning`/`reportes-operativos` | Consumen el DW resultante. |
| Paquete `alertas` (OP9) | Recibe el evento ante fallo de calidad o de ETL. |

## 4. Requisitos funcionales

**De CU-O04 (Validar la calidad) — se ejecuta antes y después del ETL:**
- **RF-201** El sistema valida el **staging Parquet** con una suite GE por dataset
  (`stg_resena_suite`, `stg_precio_suite`, `stg_puntuacion_suite`): unicidad de clave
  natural, no-nulos críticos, dominios (`precio>0`, `puntaje∈[80,100]`, fecha no
  futura, `moneda` ISO-4217) y conteo de filas razonable.
- **RF-202** Si la suite previa falla, el sistema **detiene el pipeline** (fail-fast)
  y no ejecuta el ETL. *(RT-07)*
- **RF-203** Tras el ETL, el sistema valida el **DW StarRocks** (suites por Fact/Dim)
  e impide la promoción a agregaciones si falla.
- **RF-204** El sistema genera un **reporte de calidad** con expectativas evaluadas,
  fallidas y muestras de filas ofensoras.

**De CU-O03 (Ejecutar pipeline ETL):**
- **RF-205** El sistema ejecuta modelos DBT versionados que materializan
  `Dim_Tiempo`, `Dim_Vino`, `Dim_Bodega`, `Dim_Region_Vitivinicola`, `Dim_Mercado`,
  `Dim_Catador_Sumiller` (y demás Dim necesarias) y los hechos `Fact_Resena`,
  `Fact_Precio_Mercado`, `Fact_Puntuacion` (alcance de ingesta), en StarRocks.
- **RF-206** Los modelos declaran materialización (`view`/`table`/`incremental`) y
  son idempotentes. *(RT-12)*
- **RF-207** El sistema ejecuta tests DBT (`unique`, `not_null`, `relationships`,
  `accepted_values`) en columnas clave. *(RT-13)*
- **RF-208** El sistema resuelve claves foráneas Fact→Dim (integridad referencial).
- **RF-209** El sistema genera un **reporte de ejecución del ETL** (modelos corridos,
  filas afectadas, errores, duración).
- **RF-210** El sistema documenta el **linaje** vía `dbt docs` (`sources`/`exposures`),
  rastreando cada columna Fact-Dim a su origen. *(RT-14)*

## 5. Requisitos no funcionales

- **RNF-201 Fail-fast:** una expectativa GE fallida detiene el pipeline en < 1 tarea. *(RT-07)*
- **RNF-202 Idempotencia:** reejecutar el ETL de una ventana no duplica hechos. *(RT-11)*
- **RNF-203 Calidad mínima:** ≥ 98% de registros válidos en el DW (BSC procesos internos, RT-08).
- **RNF-204 Declaratividad:** 0 SQL imperativo suelto; toda transformación es DBT. *(RT-12)*
- **RNF-205 Reproducibilidad:** runner DBT + GE en contenedor; orquestado por Airflow. *(RT-17)*
- **RNF-206 Rendimiento:** el ETL diario incremental completa dentro de la ventana batch acordada.

## 6. Reglas de negocio

- **RN-301** No se carga data sucia a StarRocks ni a ClickHouse: validación previa
  obligatoria. *(RT-05, RT-07)*
- **RN-302** No se promueve a agregaciones (ClickHouse) sin validación posterior del DW. *(RT-15)*
- **RN-303** Toda transformación a StarRocks es un modelo DBT versionado con tests. *(RT-12, RT-13)*
- **RN-304** Integridad referencial: ningún hecho sin su dimensión (FK válida). *(RT-13)*
- **RN-305** Deduplicación en la transformación además de en la ingesta (defensa en profundidad). *(RT-09)*
- **RN-306** Cada columna del DW debe tener procedencia documentada; sin linaje no se publica. *(RT-14)*

## 7. Entradas

- **Staging Parquet (snappy)** de `ingesta-datos`: reseñas, precios, puntuaciones.
- **PocketBase**: dimensiones operacionales (clientes, planes, fuentes) cuando aplique.
- **Definiciones DBT** (`.sql` + `schema.yml`) y **suites GE**.

## 8. Salidas

- **Data Warehouse StarRocks** con esquema Fact-Dim poblado y testeado.
- **Reporte de calidad** (GE) y **reporte de ejecución del ETL** (DBT).
- **Documentación de linaje** (`dbt docs`, grafo de dependencias).
- **Eventos** de éxito/fallo para observabilidad y alertas.

## 9. Estados posibles

`PENDIENTE` → `VALIDANDO_STAGING` → `TRANSFORMANDO` → `TESTEANDO_DW` →
`VALIDANDO_DW` → `COMPLETADO`. Rutas de error: `BLOQUEADO_POR_CALIDAD` (falla GE
previa o posterior) y `FALLIDO_ETL` (error en modelos/tests DBT). Ambos emiten alerta.

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-201 (flujo nominal):** *Dado* staging válido, *cuando* corre el DAG,
  *entonces* GE previa pasa, los modelos DBT cargan el Fact-Dim, GE posterior pasa y
  el estado es `COMPLETADO`.
- **Esc-202 (calidad previa falla):** *Dado* staging con `puntaje=120`, *cuando* la
  suite previa evalúa el dominio, *entonces* detiene el pipeline en
  `BLOQUEADO_POR_CALIDAD`, **no** ejecuta el ETL y emite alerta. *(RF-202, RN-301)*
- **Esc-203 (test DBT falla):** *Dado* un `Fact_Precio_Mercado` con FK de mercado
  inexistente, *cuando* corre el test `relationships`, *entonces* el ETL falla en
  `FALLIDO_ETL` y no se promueve a agregaciones. *(RN-304, Esc)*
- **Esc-204 (calidad posterior falla):** *Dado* un DW cargado con duplicados,
  *cuando* la suite posterior detecta clave repetida, *entonces* bloquea la
  promoción a ClickHouse y emite alerta. *(RF-203, RN-302)*
- **Esc-205 (reejecución idempotente):** *Dado* una ventana ya transformada,
  *cuando* se reejecuta el ETL incremental, *entonces* no se duplican hechos. *(RNF-202)*
- **Esc-206 (linaje incompleto):** *Dado* un modelo nuevo sin `source` declarado,
  *cuando* se intenta publicar, *entonces* la revisión lo rechaza por falta de
  procedencia. *(RN-306, RT-14)*

## 11. Criterios de aceptación

- **CA-201** GE previa sobre staging pasa antes de ejecutar cualquier modelo DBT. *(RF-201)*
- **CA-202** Una expectativa fallida detiene el pipeline y bloquea la carga. *(RF-202, CA fail-fast)*
- **CA-203** El DW StarRocks contiene los Fact/Dim del alcance, materializados por DBT. *(RF-205)*
- **CA-204** Tests DBT (`unique`, `not_null`, `relationships`, `accepted_values`) pasan. *(RF-207)*
- **CA-205** GE posterior pasa antes de promover a agregaciones. *(RF-203, RN-302)*
- **CA-206** `dbt docs` muestra el linaje completo staging→Fact-Dim. *(RF-210)*
- **CA-207** Reejecución incremental no duplica hechos. *(RNF-202)*
- **CA-208** Reportes de calidad y de ejecución generados por corrida. *(RF-204, RF-209)*

## 12. Dependencias

- **Capas:** Parquet (entrada), StarRocks (salida del ETL), ClickHouse (consumidor posterior).
- **Paquetes:** `ingesta-datos` (OP1, provee staging); `dashboards` (OP3),
  `machine-learning` (OP8) y `reportes-operativos` (OP11) consumen el DW;
  `observabilidad`/`alertas` reciben eventos.
- **Tablas Fact/Dim:** materializa todo el esquema; control de calidad sobre todas las Fact.
- **Herramientas:** DBT, Great Expectations, StarRocks (MySQL :9030), Airflow, Docker.

## 13. Fuera de alcance

- Ingesta y aterrizaje a Parquet (es OP1 / `ingesta-datos`).
- Agregaciones de serving en ClickHouse y construcción de dashboards (OP3).
- Entrenamiento de modelos de ML (OP8); aquí solo se prepara el DW que consumen.
- Hechos fuera del alcance de ingesta (suscripción, uso, API, etc.) se modelan en sus
  paquetes respectivos, reutilizando este marco DBT/GE.
