# Design Document: RETAILYTICS Dashboard

## Overview

RETAILYTICS Dashboard es un sistema web que ingesta 100,000 registros de comportamiento de usuarios desde un CSV, los normaliza en 10 tablas PostgreSQL y los expone mediante una interfaz Flask con paginación, recarga asíncrona y feedback visual en tiempo real. El stack es Python + Flask + SQLAlchemy + pandas + PostgreSQL.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (Cliente)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  index.html  (Vanilla JS + fetch API)                    │   │
│  │  - Botón "Cargar / Recargar Dataset"                     │   │
│  │  - Spinner + mensajes inline                             │   │
│  │  - Tabla paginada (Anterior / Siguiente)                 │   │
│  │  - Contador "Total de registros: N"                      │   │
│  └──────────────┬───────────────────────────────────────────┘   │
└─────────────────┼───────────────────────────────────────────────┘
                  │  HTTP (GET / POST / GET)
┌─────────────────▼───────────────────────────────────────────────┐
│                     Flask Application (app.py)                  │
│                                                                 │
│  GET  /                  → render index.html                    │
│  POST /load-data         → reload_data() → JSON response        │
│  GET  /interactions      → paginated query → JSON response      │
│                                                                 │
│  Error handlers: 400 / 500 / 503  →  JSON + logging            │
└──────────┬──────────────────────────┬───────────────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐      ┌───────────────────────────────────────┐
│   csv_loader.py  │      │           db_manager.py               │
│                  │      │                                       │
│ read_and_validate│      │ ensure_database_exists()              │
│ _csv(csv_path)   │      │   └─ conecta a 'postgres' DB          │
│                  │      │   └─ crea 'retailytics_db' si falta   │
│ load_data(       │      │                                       │
│   engine, df)    │      │ get_engine()                          │
│                  │      │   └─ SQLAlchemy engine para           │
│ reload_data(     │      │      retailytics_db                   │
│   engine,        │      │                                       │
│   csv_path)      │      │ create_tables(engine)                 │
│                  │      │   └─ 10 tablas en orden de FK         │
└──────────┬───────┘      └───────────────────────────────────────┘
           │                          │
           └──────────┬───────────────┘
                      │  SQLAlchemy Core
┌─────────────────────▼───────────────────────────────────────────┐
│                  PostgreSQL — retailytics_db                     │
│                                                                 │
│  Catálogos:  categorias  marcas  canales  regiones              │
│              fuentes_trafico                                    │
│  Entidades:  usuarios  productos  sesiones                      │
│  Hechos:     interacciones  transacciones                       │
└─────────────────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│  retail_user_behavior_100k.csv  (raíz del proyecto)             │
│  100,000 filas × 18 columnas                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Orden de creación (respeta dependencias FK)

```
1. categorias
2. marcas
3. canales
4. regiones
5. fuentes_trafico
6. usuarios          → FK: regiones
7. productos         → FK: categorias, marcas
8. sesiones          → FK: usuarios, canales, fuentes_trafico
9. transacciones     → FK: sesiones, usuarios, productos
10. interacciones    → FK: sesiones, usuarios, productos
```

### Definición de tablas

