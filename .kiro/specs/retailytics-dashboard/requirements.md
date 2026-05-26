# Requirements Document

## Introduction

RETAILYTICS Dashboard es un sistema web para la empresa RETAILYTICS S.A. que permite ingestar, almacenar y visualizar datos de comportamiento de usuarios en una tienda online. El sistema lee un archivo CSV con 100,000 registros (`retail_user_behavior_100k.csv`), los carga en una base de datos PostgreSQL normalizada en 10 tablas, y expone una interfaz web construida con Flask que permite recargar el dataset y explorar los datos de interacciones con paginación y feedback visual en tiempo real.

Stack tecnológico: Python, Flask, PostgreSQL, pandas, SQLAlchemy.

---

## Glossary

- **CSV_Loader**: Componente Python/pandas responsable de leer el archivo CSV y cargar los datos en la base de datos.
- **DB_Manager**: Componente SQLAlchemy responsable de gestionar la conexión a PostgreSQL y la creación del esquema de tablas.
- **Dashboard**: Interfaz web Flask que expone las funcionalidades de carga y visualización de datos.
- **Interacciones**: Tabla principal de la base de datos que almacena todos los registros del CSV.
- **Dataset**: El archivo `retail_user_behavior_100k.csv` ubicado en la raíz del proyecto.
- **Registro**: Una fila del CSV o de la tabla `interacciones`, representando un evento de comportamiento de usuario.
- **Recarga**: Operación de truncar la tabla `interacciones` y volver a cargar todos los datos del CSV.
- **Paginación**: Mecanismo de división de resultados en páginas de tamaño fijo para su visualización.
- **Feedback Visual**: Indicadores en la interfaz web que comunican el estado de una operación (cargando, éxito, error).
- **Esquema Normalizado**: Conjunto de 10 tablas relacionadas que representan las entidades del dominio retail.

---

## Requirements

### Requirement 1: Inicialización de la Base de Datos

**User Story:** Como administrador del sistema, quiero que la base de datos y todas las tablas se creen automáticamente si no existen, para que el sistema sea autónomo en su configuración inicial.

#### Acceptance Criteria

1. WHEN el sistema inicia, THE DB_Manager SHALL conectarse a PostgreSQL en `localhost` con la base de datos `retailytics_db` y usuario `postgres`.
2. WHEN la base de datos `retailytics_db` no existe, THE DB_Manager SHALL crearla antes de intentar crear las tablas.
3. WHEN la conexión a PostgreSQL es exitosa, THE DB_Manager SHALL crear las siguientes tablas si no existen, en este orden de dependencias: `categorias`, `marcas`, `canales`, `regiones`, `fuentes_trafico`, `usuarios`, `productos`, `sesiones`, `transacciones`, `interacciones`.
4. THE DB_Manager SHALL crear la tabla `categorias` con columnas: `category_id` (PK, SERIAL), `nombre` (VARCHAR(255), UNIQUE, NOT NULL).
5. THE DB_Manager SHALL crear la tabla `marcas` con columnas: `brand_id` (PK, SERIAL), `nombre` (VARCHAR(255), UNIQUE, NOT NULL).
6. THE DB_Manager SHALL crear la tabla `canales` con columnas: `channel_id` (PK, SERIAL), `nombre` (VARCHAR(100), UNIQUE, NOT NULL).
7. THE DB_Manager SHALL crear la tabla `regiones` con columnas: `region_id` (PK, SERIAL), `nombre` (VARCHAR(100), UNIQUE, NOT NULL).
8. THE DB_Manager SHALL crear la tabla `fuentes_trafico` con columnas: `source_id` (PK, SERIAL), `nombre` (VARCHAR(100), UNIQUE, NOT NULL).
9. THE DB_Manager SHALL crear la tabla `usuarios` con columnas: `user_id` (PK, VARCHAR(50)), `region_id` (INTEGER, FK → `regiones.region_id`, NOT NULL), `device_type` (VARCHAR(50), NOT NULL).
10. THE DB_Manager SHALL crear la tabla `productos` con columnas: `product_id` (PK, VARCHAR(50)), `category_id` (INTEGER, FK → `categorias.category_id`, NOT NULL), `brand_id` (INTEGER, FK → `marcas.brand_id`, NOT NULL), `price` (NUMERIC(12,2), NOT NULL).
11. THE DB_Manager SHALL crear la tabla `sesiones` con columnas: `session_id` (PK, VARCHAR(50)), `user_id` (VARCHAR(50), FK → `usuarios.user_id`, NOT NULL), `channel_id` (INTEGER, FK → `canales.channel_id`, NOT NULL), `source_id` (INTEGER, FK → `fuentes_trafico.source_id`, NOT NULL), `session_length` (INTEGER, NOT NULL).
12. THE DB_Manager SHALL crear la tabla `interacciones` con columnas: `id` (PK, SERIAL), `session_id` (VARCHAR(50), FK → `sesiones.session_id`, NOT NULL), `user_id` (VARCHAR(50), FK → `usuarios.user_id`, NOT NULL), `timestamp_utc` (TIMESTAMPTZ, NOT NULL), `event_index` (INTEGER, NOT NULL), `user_action` (VARCHAR(50), NOT NULL), `product_id` (VARCHAR(50), FK → `productos.product_id`, NOT NULL), `time_spent_sec` (INTEGER), `interaction_count` (INTEGER), `is_conversion` (BOOLEAN, NOT NULL, DEFAULT FALSE), `drop_off_flag` (BOOLEAN, NOT NULL, DEFAULT FALSE).
13. THE DB_Manager SHALL crear la tabla `transacciones` con columnas: `id` (PK, SERIAL), `session_id` (VARCHAR(50), FK → `sesiones.session_id`, NOT NULL), `user_id` (VARCHAR(50), FK → `usuarios.user_id`, NOT NULL), `product_id` (VARCHAR(50), FK → `productos.product_id`, NOT NULL), `is_conversion` (BOOLEAN, NOT NULL).
14. IF la conexión a PostgreSQL falla, THEN THE DB_Manager SHALL lanzar una excepción que incluya el motivo del fallo de conexión (host no alcanzable, credenciales inválidas, base de datos no encontrada) y detenga el inicio del sistema.
15. IF la creación de alguna tabla falla, THEN THE DB_Manager SHALL revertir cualquier tabla parcialmente creada en esa sesión y lanzar una excepción descriptiva.

