# Implementation Plan: RETAILYTICS Dashboard

## Overview

Implementación incremental del sistema RETAILYTICS Dashboard en Python. El plan sigue el orden natural de dependencias: configuración del entorno → capa de base de datos → carga de datos CSV → aplicación Flask → frontend. Cada tarea construye sobre la anterior y termina con la integración completa de todos los componentes.

## Tasks

- [x] 1. Configurar el entorno del proyecto
  - Crear el archivo `requirements.txt` en la raíz del proyecto con las dependencias exactas: `Flask==3.0.3`, `SQLAlchemy==2.0.30`, `pandas==2.2.2`, `psycopg2-binary==2.9.9`
  - Crear la estructura de carpetas: `templates/` en la raíz del proyecto
  - Crear el archivo vacío `retailytics.log` en la raíz del proyecto
  - _Requirements: 7.4_

- [x] 2. Implementar DB_Manager (`db_manager.py`)
  - [x] 2.1 Implementar `ensure_database_exists()`
    - Conectar a la base de datos administrativa `postgres` con `isolation_level="AUTOCOMMIT"`
    - Ejecutar `CREATE DATABASE retailytics_db` si no existe
    - Capturar `OperationalError` y relanzar con mensaje descriptivo (host no alcanzable, credenciales inválidas)
    - _Requirements: 1.1, 1.2, 1.14_

  - [x] 2.2 Implementar `get_engine()`
    - Crear y retornar un `Engine` de SQLAlchemy apuntando a `retailytics_db` en `localhost`
    - Configurar pool: `pool_size=5`, `max_overflow=10`, `pool_timeout=30`
    - _Requirements: 1.1_

  - [x] 2.3 Implementar `create_tables(engine)`
    - Definir las 10 tablas usando `MetaData` + `Table` + `Column` de SQLAlchemy Core en el orden de dependencias FK: `categorias`, `marcas`, `canales`, `regiones`, `fuentes_trafico`, `usuarios`, `productos`, `sesiones`, `transacciones`, `interacciones`
    - Usar `checkfirst=True` en `metadata.create_all()` para idempotencia
    - Capturar `SQLAlchemyError`, hacer rollback y relanzar con mensaje descriptivo
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 1.11, 1.12, 1.13, 1.15_

  - [ ]* 2.4 Escribir tests unitarios para DB_Manager
    - Testear que `ensure_database_exists()` lanza excepción con mensaje descriptivo cuando la conexión falla
    - Testear que `create_tables()` crea las 10 tablas en el orden correcto usando una DB de test
    - _Requirements: 1.14, 1.15_

- [x] 3. Checkpoint — Verificar DB_Manager
  - Asegurarse de que todos los tests de DB_Manager pasan. Consultar al usuario si surgen dudas sobre credenciales de PostgreSQL o configuración del entorno.

- [x] 4. Implementar CSV_Loader (`csv_loader.py`)
  - [x] 4.1 Implementar `read_and_validate_csv(csv_path)`
    - Leer el CSV con `pandas.read_csv()` desde `csv_path`
    - Verificar que el archivo existe; lanzar `FileNotFoundError` con mensaje descriptivo si no
    - Verificar que el DataFrame contiene exactamente las 18 columnas requeridas; lanzar `ValueError` indicando las columnas faltantes
    - Verificar que el DataFrame tiene al menos una fila; lanzar `ValueError` si está vacío
    - Convertir `timestamp_utc` a `datetime64[ns, UTC]` con `pd.to_datetime(utc=True)`; lanzar `ValueError` si la conversión falla
    - Convertir `is_conversion` y `drop_off_flag` a `bool` (0→False, 1→True); lanzar `ValueError` si hay valores distintos de 0 y 1
    - Convertir `price` a `float64`; lanzar `ValueError` si hay valores no numéricos
    - Retornar el DataFrame validado
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 4.2 Escribir tests unitarios para `read_and_validate_csv`
    - Testear CSV válido retorna DataFrame con tipos correctos
    - Testear error cuando el archivo no existe
    - Testear error cuando faltan columnas requeridas
    - Testear error cuando el CSV está vacío (solo encabezado)
    - Testear error con `timestamp_utc` en formato inválido
    - Testear error con valores no booleanos en `is_conversion` o `drop_off_flag`
    - Testear error con valores no numéricos en `price`
    - _Requirements: 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [x] 4.3 Implementar `load_data(engine, df)`
    - Abrir una transacción SQLAlchemy única para toda la operación
    - Paso 2a: Insertar valores únicos de `category`, `brand`, `channel`, `region`, `traffic_source` en sus tablas de catálogo usando `INSERT ... ON CONFLICT DO NOTHING`
    - Paso 2b: Cargar lookup maps `{nombre: id}` para cada catálogo con `SELECT id, nombre`
    - Paso 2c: Insertar usuarios únicos por `user_id` con FK resuelta a `region_id` usando `INSERT ... ON CONFLICT DO NOTHING`
    - Paso 2d: Insertar productos únicos por `product_id` con FKs resueltas a `category_id` y `brand_id` usando `INSERT ... ON CONFLICT DO NOTHING`
    - Paso 2e: Insertar sesiones únicas por `session_id` con FKs resueltas usando `INSERT ... ON CONFLICT DO NOTHING`
    - Paso 2f: Insertar todos los registros en `interacciones` en chunks de 5,000 filas
    - Paso 2g: Insertar en `transacciones` solo los registros donde `is_conversion = True`
    - Hacer commit al finalizar; hacer rollback en cualquier excepción y relanzar con tabla afectada y motivo
    - Retornar `COUNT(*)` de `interacciones`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 3.9, 3.10_

  - [ ]* 4.4 Escribir tests unitarios para `load_data`
    - Testear que las 10 tablas se pueblan en el orden correcto usando una DB de test con datos mínimos
    - Testear que el rollback ocurre cuando falla la inserción en alguna tabla
    - Testear que `COUNT(*)` retornado coincide con el número de filas del DataFrame
    - _Requirements: 3.8, 3.9_

  - [x] 4.5 Implementar `reload_data(engine, csv_path)`
    - Llamar a `read_and_validate_csv(csv_path)` para obtener el DataFrame validado
    - Ejecutar `TRUNCATE ... RESTART IDENTITY CASCADE` en el orden inverso de FK: `interacciones`, `transacciones`, `sesiones`, `productos`, `usuarios`, `categorias`, `marcas`, `canales`, `regiones`, `fuentes_trafico`
    - Llamar a `load_data(engine, df)` y retornar el conteo
    - _Requirements: 3.7_

  - [ ]* 4.6 Escribir tests unitarios para `reload_data`
    - Testear que después de una recarga la tabla `interacciones` contiene exactamente los registros del CSV
    - Testear que los SERIAL se reinician tras el TRUNCATE RESTART IDENTITY
    - _Requirements: 3.7_