```sql
-- 1. Catálogos (sin FK)
CREATE TABLE categorias (
    category_id  SERIAL          PRIMARY KEY,
    nombre       VARCHAR(255)    NOT NULL UNIQUE
);

CREATE TABLE marcas (
    brand_id     SERIAL          PRIMARY KEY,
    nombre       VARCHAR(255)    NOT NULL UNIQUE
);

CREATE TABLE canales (
    channel_id   SERIAL          PRIMARY KEY,
    nombre       VARCHAR(100)    NOT NULL UNIQUE
);

CREATE TABLE regiones (
    region_id    SERIAL          PRIMARY KEY,
    nombre       VARCHAR(100)    NOT NULL UNIQUE
);

CREATE TABLE fuentes_trafico (
    source_id    SERIAL          PRIMARY KEY,
    nombre       VARCHAR(100)    NOT NULL UNIQUE
);

-- 2. Entidades (con FK a catálogos)
CREATE TABLE usuarios (
    user_id      VARCHAR(50)     PRIMARY KEY,
    region_id    INTEGER         NOT NULL REFERENCES regiones(region_id),
    device_type  VARCHAR(50)     NOT NULL
);

CREATE TABLE productos (
    product_id   VARCHAR(50)     PRIMARY KEY,
    category_id  INTEGER         NOT NULL REFERENCES categorias(category_id),
    brand_id     INTEGER         NOT NULL REFERENCES marcas(brand_id),
    price        NUMERIC(12,2)   NOT NULL
);

CREATE TABLE sesiones (
    session_id      VARCHAR(50)  PRIMARY KEY,
    user_id         VARCHAR(50)  NOT NULL REFERENCES usuarios(user_id),
    channel_id      INTEGER      NOT NULL REFERENCES canales(channel_id),
    source_id       INTEGER      NOT NULL REFERENCES fuentes_trafico(source_id),
    session_length  INTEGER      NOT NULL
);

-- 3. Tablas de hechos
CREATE TABLE transacciones (
    id             SERIAL        PRIMARY KEY,
    session_id     VARCHAR(50)   NOT NULL REFERENCES sesiones(session_id),
    user_id        VARCHAR(50)   NOT NULL REFERENCES usuarios(user_id),
    product_id     VARCHAR(50)   NOT NULL REFERENCES productos(product_id),
    is_conversion  BOOLEAN       NOT NULL
);

CREATE TABLE interacciones (
    id                SERIAL        PRIMARY KEY,
    session_id        VARCHAR(50)   NOT NULL REFERENCES sesiones(session_id),
    user_id           VARCHAR(50)   NOT NULL REFERENCES usuarios(user_id),
    timestamp_utc     TIMESTAMPTZ   NOT NULL,
    event_index       INTEGER       NOT NULL,
    user_action       VARCHAR(50)   NOT NULL,
    product_id        VARCHAR(50)   NOT NULL REFERENCES productos(product_id),
    time_spent_sec    INTEGER,
    interaction_count INTEGER,
    is_conversion     BOOLEAN       NOT NULL DEFAULT FALSE,
    drop_off_flag     BOOLEAN       NOT NULL DEFAULT FALSE
);
```

---

## Data Flow: CSV → PostgreSQL

```
retail_user_behavior_100k.csv
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 1 — read_and_validate_csv(csv_path)                       │
│                                                                 │
│  pandas.read_csv()                                              │
│    ├─ Verificar 18 columnas requeridas                          │
│    ├─ timestamp_utc → pd.to_datetime(utc=True)                  │
│    ├─ is_conversion, drop_off_flag → bool (0→False, 1→True)     │
│    ├─ price → float / NUMERIC(12,2)                             │
│    └─ Verificar que df.shape[0] > 0                             │
│                                                                 │
│  Retorna: DataFrame validado  |  Lanza: ValueError con detalle  │
└─────────────────────┬───────────────────────────────────────────┘
                      │  df (100,000 filas)
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  PASO 2 — load_data(engine, df)                                 │
│                                                                 │
│  Dentro de una transacción SQLAlchemy:                          │
│                                                                 │
│  2a. Catálogos (INSERT … ON CONFLICT DO NOTHING)                │
│      df['category'].unique()     → categorias                   │
│      df['brand'].unique()        → marcas                       │
│      df['channel'].unique()      → canales                      │
│      df['region'].unique()       → regiones                     │
│      df['traffic_source'].unique()→ fuentes_trafico             │
│                                                                 │
│  2b. Lookup maps: SELECT id, nombre FROM cada catálogo          │
│      → dicts {nombre: id} para resolver FKs                     │
│                                                                 │
│  2c. Usuarios únicos por user_id                                │
│      (INSERT … ON CONFLICT DO NOTHING)                          │
│                                                                 │
│  2d. Productos únicos por product_id                            │
│      (INSERT … ON CONFLICT DO NOTHING)                          │
│                                                                 │
│  2e. Sesiones únicas por session_id                             │
│      (INSERT … ON CONFLICT DO NOTHING)                          │
│                                                                 │
│  2f. Interacciones — todos los registros                        │
│      chunks de 5,000 filas → INSERT bulk                        │
│      (20 batches × 5,000 = 100,000 filas)                       │
│                                                                 │
│  2g. Transacciones — solo filas donde is_conversion = True      │
│      (INSERT … ON CONFLICT DO NOTHING)                          │
│                                                                 │
│  Commit  |  Rollback en cualquier excepción                     │
│  Retorna: int (total filas en interacciones)                    │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo de recarga (reload_data)

```
reload_data(engine, csv_path)
    │
    ├─ 1. read_and_validate_csv(csv_path)   → df
    │
    ├─ 2. TRUNCATE en cascada (orden inverso de FK):
    │      interacciones, transacciones, sesiones,
    │      productos, usuarios,
    │      categorias, marcas, canales, regiones, fuentes_trafico
    │      (RESTART IDENTITY CASCADE)
    │
    └─ 3. load_data(engine, df)             → count