---

### Requirement 2: Lectura y Validación del CSV

**User Story:** Como sistema, quiero leer y validar el archivo CSV antes de cargarlo, para garantizar la integridad de los datos que ingresan a la base de datos.

#### Acceptance Criteria

1. WHEN se inicia una operación de carga, THE CSV_Loader SHALL leer el archivo `retail_user_behavior_100k.csv` desde la raíz del proyecto usando pandas.
2. THE CSV_Loader SHALL verificar que el archivo CSV contiene exactamente las siguientes columnas: `session_id`, `user_id`, `timestamp_utc`, `event_index`, `user_action`, `product_id`, `category`, `brand`, `price`, `channel`, `device_type`, `region`, `traffic_source`, `time_spent_sec`, `session_length`, `interaction_count`, `is_conversion`, `drop_off_flag`.
3. IF el archivo CSV no existe en la ruta esperada, THEN THE CSV_Loader SHALL retornar un error indicando que el archivo no fue encontrado en la ruta especificada.
4. IF el archivo CSV no contiene alguna de las columnas requeridas, THEN THE CSV_Loader SHALL retornar un error indicando cuáles columnas están faltantes.
5. WHEN el CSV es leído exitosamente, THE CSV_Loader SHALL convertir la columna `timestamp_utc` al tipo `datetime` con zona horaria UTC; IF la conversión falla para algún valor, THEN THE CSV_Loader SHALL retornar un error indicando el problema de formato.
6. WHEN el CSV es leído exitosamente, THE CSV_Loader SHALL convertir las columnas `is_conversion` y `drop_off_flag` al tipo booleano (0→False, 1→True); IF algún valor no es 0 ni 1, THEN THE CSV_Loader SHALL retornar un error indicando los valores inválidos encontrados.
7. WHEN el CSV es leído exitosamente, THE CSV_Loader SHALL convertir la columna `price` al tipo numérico de punto flotante (NUMERIC(12,2)); IF algún valor no es convertible a número, THEN THE CSV_Loader SHALL retornar un error indicando los valores inválidos.
8. IF el archivo CSV existe pero no contiene filas de datos (solo encabezado o está vacío), THEN THE CSV_Loader SHALL retornar un error indicando que el archivo no contiene registros para cargar.

---

### Requirement 3: Carga de Datos en la Base de Datos

**User Story:** Como administrador, quiero cargar todos los datos del CSV en la base de datos de forma normalizada, para poder consultarlos eficientemente desde la aplicación web.

