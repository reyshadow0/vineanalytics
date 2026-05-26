"""
CSV_Loader — Lectura, validación y carga de datos desde CSV.

Responsabilidades:
- Leer y validar el archivo CSV (read_and_validate_csv).
- Cargar el DataFrame normalizado en las 10 tablas (load_data).
- Truncar y recargar los datos (reload_data).
"""

import pandas as pd
import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from db_manager import (
    categorias,
    marcas,
    canales,
    regiones,
    fuentes_trafico,
    usuarios,
    productos,
    sesiones,
    transacciones,
    interacciones,
)


# ---------------------------------------------------------------------------
# Columnas requeridas (orden canónico del CSV)
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "session_id",
    "user_id",
    "timestamp_utc",
    "event_index",
    "user_action",
    "product_id",
    "category",
    "brand",
    "price",
    "channel",
    "device_type",
    "region",
    "traffic_source",
    "time_spent_sec",
    "session_length",
    "interaction_count",
    "is_conversion",
    "drop_off_flag",
]


# ---------------------------------------------------------------------------
# Función pública: read_and_validate_csv
# ---------------------------------------------------------------------------


def read_and_validate_csv(csv_path: str) -> pd.DataFrame:
    """
    Lee el CSV desde ``csv_path`` y valida su estructura y tipos de datos.

    Precondiciones:
    - ``csv_path`` apunta a un archivo CSV con las 18 columnas requeridas.

    Postcondiciones:
    - ``df.columns`` contiene exactamente las 18 columnas requeridas.
    - ``df['timestamp_utc'].dtype == datetime64[ns, UTC]``
    - ``df['is_conversion'].dtype == bool``
    - ``df['drop_off_flag'].dtype == bool``
    - ``df['price'].dtype == float64``
    - ``len(df) > 0``

    Args:
        csv_path: Ruta al archivo CSV a leer.

    Returns:
        pd.DataFrame: DataFrame validado con los tipos de datos correctos.

    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta especificada.
        ValueError: Si el CSV tiene columnas faltantes, está vacío, o
            contiene valores inválidos en ``timestamp_utc``,
            ``is_conversion``, ``drop_off_flag`` o ``price``.
    """
    # ------------------------------------------------------------------
    # 1. Leer el CSV — capturar FileNotFoundError explícitamente
    # ------------------------------------------------------------------
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Archivo no encontrado en la ruta especificada: {csv_path}"
        )

    # ------------------------------------------------------------------
    # 2. Verificar columnas requeridas
    # ------------------------------------------------------------------
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Columnas faltantes en el CSV: {missing_cols}"
        )

    # ------------------------------------------------------------------
    # 3. Verificar que el DataFrame no esté vacío
    # ------------------------------------------------------------------
    if len(df) == 0:
        raise ValueError(
            "El archivo CSV no contiene registros para cargar "
            "(el archivo está vacío o solo tiene encabezado)."
        )

    # ------------------------------------------------------------------
    # 4. Convertir timestamp_utc a datetime64[ns, UTC]
    # ------------------------------------------------------------------
    try:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    except Exception as exc:
        raise ValueError(
            f"Error al convertir 'timestamp_utc' a datetime con zona horaria UTC: {exc}"
        ) from exc

    # ------------------------------------------------------------------
    # 5. Convertir is_conversion y drop_off_flag a bool
    #    Solo se permiten los valores 0 y 1 (o True/False ya convertidos).
    # ------------------------------------------------------------------
    for bool_col in ("is_conversion", "drop_off_flag"):
        # Detectar valores que no sean 0 ni 1 antes de convertir
        col_series = df[bool_col]
        invalid_mask = ~col_series.isin([0, 1, True, False])
        if invalid_mask.any():
            invalid_values = col_series[invalid_mask].unique().tolist()
            raise ValueError(
                f"La columna '{bool_col}' contiene valores inválidos "
                f"(se esperan 0 o 1): {invalid_values}"
            )
        df[bool_col] = col_series.astype(bool)

    # ------------------------------------------------------------------
    # 6. Convertir price a float64
    # ------------------------------------------------------------------
    try:
        df["price"] = pd.to_numeric(df["price"], errors="raise").astype("float64")
    except (ValueError, TypeError) as exc:
        # Identificar los valores no numéricos para el mensaje de error
        non_numeric_mask = pd.to_numeric(df["price"], errors="coerce").isna()
        invalid_values = df.loc[non_numeric_mask, "price"].unique().tolist()
        raise ValueError(
            f"La columna 'price' contiene valores no numéricos: {invalid_values}"
        ) from exc

    return df


# ---------------------------------------------------------------------------
# Función pública: load_data
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 5_000


