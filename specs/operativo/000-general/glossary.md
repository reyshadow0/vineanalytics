# 000-general · Glosario operativo — VinAnalytics Group

Glosario único del dominio para toda la capa operativa. Los nombres de tablas y
columnas son **canónicos**: cualquier paquete, modelo DBT o suite GE debe usarlos
tal cual. Fuente: `Desarrollo_Empresarial_VinAnalytics.md` §9.3–§9.8 y la
[constitución](../../../.specify/memory/constitution.md).

---

## 1. Capas del stack

| Término | Definición |
|---|---|
| **PocketBase** | Base de datos **operacional**: cuentas, suscripciones, usuarios, metadatos y **catálogo de fuentes**. Origen del linaje operacional. |
| **Parquet (staging)** | Capa intermedia columnar (pyarrow, compresión **snappy**). Aterriza la ingesta cruda y limpia antes del DW. Nunca CSV en producción. |
| **StarRocks** | Data Warehouse OLAP (protocolo MySQL, puerto **9030**). Aloja el esquema **Fact-Dim** y los modelos **DBT**. |
| **ClickHouse** | Base de **agregaciones / serving** para dashboards, API y reportes. Se alimenta **solo** desde StarRocks. |
| **DBT** | Herramienta de transformación declarativa (modelos `.sql` + `schema.yml`) sobre StarRocks. |
| **Great Expectations (GE)** | Framework de validación de calidad de datos con **fail-fast**. |
| **Apache Airflow** | Orquestador del pipeline como **DAG** idempotente. |

## 2. Tablas de hechos (Fact) — eventos medibles

| Tabla Fact | Qué mide | Métricas típicas |
|---|---|---|
| **Fact_Resena** | Reseñas de sumilleres ingeridas | cantidad, sentimiento, palabras clave |
| **Fact_Precio_Mercado** | Precios de mercado del vino | precio, variación, moneda, región |
| **Fact_Puntuacion** | Puntuaciones de catadores | puntaje (80–100), escala, nº de catas |
| **Fact_Suscripcion** | Suscripciones e ingresos recurrentes | MRR, ARR, upgrades, downgrades |
| **Fact_Uso_Plataforma** | Uso y engagement de clientes | sesiones, dashboards vistos, funciones |
| **Fact_Consumo_API** | Consumo de la API pública | llamadas, latencia, errores, partner |
| **Fact_Campana** | Campañas de marketing | impresiones, clics, gasto, leads |
| **Fact_Conversion** | Embudo de conversión | leads, oportunidades, conversiones, CAC |
| **Fact_Retencion** | Retención y churn | activos, cancelaciones, LTV |
| **Fact_Disponibilidad** | Salud de la infraestructura | uptime, latencia, incidentes, SLA |
| **Fact_Integracion_Partner** | Integraciones de ecosistema | conexiones activas, ingresos por API |

## 3. Dimensiones (Dim) — contexto de los hechos

| Dimensión | Uso |
|---|---|
| **Dim_Tiempo** | día, semana, mes, trimestre, año |
| **Dim_Vino** | variedad, tipo, añada, gama de precio |
| **Dim_Bodega** | productor, tamaño, país de origen |
| **Dim_Region_Vitivinicola** | región y denominación de origen del vino |
| **Dim_Mercado** | país o mercado destino internacional |
| **Dim_Cliente** | cuenta B2B: tipo, tamaño, segmento |
| **Dim_Plan** | plan de suscripción: básico, profesional, enterprise |
| **Dim_Catador_Sumiller** | fuente de reseñas y puntuaciones |
| **Dim_Canal_Adquisicion** | orgánico, pago, referido, marketplace |
| **Dim_Partner_API** | integrador o marketplace conectado |
| **Dim_Campana** | campaña, región, segmento objetivo |
| **Dim_Estado_Suscripcion** | prueba, activa, en pausa, cancelada |
| **Dim_Empleado** | empleado (capacitación, responsable) |

## 4. Términos del dominio y de negocio

| Término | Definición |
|---|---|
| **Fuente de datos externa** | Proveedor de reseñas, precios o puntuaciones; se registra en el catálogo (CU-O01) con tipo, frecuencia y formato. |
| **Ingesta** | Aterrizaje de datos crudos desde una fuente externa a Parquet staging (CU-O02). |
| **Staging** | Zona Parquet previa al DW donde se limpia y deduplica. |
| **Esquema estrella (Fact-Dim)** | Modelo dimensional: hechos rodeados de dimensiones. |
| **Linaje** | Trazabilidad origen → destino de cada dataset/columna (`dbt docs`). |
| **MRR / ARR** | Ingreso recurrente mensual / anual. |
| **CAC** | Costo de adquisición de clientes. |
| **Churn** | Tasa de cancelación de clientes. |
| **LTV** | Valor de vida del cliente. |
| **NPS** | Net Promoter Score (satisfacción). |
| **Uptime** | % de tiempo operativo de la plataforma. |
| **CU-O** | Caso de uso operativo (CU-O01..CU-O16). |
| **OP / OT / OE** | Objetivo operativo / táctico / estratégico. |
| **Fail-fast** | Estrategia: ante validación fallida, detener el pipeline de inmediato. |
| **Idempotencia** | Propiedad de reejecutar sin duplicar ni corromper. |

## 5. Reglas de nomenclatura

- Tablas Fact: prefijo `Fact_` + sustantivo en singular (`Fact_Resena`).
- Dimensiones: prefijo `Dim_` + sustantivo (`Dim_Cliente`).
- Modelos DBT staging: `stg_<fuente>__<entidad>`; modelos de marca: `fct_*` / `dim_*`.
- Suites GE: `<dataset>_suite` (p. ej. `stg_resena_suite`).
- DAGs Airflow: `dag_<flujo>` (p. ej. `dag_pipeline_diario`).