#### Acceptance Criteria

1. WHEN se ejecuta una carga de datos, THE CSV_Loader SHALL poblar primero las tablas de catálogo (`categorias`, `marcas`, `canales`, `regiones`, `fuentes_trafico`) con los valores únicos del CSV usando INSERT ... ON CONFLICT DO NOTHING para ignorar duplicados.
2. WHEN se ejecuta una carga de datos, THE CSV_Loader SHALL poblar la tabla `usuarios` con los registros únicos por `user_id` usando INSERT ... ON CONFLICT DO NOTHING.
3. WHEN se ejecuta una carga de datos, THE CSV_Loader SHALL poblar la tabla `productos` con los registros únicos por `product_id` usando INSERT ... ON CONFLICT DO NOTHING.
4. WHEN se ejecuta una carga de datos, THE CSV_Loader SHALL poblar la tabla `sesiones` con los registros únicos por `session_id` usando INSERT ... ON CONFLICT DO NOTHING.
5. WHEN se ejecuta una carga de datos, THE CSV_Loader SHALL insertar todos los registros del CSV en la tabla `interacciones` en lotes (chunks) de máximo 5,000 registros para optimizar el rendimiento.
6. WHEN se ejecuta una carga de datos, THE CSV_Loader SHALL poblar la tabla `transacciones` únicamente con los registros donde `is_conversion = True`.
7. WHEN se solicita una recarga, THE CSV_Loader SHALL truncar en cascada las tablas `interacciones`, `transacciones`, `sesiones`, `productos`, `usuarios`, `categorias`, `marcas`, `canales`, `regiones` y `fuentes_trafico` antes de reinsertar los datos.
8. WHEN la carga de datos finaliza exitosamente, THE CSV_Loader SHALL retornar el número total de registros insertados en `interacciones`, que debe ser igual al número de filas del CSV.
9. IF ocurre un error durante la inserción en la base de datos, THEN THE CSV_Loader SHALL revertir la transacción completa (rollback) y retornar un mensaje de error que incluya la tabla afectada y el motivo del fallo.
10. THE CSV_Loader SHALL completar la carga de los 100,000 registros en la tabla `interacciones` en un tiempo máximo de 120 segundos en condiciones normales de hardware.

---

### Requirement 4: Interfaz Web — Página Principal

**User Story:** Como usuario del sistema, quiero acceder a una página web que centralice las funciones de carga y visualización de datos, para operar el sistema sin necesidad de usar la línea de comandos.

#### Acceptance Criteria

1. THE Dashboard SHALL exponer una ruta HTTP GET en `/` que retorne la página principal con código de estado 200 en menos de 2 segundos.
2. THE Dashboard SHALL mostrar en la página principal un botón con la etiqueta "Cargar / Recargar Dataset" que sea siempre visible en la parte superior de la página (above the fold), independientemente del estado de los datos.
3. THE Dashboard SHALL mostrar en la página principal un contador con el total de registros actualmente almacenados en la tabla `interacciones`, con el formato "Total de registros: {N}".
4. THE Dashboard SHALL mostrar en la página principal una tabla paginada con los primeros 100 registros de la tabla `interacciones`, ordenados por `id` ascendente.
5. THE Dashboard SHALL mostrar en la tabla paginada las siguientes columnas en este orden: `session_id`, `user_id`, `timestamp_utc`, `event_index`, `user_action`, `product_id`, `time_spent_sec`, `is_conversion`, `drop_off_flag`.
6. WHEN la tabla `interacciones` está vacía, THE Dashboard SHALL mostrar la tabla con sus encabezados de columna pero sin filas de datos, junto con el mensaje "No hay datos cargados. Usa el botón para cargar el dataset." debajo de los encabezados, y el contador SHALL mostrar "Total de registros: 0".

---

### Requirement 5: Operación de Carga desde la Interfaz Web

**User Story:** Como usuario del sistema, quiero iniciar la carga del dataset desde la interfaz web y recibir feedback visual del progreso, para saber en todo momento el estado de la operación.

#### Acceptance Criteria