```

---

## Components and Interfaces

### DB_Manager (`db_manager.py`)

```python
def ensure_database_exists() -> None:
    """
    Conecta a la DB 'postgres' (superusuario).
    Crea 'retailytics_db' si no existe.
    Lanza: sqlalchemy.exc.OperationalError si la conexión falla.
    """

def get_engine() -> sqlalchemy.engine.Engine:
    """
    Retorna un Engine configurado para retailytics_db.
    Pool: pool_size=5, max_overflow=10, pool_timeout=30.
    """

def create_tables(engine: sqlalchemy.engine.Engine) -> None:
    """
    Crea las 10 tablas usando SQLAlchemy Core (MetaData + Table).
    Usa checkfirst=True para idempotencia.
    Lanza: sqlalchemy.exc.SQLAlchemyError si la creación falla;
           hace rollback de la sesión antes de relanzar.
    """
```

### CSV_Loader (`csv_loader.py`)

```python
def read_and_validate_csv(csv_path: str) -> pd.DataFrame:
    """
    Lee el CSV con pandas y valida estructura y tipos.
    
    Precondiciones:
    - csv_path apunta a un archivo existente y legible
    
    Postcondiciones:
    - df.columns contiene exactamente las 18 columnas requeridas
    - df['timestamp_utc'].dtype == datetime64[ns, UTC]
    - df['is_conversion'].dtype == bool
    - df['drop_off_flag'].dtype == bool
    - df['price'].dtype == float64
    - len(df) > 0
    
    Lanza: FileNotFoundError, ValueError con mensaje descriptivo
    """

def load_data(engine: Engine, df: pd.DataFrame) -> int:
    """
    Carga el DataFrame normalizado en las 10 tablas.
    
    Precondiciones:
    - engine conectado y tablas creadas
    - df validado por read_and_validate_csv
    
    Postcondiciones:
    - Todas las tablas pobladas en orden de FK
    - Retorna COUNT(*) de interacciones == len(df)
    
    Lanza: sqlalchemy.exc.SQLAlchemyError → rollback automático
    """

def reload_data(engine: Engine, csv_path: str) -> int:
    """
    Trunca todas las tablas y ejecuta load_data.
    Retorna: número de registros insertados en interacciones.
    """
```

### Flask App (`app.py`)

```python
@app.route('/', methods=['GET'])
def index() -> str:
    """
    Renderiza index.html.
    Consulta: SELECT COUNT(*) FROM interacciones
    Consulta: SELECT ... FROM interacciones ORDER BY id LIMIT 100
    Retorna: HTML 200 en < 2 segundos
    """

@app.route('/load-data', methods=['POST'])
def load_data_route() -> Response:
    """
    Dispara reload_data(engine, CSV_PATH).
    Retorna JSON: {"status": "success"|"error", "message": str, "count": int}
    HTTP 200 en éxito, HTTP 500 en error interno, HTTP 503 si DB no disponible
    """

@app.route('/interactions', methods=['GET'])
def interactions() -> Response:
    """
    Parámetros: page (int, default=1), per_page (int, default=100, max=500)
    Retorna JSON:
    {
      "data": [...],
      "total": int,
      "page": int,
      "per_page": int,
      "total_pages": int
    }
    HTTP 200 en éxito, HTTP 400 si parámetros inválidos (no recuperables)
    """
