# ingesta-datos · Especificación — VinAnalytics Group

> **Bloque de trazabilidad**
> - **Nivel:** Operativo
> - **Departamento responsable:** Ingeniería de datos
> - **Paquete:** `ingesta-datos`
> - **Objetivo operativo (OP):** OP1 — Ingestar datos de fuentes externas (reseñas, precios, puntuaciones).
> - **Objetivos de origen (OT/OE):** OT7 (Consolidar el Data Warehouse unificado para BI) → OE4 (Inteligencia de Negocio Centralizada para la ventaja competitiva global).
> - **Casos de uso (CU-O):** CU-O01 (Registrar fuente de datos externa) y CU-O02 (Ingestar datos: reseñas, precios, puntuaciones).
> - **Modelo Fact-Dim que toca (matriz §9.8):**
>   - CU-O01 → `Dim_Catador_Sumiller`, `Dim_Mercado`.
>   - CU-O02 → `Fact_Resena`, `Fact_Precio_Mercado`, `Fact_Puntuacion`.

Hereda arquitectura, glosario y reglas de [000-general](../000-general/operativo-general-spec.md),
[glossary.md](../000-general/glossary.md) y [rules.md](../000-general/rules.md).

---

## 1. Objetivo

Registrar y gobernar las **fuentes de datos externas** del mercado vitivinícola
(reseñas de sumilleres, precios de mercado, puntuaciones de catadores) y **ingerir**
sus datos de forma idempotente y deduplicada hacia la capa de **staging Parquet
(snappy)**, validando esquema en el aterrizaje, para que el ETL (OP2) los promueva
luego al Data Warehouse StarRocks. Es el **primer eslabón** del flujo de datos:
sin ingesta confiable no hay DW, ni dashboards, ni API, ni ML.

## 2. Contexto

Es el inicio del pipeline (`ingesta → calidad → ETL → calidad → agregaciones`).
El **catálogo de fuentes** (CU-O01) vive en **PocketBase** (capa operacional): cada
fuente declara su tipo, frecuencia, formato y endpoint. La **ingesta** (CU-O02) lee
de la fuente externa y aterriza los datos crudos en **Parquet snappy** (staging),
aplicando validación de esquema y deduplicación por clave natural. La validación de
calidad profunda (Great Expectations, CU-O04) y la transformación a Fact-Dim
(CU-O03) pertenecen al paquete `etl-calidad` (OP2); aquí solo se garantiza un
aterrizaje limpio y trazable. Departamento responsable: **Ingeniería de datos**.

### Historias de usuario

**CU-O01 — Registrar fuente de datos externa**
- HU-01: *Como Ingeniero de datos, quiero registrar una fuente externa con su tipo,
  frecuencia, formato y endpoint, para que la ingesta sepa de dónde y cada cuánto leer.*
- HU-02: *Como Ingeniero de datos, quiero que el sistema rechace fuentes duplicadas,
  para mantener un catálogo limpio y sin ingestas repetidas.*
- HU-03: *Como Ingeniero de datos, quiero validar la conectividad y el esquema de la
  fuente al registrarla, para no descubrir errores recién en producción.*

**CU-O02 — Ingestar datos (reseñas, precios, puntuaciones)**
- HU-04: *Como Sistema, quiero ejecutar la ingesta programada de cada fuente activa y
  aterrizar los datos en Parquet snappy, para alimentar el staging del pipeline.*
- HU-05: *Como Sistema, quiero validar el esquema y deduplicar cada lote ingerido,
  para no propagar datos malformados o repetidos al Data Warehouse.*
- HU-06: *Como Ingeniero de datos, quiero un reporte de ingesta (filas leídas,
  cargadas, rechazadas y duplicadas) por lote, para auditar y detectar problemas.*

## 3. Actores

| Actor | Participación |
|---|---|
| **Ingeniero de datos** | Registra y mantiene fuentes (CU-O01); supervisa la ingesta y revisa el reporte. |
| **Sistema (procesos automáticos)** | Ejecuta la ingesta programada y aterriza a Parquet (CU-O02). |
| **Fuente de datos externa** | Provee reseñas, precios y puntuaciones (API/archivo/feed). |
| Paquete `alertas` (OP9) | Recibe el evento ante fallo de ingesta (consumidor). |

## 4. Requisitos funcionales

**De CU-O01 (Registrar fuente de datos externa):**
- **RF-101** El sistema permite registrar una fuente con: `nombre`, `tipo`
  (reseñas | precios | puntuaciones), `formato` (json | parquet | api | csv-origen),
  `endpoint`/origen, `frecuencia` (cron) y `mercado`/`catador` asociado.
- **RF-102** Antes de aceptar el alta, el sistema valida conectividad y el esquema
  mínimo esperado de la fuente (campos obligatorios según `tipo`).