1. WHEN el usuario hace clic en el botón "Cargar / Recargar Dataset", THE Dashboard SHALL enviar una solicitud HTTP POST asíncrona (AJAX/fetch) a la ruta `/load-data`.
2. WHILE la solicitud POST a `/load-data` está pendiente, THE Dashboard SHALL mostrar un spinner de carga visible y deshabilitar el botón para prevenir clics duplicados.
3. WHEN la respuesta de `/load-data` tiene `status: "success"`, THE Dashboard SHALL mostrar un mensaje de éxito con el texto "Dataset cargado exitosamente. {N} registros insertados." donde `{N}` es el valor del campo `count` en la respuesta JSON.
4. WHEN la respuesta de `/load-data` tiene `status: "success"`, THE Dashboard SHALL actualizar automáticamente el contador de registros y la tabla paginada (página 1) sin recargar la página completa.
5. IF la respuesta de `/load-data` tiene `status: "error"`, THEN THE Dashboard SHALL mostrar un mensaje de error con el texto "Error al cargar el dataset: {message}" donde `{message}` es el campo `message` de la respuesta JSON.
6. IF la respuesta de `/load-data` tiene `status: "error"` o si la solicitud HTTP falla (sin respuesta del servidor), THEN THE Dashboard SHALL ocultar el spinner y rehabilitar el botón de carga.
7. THE Dashboard SHALL exponer la ruta HTTP POST `/load-data` que retorne una respuesta JSON con Content-Type `application/json` y los campos: `status` (string: "success" o "error"), `message` (string descriptivo), `count` (integer: número de registros insertados, 0 en caso de error).

---

### Requirement 6: Paginación de la Tabla de Interacciones

**User Story:** Como usuario del sistema, quiero navegar por los registros de interacciones en páginas, para explorar el dataset sin sobrecargar el navegador.

#### Acceptance Criteria

1. THE Dashboard SHALL exponer una ruta HTTP GET en `/interactions` que acepte los parámetros de consulta `page` (entero, por defecto 1) y `per_page` (entero, por defecto 100).
2. WHEN se solicita la ruta `/interactions` con parámetros válidos, THE Dashboard SHALL retornar una respuesta JSON con los campos: `data` (array de objetos con los campos de la tabla), `total` (integer: total de registros en `interacciones`), `page` (integer: página actual), `per_page` (integer: registros por página), `total_pages` (integer: ceil(total / per_page)).
3. WHEN el parámetro `page` recibido es menor a 1 o no es un entero válido, THE Dashboard SHALL tratarlo como `page = 1`.
4. WHEN el parámetro `per_page` recibido es mayor a 500, THE Dashboard SHALL limitarlo a 500 sin retornar error. WHEN el parámetro `per_page` es inválido (negativo, cero, o no es un entero), THE Dashboard SHALL usar el valor por defecto de 100.
5. THE Dashboard SHALL mostrar controles de navegación "Anterior" y "Siguiente" en la tabla paginada; el botón "Anterior" SHALL estar deshabilitado en la página 1 y el botón "Siguiente" SHALL estar deshabilitado en la última página. WHEN la tabla `interacciones` está vacía, ambos botones SHALL estar deshabilitados sin mostrar mensajes adicionales.
6. WHEN el usuario hace clic en "Anterior" o "Siguiente", THE Dashboard SHALL realizar una solicitud GET a `/interactions` con el número de página correspondiente y actualizar la tabla sin recargar la página completa.

---

### Requirement 7: Manejo de Errores y Resiliencia

**User Story:** Como usuario del sistema, quiero que los errores sean manejados de forma controlada y comunicados claramente, para poder diagnosticar y resolver problemas sin interrumpir la operación del sistema.

#### Acceptance Criteria

1. IF una ruta del Dashboard recibe parámetros de tipo incorrecto (ej. `page=abc`), THEN THE Dashboard SHALL retornar una respuesta JSON con `status: "error"`, un mensaje indicando el parámetro inválido, y código HTTP 400, a menos que también ocurra una excepción no controlada, en cuyo caso SHALL retornar HTTP 500.
2. IF ocurre una excepción no controlada en cualquier ruta del Dashboard, THEN THE Dashboard SHALL capturarla, registrarla en el log, y retornar una respuesta JSON con `status: "error"`, un mensaje genérico de error interno, y código HTTP 500.
3. IF la conexión a la base de datos no está disponible al momento de procesar una solicitud, THEN THE Dashboard SHALL retornar una respuesta JSON con `status: "error"`, mensaje "Base de datos no disponible", y código HTTP 503.
4. THE Dashboard SHALL registrar todos los errores en un archivo de log `retailytics.log` en la raíz del proyecto usando el módulo `logging` de Python, con formato: `{timestamp} [{nivel}] {mensaje}`, donde nivel es WARNING, ERROR o CRITICAL según la severidad.