```

---

## API Contracts

### GET /

| Campo       | Valor                                      |
|-------------|--------------------------------------------|
| Método      | GET                                        |
| Ruta        | `/`                                        |
| Respuesta   | HTML 200                                   |
| Tiempo máx. | 2 segundos                                 |
| Errores     | 500 JSON si excepción no controlada        |
|             | 503 JSON si DB no disponible               |

---

### POST /load-data

| Campo       | Valor                                      |
|-------------|--------------------------------------------|
| Método      | POST                                       |
| Ruta        | `/load-data`                               |
| Body        | (vacío)                                    |
| Content-Type respuesta | `application/json`              |

**Respuesta exitosa (HTTP 200):**
```json
{
  "status": "success",
  "message": "Dataset cargado exitosamente. 100000 registros insertados.",
  "count": 100000
}
```

**Respuesta de error (HTTP 500):**
```json
{
  "status": "error",
  "message": "Error al cargar el dataset: <detalle del error>",
  "count": 0
}
```

**Respuesta DB no disponible (HTTP 503):**
```json
{
  "status": "error",
  "message": "Base de datos no disponible",
  "count": 0
}
```

---

### GET /interactions

| Campo       | Valor                                      |
|-------------|--------------------------------------------|
| Método      | GET                                        |
| Ruta        | `/interactions`                            |
| Parámetros  | `page` (int, default=1, min=1)             |
|             | `per_page` (int, default=100, max=500)     |

**Reglas de sanitización de parámetros:**

| Condición                          | Comportamiento              |
|------------------------------------|-----------------------------|
| `page < 1` o no es entero          | Usar `page = 1`             |
| `per_page > 500`                   | Limitar a `per_page = 500`  |
| `per_page <= 0` o no es entero     | Usar `per_page = 100`       |

**Respuesta exitosa (HTTP 200):**
```json
{
  "data": [
    {
      "id": 1,
      "session_id": "S00001",
      "user_id": "U00001",
      "timestamp_utc": "2024-01-15T10:23:45+00:00",
      "event_index": 1,
      "user_action": "view",
      "product_id": "P00001",
      "time_spent_sec": 45,
      "interaction_count": 3,
      "is_conversion": false,
      "drop_off_flag": false
    }
  ],
  "total": 100000,
  "page": 1,
  "per_page": 100,
  "total_pages": 1000
}
```

**Respuesta de error de parámetro (HTTP 400):**
```json
{
  "status": "error",
  "message": "Parámetro inválido: page debe ser un entero positivo"
}
```

---

## Frontend Design (`templates/index.html`)

### Estructura de la página

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER (sticky, siempre visible)                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  RETAILYTICS Dashboard                                  │   │
│  │  [Cargar / Recargar Dataset]  ← botón siempre visible   │   │
│  │  ⟳ Cargando...  (spinner, oculto por defecto)           │   │
│  │  ✓ Dataset cargado exitosamente. 100000 registros.      │   │
│  │    (mensaje inline, oculto por defecto)                 │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Total de registros: 100000                                     │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ session_id │ user_id │ timestamp_utc │ event_index │ …  │   │
│  ├────────────┼─────────┼───────────────┼─────────────┼───┤   │
│  │ S00001     │ U00001  │ 2024-01-15 …  │ 1           │ … │   │
│  │ …          │ …       │ …             │ …           │ … │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [← Anterior]   Página 1 de 1000   [Siguiente →]               │
└─────────────────────────────────────────────────────────────────┘
```

### Flujo AJAX — Carga de datos

```
Usuario click "Cargar / Recargar Dataset"
    │
    ├─ Deshabilitar botón
    ├─ Mostrar spinner
    ├─ Ocultar mensajes previos
    │
    ▼
fetch('POST /load-data')
    │
    ├─ [success] status == "success"
    │       ├─ Mostrar mensaje éxito con count
    │       ├─ fetch('GET /interactions?page=1&per_page=100')
    │       │       └─ Actualizar tabla + contador
    │       └─ Ocultar spinner, habilitar botón
    │
    └─ [error] status == "error" o fallo de red
            ├─ Mostrar mensaje de error con message
            └─ Ocultar spinner, habilitar botón
```

### Flujo AJAX — Paginación

```
Usuario click "Anterior" o "Siguiente"
    │
    ├─ Calcular nueva página (currentPage ± 1)
    │
    ▼
fetch('GET /interactions?page={n}&per_page=100')
    │
    ├─ Actualizar filas de la tabla con data[]
    ├─ Actualizar indicador "Página X de Y"
    ├─ Deshabilitar "Anterior" si page == 1
    └─ Deshabilitar "Siguiente" si page == total_pages
```

---

## Error Handling

### Escenarios y respuestas