- [x] 5. Checkpoint — Verificar CSV_Loader
  - Asegurarse de que todos los tests de CSV_Loader pasan. Consultar al usuario si surgen dudas sobre el rendimiento de la carga o el manejo de errores.

- [x] 6. Implementar Flask App (`app.py`)
  - [x] 6.1 Configurar la aplicación Flask y el sistema de logging
    - Crear `app.py` con la instancia Flask
    - Configurar `logging.basicConfig` con `filename='retailytics.log'`, `level=logging.WARNING` y formato `%(asctime)s [%(levelname)s] %(message)s`
    - Definir `CSV_PATH` apuntando a `retail_user_behavior_100k.csv` en la raíz del proyecto
    - Inicializar el engine llamando a `ensure_database_exists()` y `get_engine()` al arrancar la app; capturar errores de conexión y registrarlos como CRITICAL
    - Llamar a `create_tables(engine)` al arrancar
    - _Requirements: 7.4_

  - [x] 6.2 Implementar la ruta `GET /`
    - Consultar `SELECT COUNT(*) FROM interacciones` para obtener el total de registros
    - Consultar `SELECT ... FROM interacciones ORDER BY id LIMIT 100` para obtener la primera página
    - Renderizar `templates/index.html` pasando `total` y `rows` como contexto
    - Retornar HTTP 200 en menos de 2 segundos
    - Capturar `OperationalError` de SQLAlchemy y retornar JSON `{status: "error", message: "Base de datos no disponible"}` con HTTP 503
    - Capturar cualquier otra excepción, registrarla como ERROR y retornar JSON con HTTP 500
    - _Requirements: 4.1, 4.3, 4.4, 7.2, 7.3_

  - [x] 6.3 Implementar la ruta `POST /load-data`
    - Llamar a `reload_data(engine, CSV_PATH)`
    - Retornar JSON `{"status": "success", "message": "Dataset cargado exitosamente. {N} registros insertados.", "count": N}` con HTTP 200
    - Capturar `OperationalError` y retornar JSON con `status: "error"`, `message: "Base de datos no disponible"`, `count: 0` y HTTP 503
    - Capturar cualquier otra excepción, registrarla como ERROR y retornar JSON con `status: "error"`, mensaje descriptivo, `count: 0` y HTTP 500
    - _Requirements: 5.7, 7.2, 7.3_

  - [x] 6.4 Implementar la ruta `GET /interactions`
    - Leer parámetros `page` y `per_page` de la query string
    - Sanitizar: `page < 1` o no entero → usar `page = 1`; `per_page > 500` → limitar a 500; `per_page <= 0` o no entero → usar `per_page = 100`; registrar WARNING si se aplica sanitización
    - Calcular `offset = (page - 1) * per_page`
    - Consultar `SELECT ... FROM interacciones ORDER BY id LIMIT per_page OFFSET offset`
    - Consultar `SELECT COUNT(*) FROM interacciones` para `total`
    - Calcular `total_pages = ceil(total / per_page)`
    - Retornar JSON con `data`, `total`, `page`, `per_page`, `total_pages` y HTTP 200
    - Capturar `OperationalError` y retornar HTTP 503; capturar otras excepciones y retornar HTTP 500
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3_

  - [ ]* 6.5 Escribir tests unitarios para las rutas Flask
    - Testear `GET /` retorna HTTP 200 con datos de contexto correctos
    - Testear `POST /load-data` retorna JSON con `status: "success"` y `count` correcto
    - Testear `GET /interactions` con parámetros válidos retorna estructura JSON correcta
    - Testear sanitización de `page` y `per_page` (valores inválidos, fuera de rango)
    - Testear respuestas de error HTTP 503 cuando la DB no está disponible
    - _Requirements: 4.1, 5.7, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3_