- **RF-103** El sistema persiste el catálogo de fuentes en **PocketBase** y asocia
  cada fuente a `Dim_Catador_Sumiller` (reseñas/puntuaciones) y/o `Dim_Mercado`.
- **RF-104** El sistema rechaza un alta duplicada (misma combinación
  `tipo + endpoint + formato`) y devuelve el id de la fuente existente. *(RT-10)*
- **RF-105** El sistema permite activar, pausar y dar de baja una fuente sin borrar
  su historial de ingestas.

**De CU-O02 (Ingestar datos):**
- **RF-106** Para cada fuente **activa**, el sistema ejecuta la ingesta según su
  `frecuencia`, leyendo solo el incremento (ventana temporal o cursor).
- **RF-107** El sistema valida el **esquema** de cada registro entrante; los
  registros que no cumplen se desvían a un área de rechazo (`rejects/`) sin detener
  el lote, salvo que el % de rechazo supere el umbral (ver RN-204).
- **RF-108** El sistema **deduplica** por clave natural antes de escribir. *(RT-09, RT-11)*
- **RF-109** El sistema escribe los datos crudos válidos en **Parquet snappy**,
  particionados por `fuente` y `fecha_ingesta`, en el área de staging.
- **RF-110** Cada lote produce un **reporte de ingesta**: filas leídas, cargadas,
  rechazadas, duplicadas, timestamp y estado.
- **RF-111** Los datos aterrizados quedan listos para que CU-O04 (GE) los valide y
  CU-O03 (ETL/DBT) los promueva a `Fact_Resena`, `Fact_Precio_Mercado` y
  `Fact_Puntuacion`.

## 5. Requisitos no funcionales

- **RNF-101 Formato:** staging exclusivamente en Parquet con compresión **snappy**
  (pyarrow). Prohibido CSV en producción. *(RT-04)*
- **RNF-102 Idempotencia:** reejecutar la ingesta de una misma ventana no duplica
  filas en staging. *(RT-11)*
- **RNF-103 Volumen:** soporta lotes de al menos 10⁶ registros por ejecución sin
  degradar el pipeline diario.
- **RNF-104 Frecuencia:** ingesta programada (diaria por defecto; configurable por
  fuente vía cron).
- **RNF-105 Observabilidad:** cada ejecución emite métricas y logs estructurados
  consumibles por `observabilidad` (OP7) y `alertas` (OP9).
- **RNF-106 Reproducibilidad:** el conector y el runner corren en contenedor dentro
  de `docker compose`, orquestados por Airflow. *(RT-17)*

## 6. Reglas de negocio

- **RN-201** Una fuente debe existir y estar **activa** en el catálogo (PocketBase)
  para poder ingerirse. Sin registro previo no hay ingesta.
- **RN-202** No se admiten fuentes duplicadas (`tipo + endpoint + formato`). *(RT-10)*
- **RN-203** Deduplicación por clave natural obligatoria antes de escribir staging:
  - `Fact_Resena`: `(fuente, catador, vino, fecha_resena)`.
  - `Fact_Precio_Mercado`: `(fuente, vino, mercado, fecha_precio)`.
  - `Fact_Puntuacion`: `(fuente, catador, vino, fecha_cata)`. *(RT-09)*
- **RN-204** Si el porcentaje de registros rechazados por esquema supera **5%** del
  lote, la ingesta se marca `FALLIDA` y emite alerta (no aterriza el lote). *(RT-16)*
- **RN-205** Dominios mínimos verificados en el aterrizaje (validación completa en GE/CU-O04):
  `precio > 0`, `puntaje` ∈ [80, 100], `fecha` no futura, `moneda` ISO-4217. *(RT-06)*
- **RN-206** La ingesta **no transforma** a Fact-Dim ni carga StarRocks: solo aterriza
  crudo en Parquet. Saltarse esto viola la separación de capas. *(RT-01, RT-03)*

## 7. Entradas

- **Catálogo de fuentes** (PocketBase): metadatos de cada fuente (CU-O01).
- **Datos de la fuente externa** (CU-O02): reseñas, precios, puntuaciones (API/feed/archivo).
- **Parámetros de ejecución:** ventana temporal/cursor, id de fuente, modo (full/incremental).

## 8. Salidas

- **Catálogo de fuentes** poblado en PocketBase (incluye estado y última ingesta).
- **Datasets Parquet snappy** en staging, particionados por `fuente` y `fecha_ingesta`,
  para reseñas, precios y puntuaciones.
- **Reporte de ingesta** por lote (filas leídas/cargadas/rechazadas/duplicadas, estado).
- **Área de rechazos** (`rejects/`) con los registros que no pasaron el esquema.
- **Eventos/metrics** para observabilidad y alertas.

## 9. Estados posibles

**Fuente (CU-O01):** `BORRADOR` → `VALIDANDO_CONEXION` → `ACTIVA` → (`PAUSADA`) → `BAJA`.
Si la validación falla: `RECHAZADA`.