| Escenario                              | Código HTTP | Respuesta JSON                                      | Log nivel  |
|----------------------------------------|-------------|-----------------------------------------------------|------------|
| Parámetro inválido (ej. `page=abc`)    | 400         | `{status: "error", message: "Parámetro inválido…"}` | WARNING    |
| Excepción no controlada en ruta        | 500         | `{status: "error", message: "Error interno…"}`      | ERROR      |
| DB no disponible                       | 503         | `{status: "error", message: "Base de datos no disponible"}` | CRITICAL |
| CSV no encontrado                      | 500         | `{status: "error", message: "Archivo no encontrado: …"}` | ERROR  |
| CSV con columnas faltantes             | 500         | `{status: "error", message: "Columnas faltantes: …"}` | ERROR    |
| Error de inserción en DB               | 500         | `{status: "error", message: "Error en tabla X: …"}` | ERROR      |

### Formato de log (`retailytics.log`)

```
2024-01-15 10:23:45,123 [ERROR] Error al cargar dataset: columnas faltantes: ['price']
2024-01-15 10:24:01,456 [CRITICAL] Base de datos no disponible: connection refused on localhost:5432
2024-01-15 10:25:10,789 [WARNING] Parámetro inválido: page=abc, usando page=1
```

Configuración del logger:
```python
logging.basicConfig(
    filename='retailytics.log',
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
```

---

## Key Design Decisions

### 1. SQLAlchemy Core en lugar de ORM

Se usa SQLAlchemy Core (MetaData + Table + Column) para la creación de tablas y las operaciones de inserción masiva. El ORM añade overhead innecesario para operaciones bulk. Las inserciones en `interacciones` usan `engine.execute(table.insert(), list_of_dicts)` que es significativamente más rápido que insertar objeto por objeto.

### 2. Chunks de 5,000 para interacciones

100,000 filas en un solo INSERT puede causar timeouts o consumo excesivo de memoria. Chunks de 5,000 equilibran rendimiento y uso de memoria, completando la carga en ~20 batches dentro del límite de 120 segundos.

### 3. INSERT ON CONFLICT DO NOTHING para catálogos

Las tablas de catálogo (`categorias`, `marcas`, etc.) tienen restricción UNIQUE en `nombre`. Usar ON CONFLICT DO NOTHING permite que la operación de recarga sea idempotente sin necesidad de verificar existencia previa, simplificando el código y mejorando el rendimiento.

### 4. TRUNCATE RESTART IDENTITY CASCADE

En lugar de DELETE, se usa TRUNCATE para vaciar las tablas en la recarga. TRUNCATE es más rápido (no genera WAL por fila), RESTART IDENTITY reinicia los SERIAL, y CASCADE maneja automáticamente el orden de las FK sin necesidad de deshabilitar constraints.

### 5. Lookup maps en memoria para resolución de FKs

Después de insertar los catálogos, se cargan en memoria dicts `{nombre: id}` para cada catálogo. Esto evita N subconsultas al insertar usuarios, productos y sesiones, reduciendo el tiempo de carga significativamente.

### 6. Paginación server-side con LIMIT/OFFSET

La tabla `interacciones` tiene 100,000 registros. Cargar todos en el navegador no es viable. La paginación server-side con LIMIT/OFFSET en PostgreSQL es eficiente para las primeras páginas (uso típico). El endpoint `/interactions` está diseñado para ser consumido tanto por el frontend como por clientes externos.

### 7. Transaccionalidad completa en load_data

Toda la carga (catálogos + entidades + hechos) ocurre dentro de una única transacción SQLAlchemy. Si cualquier paso falla, el rollback garantiza que la base de datos no quede en estado inconsistente (ej. sesiones sin usuarios).

### 8. ensure_database_exists() con conexión a 'postgres'

PostgreSQL no permite crear una base de datos dentro de una transacción ni conectarse a una DB que no existe. La función se conecta primero a la DB administrativa `postgres` con `isolation_level="AUTOCOMMIT"` para ejecutar `CREATE DATABASE retailytics_db IF NOT EXISTS`.

---

## Dependencies

```
# requirements.txt
Flask==3.0.3
SQLAlchemy==2.0.30
pandas==2.2.2
psycopg2-binary==2.9.9
```

| Dependencia       | Propósito                                          |
|-------------------|----------------------------------------------------|
| Flask             | Framework web, routing, templates, JSON responses  |
| SQLAlchemy        | Abstracción de DB, creación de esquema, bulk insert|
| pandas            | Lectura CSV, validación de tipos, transformaciones |
| psycopg2-binary   | Driver PostgreSQL para SQLAlchemy                  |

**Requisito de entorno:**
- PostgreSQL 14+ corriendo en `localhost:5432`
- Usuario `postgres` con permisos para crear bases de datos
- Python 3.10+