def load_data(engine: Engine, df: pd.DataFrame) -> int:
    """
    Carga el DataFrame validado en las 10 tablas normalizadas dentro de una
    única transacción SQLAlchemy.

    Precondiciones:
    - ``engine`` está conectado y las tablas ya existen (creadas por
      ``db_manager.create_tables``).
    - ``df`` fue validado por ``read_and_validate_csv`` (tipos correctos,
      18 columnas, al menos 1 fila).

    Postcondiciones:
    - Todas las tablas están pobladas en el orden correcto de FK.
    - Retorna ``COUNT(*)`` de ``interacciones``, que debe ser igual a
      ``len(df)``.

    Args:
        engine: Engine de SQLAlchemy apuntando a ``retailytics_db``.
        df: DataFrame validado con los 18 campos del CSV.

    Returns:
        int: Número total de filas en la tabla ``interacciones`` tras la
        inserción.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: Si ocurre cualquier error durante la
            inserción. La transacción se revierte automáticamente (el bloque
            ``engine.begin()`` hace rollback al salir con excepción). Se
            relanza con un mensaje que indica la tabla afectada y el motivo.
    """
    current_table = "desconocida"

    try:
        with engine.begin() as conn:

            # ------------------------------------------------------------------
            # 2a. Tablas de catálogo — INSERT ON CONFLICT DO NOTHING
            # ------------------------------------------------------------------

            # categorias
            current_table = "categorias"
            cat_values = [
                {"nombre": v} for v in df["category"].dropna().unique()
            ]
            if cat_values:
                conn.execute(
                    pg_insert(categorias).values(cat_values).on_conflict_do_nothing()
                )

            # marcas
            current_table = "marcas"
            brand_values = [
                {"nombre": v} for v in df["brand"].dropna().unique()
            ]
            if brand_values:
                conn.execute(
                    pg_insert(marcas).values(brand_values).on_conflict_do_nothing()
                )

            # canales
            current_table = "canales"
            channel_values = [
                {"nombre": v} for v in df["channel"].dropna().unique()
            ]
            if channel_values:
                conn.execute(
                    pg_insert(canales).values(channel_values).on_conflict_do_nothing()
                )

            # regiones
            current_table = "regiones"
            region_values = [
                {"nombre": v} for v in df["region"].dropna().unique()
            ]
            if region_values:
                conn.execute(
                    pg_insert(regiones).values(region_values).on_conflict_do_nothing()
                )

            # fuentes_trafico
            current_table = "fuentes_trafico"
            source_values = [
                {"nombre": v} for v in df["traffic_source"].dropna().unique()
            ]
            if source_values:
                conn.execute(
                    pg_insert(fuentes_trafico)
                    .values(source_values)
                    .on_conflict_do_nothing()
                )

            # ------------------------------------------------------------------
            # 2b. Lookup maps {nombre: id} para resolver FKs
            # ------------------------------------------------------------------

            cat_map: dict[str, int] = {
                row.nombre: row.category_id
                for row in conn.execute(
                    sqlalchemy.select(
                        categorias.c.category_id, categorias.c.nombre
                    )
                )
            }

            brand_map: dict[str, int] = {
                row.nombre: row.brand_id
                for row in conn.execute(
                    sqlalchemy.select(marcas.c.brand_id, marcas.c.nombre)
                )
            }

            channel_map: dict[str, int] = {
                row.nombre: row.channel_id
                for row in conn.execute(
                    sqlalchemy.select(canales.c.channel_id, canales.c.nombre)
                )
            }

            region_map: dict[str, int] = {
                row.nombre: row.region_id
                for row in conn.execute(
                    sqlalchemy.select(regiones.c.region_id, regiones.c.nombre)
                )
            }

            source_map: dict[str, int] = {
                row.nombre: row.source_id
                for row in conn.execute(
                    sqlalchemy.select(
                        fuentes_trafico.c.source_id, fuentes_trafico.c.nombre
                    )
                )
            }

            # ------------------------------------------------------------------
            # 2c. Usuarios — únicos por user_id, INSERT ON CONFLICT DO NOTHING
            # ------------------------------------------------------------------

            current_table = "usuarios"
            usuarios_df = (
                df[["user_id", "region", "device_type"]]
                .drop_duplicates(subset="user_id")
            )
            usuarios_values = [
                {
                    "user_id": row.user_id,
                    "region_id": region_map[row.region],
                    "device_type": row.device_type,
                }
                for row in usuarios_df.itertuples(index=False)
            ]
            if usuarios_values:
                conn.execute(
                    pg_insert(usuarios)
                    .values(usuarios_values)
                    .on_conflict_do_nothing()
                )

            # ------------------------------------------------------------------
            # 2d. Productos — únicos por product_id, INSERT ON CONFLICT DO NOTHING
            # ------------------------------------------------------------------

            current_table = "productos"
            productos_df = (
                df[["product_id", "category", "brand", "price"]]
                .drop_duplicates(subset="product_id")
            )
            productos_values = [
                {
                    "product_id": row.product_id,
                    "category_id": cat_map[row.category],
                    "brand_id": brand_map[row.brand],
                    "price": row.price,
                }
                for row in productos_df.itertuples(index=False)
            ]
            if productos_values:
                conn.execute(
                    pg_insert(productos)
                    .values(productos_values)
                    .on_conflict_do_nothing()
                )

            # ------------------------------------------------------------------
            # 2e. Sesiones — únicas por session_id, INSERT ON CONFLICT DO NOTHING
            # ------------------------------------------------------------------

            current_table = "sesiones"
            sesiones_df = (
                df[["session_id", "user_id", "channel", "traffic_source", "session_length"]]
                .drop_duplicates(subset="session_id")
            )
            sesiones_values = [
                {
                    "session_id": row.session_id,
                    "user_id": row.user_id,
                    "channel_id": channel_map[row.channel],
                    "source_id": source_map[row.traffic_source],
                    "session_length": int(row.session_length),
                }
                for row in sesiones_df.itertuples(index=False)
            ]
            if sesiones_values:
                conn.execute(
                    pg_insert(sesiones)
                    .values(sesiones_values)
                    .on_conflict_do_nothing()
                )

            # ------------------------------------------------------------------
            # 2f. Interacciones — todos los registros, en chunks de 5,000
            # ------------------------------------------------------------------

            current_table = "interacciones"
            interacciones_cols = [
                "session_id",
                "user_id",
                "timestamp_utc",
                "event_index",
                "user_action",
                "product_id",
                "time_spent_sec",
                "interaction_count",
                "is_conversion",
                "drop_off_flag",
            ]
            interacciones_df = df[interacciones_cols]

            for start in range(0, len(interacciones_df), _CHUNK_SIZE):
                chunk = interacciones_df.iloc[start : start + _CHUNK_SIZE]
                chunk_values = [
                    {
                        "session_id": row.session_id,
                        "user_id": row.user_id,
                        "timestamp_utc": row.timestamp_utc,
                        "event_index": int(row.event_index),
                        "user_action": row.user_action,
                        "product_id": row.product_id,
                        "time_spent_sec": (
                            None
                            if pd.isna(row.time_spent_sec)
                            else int(row.time_spent_sec)
                        ),
                        "interaction_count": (
                            None
                            if pd.isna(row.interaction_count)
                            else int(row.interaction_count)
                        ),
                        "is_conversion": bool(row.is_conversion),
                        "drop_off_flag": bool(row.drop_off_flag),
                    }
                    for row in chunk.itertuples(index=False)
                ]
                conn.execute(interacciones.insert().values(chunk_values))

            # ------------------------------------------------------------------
            # 2g. Transacciones — solo filas donde is_conversion == True
            # ------------------------------------------------------------------

            current_table = "transacciones"
            conv_df = df[df["is_conversion"] == True][
                ["session_id", "user_id", "product_id", "is_conversion"]
            ]
            if not conv_df.empty:
                transacciones_values = [
                    {
                        "session_id": row.session_id,
                        "user_id": row.user_id,
                        "product_id": row.product_id,
                        "is_conversion": bool(row.is_conversion),
                    }
                    for row in conv_df.itertuples(index=False)
                ]
                conn.execute(
                    pg_insert(transacciones)
                    .values(transacciones_values)
                    .on_conflict_do_nothing()
                )

            # ------------------------------------------------------------------
            # Retornar COUNT(*) de interacciones
            # ------------------------------------------------------------------

            count_result = conn.execute(
                sqlalchemy.select(sqlalchemy.func.count()).select_from(interacciones)
            )
            return count_result.scalar()

    except SQLAlchemyError as exc:
        raise SQLAlchemyError(
            f"Error al insertar en la tabla '{current_table}': {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Función pública: reload_data
# ---------------------------------------------------------------------------

_TRUNCATE_SQL = (
    "TRUNCATE TABLE interacciones, transacciones, sesiones, productos, "
    "usuarios, categorias, marcas, canales, regiones, fuentes_trafico "
    "RESTART IDENTITY CASCADE"
)


def reload_data(engine: Engine, csv_path: str) -> int:
    """
    Trunca todas las tablas y recarga los datos desde el CSV.

    Precondiciones:
    - ``engine`` está conectado y las tablas ya existen.
    - ``csv_path`` apunta a un archivo CSV válido con las 18 columnas
      requeridas.

    Postcondiciones:
    - Todas las tablas quedan vacías y con sus secuencias SERIAL
      reiniciadas antes de la recarga.
    - Retorna el número total de filas insertadas en ``interacciones``,
      que debe ser igual al número de filas del CSV.

    Args:
        engine: Engine de SQLAlchemy apuntando a ``retailytics_db``.
        csv_path: Ruta al archivo CSV a cargar.

    Returns:
        int: Número total de filas en la tabla ``interacciones`` tras la
        inserción.

    Raises:
        FileNotFoundError: Si el archivo CSV no existe.
        ValueError: Si el CSV tiene columnas faltantes, está vacío o
            contiene valores inválidos.
        sqlalchemy.exc.SQLAlchemyError: Si ocurre un error durante el
            TRUNCATE o la inserción.
    """
    # 1. Leer y validar el CSV antes de tocar la base de datos
    df = read_and_validate_csv(csv_path)

    # 2. Truncar todas las tablas en orden inverso de FK con RESTART IDENTITY
    #    TRUNCATE es DDL en PostgreSQL; engine.begin() garantiza autocommit
    #    al salir del bloque sin excepción.
    with engine.begin() as conn:
        conn.execute(sqlalchemy.text(_TRUNCATE_SQL))

    # 3. Cargar los datos y retornar el conteo
    return load_data(engine, df)