- [x] 7. Checkpoint — Verificar Flask App
  - Asegurarse de que todos los tests de las rutas Flask pasan. Consultar al usuario si surgen dudas sobre el manejo de errores o los contratos de la API.

- [x] 8. Implementar el Frontend (`templates/index.html`)
  - [x] 8.1 Crear la estructura HTML base y el header sticky
    - Crear `templates/index.html` con estructura HTML5 válida y accesible
    - Implementar header sticky con el título "RETAILYTICS Dashboard"
    - Agregar el botón "Cargar / Recargar Dataset" siempre visible (above the fold)
    - Agregar el spinner de carga (oculto por defecto con `display: none`)
    - Agregar el área de mensajes inline para éxito y error (ocultos por defecto)
    - Mostrar el contador "Total de registros: {{ total }}" renderizado desde Flask
    - _Requirements: 4.2, 4.3, 5.2_

  - [x] 8.2 Implementar la tabla paginada con datos iniciales
    - Crear la tabla HTML con las columnas en orden: `session_id`, `user_id`, `timestamp_utc`, `event_index`, `user_action`, `product_id`, `time_spent_sec`, `is_conversion`, `drop_off_flag`
    - Renderizar las filas iniciales desde el contexto Flask (`{{ rows }}`)
    - Mostrar el mensaje "No hay datos cargados. Usa el botón para cargar el dataset." cuando `rows` está vacío, manteniendo los encabezados visibles
    - Agregar los controles de paginación "← Anterior" y "→ Siguiente" con el indicador "Página X de Y"
    - Deshabilitar "Anterior" en página 1 y "Siguiente" en la última página; deshabilitar ambos cuando la tabla está vacía
    - _Requirements: 4.4, 4.5, 4.6, 6.5_

  - [x] 8.3 Implementar el flujo AJAX para carga de datos
    - Agregar el event listener al botón "Cargar / Recargar Dataset"
    - Al hacer clic: deshabilitar el botón, mostrar spinner, ocultar mensajes previos
    - Enviar `fetch('POST /load-data')` y esperar la respuesta JSON
    - Si `status == "success"`: mostrar mensaje de éxito con `count`, llamar a `fetchInteractions(1)` para actualizar tabla y contador, ocultar spinner, habilitar botón
    - Si `status == "error"` o fallo de red: mostrar mensaje de error con `message`, ocultar spinner, habilitar botón
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 8.4 Implementar el flujo AJAX para paginación
    - Implementar la función `fetchInteractions(page)` que hace `fetch('GET /interactions?page={page}&per_page=100')`
    - Al recibir la respuesta: actualizar las filas de la tabla con `data[]`, actualizar el indicador "Página X de Y", actualizar el contador de registros con `total`
    - Deshabilitar "Anterior" si `page == 1`; deshabilitar "Siguiente" si `page == total_pages`
    - Agregar event listeners a los botones "Anterior" y "Siguiente" para llamar a `fetchInteractions(currentPage ± 1)`
    - _Requirements: 6.5, 6.6, 5.4_

- [x] 9. Checkpoint final — Integración completa
  - Asegurarse de que todos los tests pasan. Verificar que el flujo completo funciona: arranque de la app → carga del CSV → visualización paginada → recarga. Consultar al usuario si surgen dudas.

## Notes

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido
- Cada tarea referencia los requisitos específicos para trazabilidad completa
- Los checkpoints garantizan validación incremental antes de avanzar al siguiente componente
- El orden de implementación respeta las dependencias: DB_Manager → CSV_Loader → Flask App → Frontend
- La transaccionalidad completa en `load_data` garantiza consistencia ante fallos parciales

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3"] },
    { "id": 3, "tasks": ["2.4", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3"] },
    { "id": 5, "tasks": ["4.4", "4.5"] },
    { "id": 6, "tasks": ["4.6", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 8, "tasks": ["6.5", "8.1"] },
    { "id": 9, "tasks": ["8.2"] },
    { "id": 10, "tasks": ["8.3"] },
    { "id": 11, "tasks": ["8.4"] }
  ]
}
```