**Lote de ingesta (CU-O02):** `PENDIENTE` → `LEYENDO` → `VALIDANDO_ESQUEMA` →
`DEDUPLICANDO` → `ESCRIBIENDO_PARQUET` → `COMPLETADA`. Rutas de error:
`FALLIDA` (conexión, % rechazo > umbral) y `PARCIAL` (aterrizó con rechazos < umbral).

## 10. Escenarios (Dado / Cuando / Entonces)

- **Esc-101 (alta nominal):** *Dado* un Ingeniero de datos con una fuente de precios
  nueva, *cuando* la registra con endpoint válido, *entonces* el sistema valida
  conexión y esquema, la persiste en PocketBase como `ACTIVA` y la asocia a `Dim_Mercado`.
- **Esc-102 (alta duplicada):** *Dado* que ya existe una fuente con igual
  `tipo + endpoint + formato`, *cuando* se intenta registrarla otra vez, *entonces*
  el sistema la rechaza y devuelve el id existente. *(RN-202)*
- **Esc-103 (ingesta nominal):** *Dado* una fuente de reseñas `ACTIVA`, *cuando*
  corre la ingesta diaria, *entonces* lee el incremento, valida esquema, deduplica y
  escribe Parquet snappy particionado, dejando el lote `COMPLETADA` con su reporte.
- **Esc-104 (esquema parcialmente inválido):** *Dado* un lote con 2% de registros
  malformados, *cuando* se valida el esquema, *entonces* esos registros van a
  `rejects/`, el resto aterriza y el lote queda `PARCIAL`. *(RF-107)*
- **Esc-105 (rechazo excesivo):** *Dado* un lote con 12% de registros inválidos,
  *cuando* supera el umbral del 5%, *entonces* el lote se marca `FALLIDA`, **no**
  aterriza y se emite alerta. *(RN-204, RT-16)*
- **Esc-106 (reejecución idempotente):** *Dado* un lote ya ingerido, *cuando* se
  reejecuta la misma ventana, *entonces* la deduplicación evita filas repetidas en
  staging. *(RNF-102, RN-203)*
- **Esc-107 (fuente caída):** *Dado* un endpoint sin respuesta, *cuando* la ingesta
  intenta leer, *entonces* reintenta según política de Airflow y, si agota
  reintentos, marca `FALLIDA` y emite alerta. *(RNF-105, RT-16)*

## 11. Criterios de aceptación

- **CA-101** Registrar una fuente válida la deja `ACTIVA` en PocketBase y asociada a
  su `Dim_Catador_Sumiller` y/o `Dim_Mercado`. *(RF-101, RF-103)*
- **CA-102** Un alta duplicada es rechazada con el id de la fuente existente. *(RF-104, RN-202)*
- **CA-103** La ingesta de una fuente activa produce archivos **Parquet snappy**
  particionados por `fuente`/`fecha_ingesta`, verificable con pyarrow. *(RF-109, RNF-101)*
- **CA-104** Reejecutar la misma ventana no incrementa el conteo de filas en staging
  (idempotencia verificable). *(RNF-102, Esc-106)*
- **CA-105** Un lote con > 5% de rechazos termina `FALLIDA`, no aterriza y genera
  alerta. *(RN-204, Esc-105)*
- **CA-106** Cada ejecución emite un reporte de ingesta con filas leídas, cargadas,
  rechazadas y duplicadas. *(RF-110)*
- **CA-107** La ingesta corre como tarea de un DAG de Airflow dentro de
  `docker compose up`, antes de la tarea de calidad. *(RNF-106, RT-03)*

## 12. Dependencias

- **Capas:** PocketBase (catálogo de fuentes), Parquet (staging destino).
- **Paquetes:** [`000-general`](../000-general/operativo-general-spec.md) (marco);
  `etl-calidad` (OP2) consume el staging vía CU-O04 (GE) y CU-O03 (DBT → StarRocks);
  `observabilidad` (OP7) y `alertas` (OP9) consumen métricas y eventos.
- **Tablas Fact/Dim:** alimenta el origen de `Fact_Resena`, `Fact_Precio_Mercado`,
  `Fact_Puntuacion`; usa `Dim_Catador_Sumiller` y `Dim_Mercado` como contexto.
- **Herramientas:** pyarrow (Parquet snappy), PocketBase SDK, Apache Airflow, Docker.

## 13. Fuera de alcance

- Transformación a esquema Fact-Dim y carga a StarRocks (es CU-O03 / `etl-calidad`).
- Validación de calidad profunda con Great Expectations (es CU-O04 / `etl-calidad`).
- Agregaciones en ClickHouse y dashboards (OP3).
- NLP/sentimiento de reseñas y OCR de etiquetas (técnicas opcionales de ML, OP8);
  aquí solo se ingiere el texto/dato crudo.
- Gestión de cuentas y suscripciones de clientes (OP5).
