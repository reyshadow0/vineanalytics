"""
DB_Manager — Gestión de conexión, esquema e índices de base de datos.
"""

import sqlalchemy
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    TIMESTAMP,
    create_engine,
    text,
)
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# ---------------------------------------------------------------------------
# Constantes de conexión
# ---------------------------------------------------------------------------

_ADMIN_DB_URL = "postgresql://postgres@localhost/postgres"
_APP_DB_URL   = "postgresql://postgres@localhost/vacia"
_DB_NAME      = "vacia"

# ---------------------------------------------------------------------------
# ensure_database_exists
# ---------------------------------------------------------------------------

def ensure_database_exists() -> None:
    """Crea retailytics_db si no existe, conectándose a la DB admin postgres."""
    try:
        engine = create_engine(_ADMIN_DB_URL, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": _DB_NAME},
            ).fetchone() is not None
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{_DB_NAME}"'))
        engine.dispose()
    except OperationalError as exc:
        original = str(exc.orig) if exc.orig else str(exc)
        lower = original.lower()
        if "connection refused" in lower or "could not connect" in lower:
            reason = "host no alcanzable (connection refused en localhost:5432)"
        elif "password authentication failed" in lower or "authentication failed" in lower:
            reason = "credenciales inválidas"
        else:
            reason = original
        raise OperationalError(
            statement=exc.statement, params=exc.params, orig=exc.orig
        ) from Exception(f"No se pudo conectar a PostgreSQL: {reason}")


# ---------------------------------------------------------------------------
# get_engine
# ---------------------------------------------------------------------------

def get_engine() -> sqlalchemy.engine.Engine:
    """Retorna un Engine configurado para retailytics_db."""
    return create_engine(
        _APP_DB_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
    )


# ---------------------------------------------------------------------------
# Esquema de tablas
# ---------------------------------------------------------------------------

metadata = MetaData()

categorias = Table(
    "categorias", metadata,
    Column("category_id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(255), nullable=False, unique=True),
)

marcas = Table(
    "marcas", metadata,
    Column("brand_id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(255), nullable=False, unique=True),
)

canales = Table(
    "canales", metadata,
    Column("channel_id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(100), nullable=False, unique=True),
)

regiones = Table(
    "regiones", metadata,
    Column("region_id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(100), nullable=False, unique=True),
)

fuentes_trafico = Table(
    "fuentes_trafico", metadata,
    Column("source_id", Integer, primary_key=True, autoincrement=True),
    Column("nombre", String(100), nullable=False, unique=True),
)

usuarios = Table(
    "usuarios", metadata,
    Column("user_id", String(50), primary_key=True),
    Column("region_id", Integer, ForeignKey("regiones.region_id"), nullable=False),
    Column("device_type", String(50), nullable=False),
)

productos = Table(
    "productos", metadata,
    Column("product_id", String(50), primary_key=True),
    Column("category_id", Integer, ForeignKey("categorias.category_id"), nullable=False),
    Column("brand_id", Integer, ForeignKey("marcas.brand_id"), nullable=False),
    Column("price", Numeric(12, 2), nullable=False),
)

sesiones = Table(
    "sesiones", metadata,
    Column("session_id", String(50), primary_key=True),
    Column("user_id", String(50), ForeignKey("usuarios.user_id"), nullable=False),
    Column("channel_id", Integer, ForeignKey("canales.channel_id"), nullable=False),
    Column("source_id", Integer, ForeignKey("fuentes_trafico.source_id"), nullable=False),
    Column("session_length", Integer, nullable=False),
)

transacciones = Table(
    "transacciones", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String(50), ForeignKey("sesiones.session_id"), nullable=False),
    Column("user_id", String(50), ForeignKey("usuarios.user_id"), nullable=False),
    Column("product_id", String(50), ForeignKey("productos.product_id"), nullable=False),
    Column("is_conversion", Boolean, nullable=False),
)

interacciones = Table(
    "interacciones", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String(50), ForeignKey("sesiones.session_id"), nullable=False),
    Column("user_id", String(50), ForeignKey("usuarios.user_id"), nullable=False),
    Column("timestamp_utc", TIMESTAMP(timezone=True), nullable=False),
    Column("event_index", Integer, nullable=False),
    Column("user_action", String(50), nullable=False),
    Column("product_id", String(50), ForeignKey("productos.product_id"), nullable=False),
    Column("time_spent_sec", Integer),
    Column("interaction_count", Integer),
    Column("is_conversion", Boolean, nullable=False, default=False),
    Column("drop_off_flag", Boolean, nullable=False, default=False),
)

# ---------------------------------------------------------------------------
# Índices de rendimiento para interacciones
# Definidos aquí para que create_all los cree junto con las tablas.
# También se crean explícitamente en create_indexes() para bases existentes.
# ---------------------------------------------------------------------------

_INDEXES = [
    Index("ix_interacciones_user_action",  interacciones.c.user_action),
    Index("ix_interacciones_is_conversion", interacciones.c.is_conversion),
    Index("ix_interacciones_drop_off_flag", interacciones.c.drop_off_flag),
    Index("ix_interacciones_timestamp_utc", interacciones.c.timestamp_utc),
    Index("ix_interacciones_session_id",    interacciones.c.session_id),
    Index("ix_interacciones_user_id",       interacciones.c.user_id),
    Index("ix_interacciones_product_id",    interacciones.c.product_id),
    # Índice en productos.price para filtros de rango
    Index("ix_productos_price",             productos.c.price),
]

# ---------------------------------------------------------------------------
# create_tables
# ---------------------------------------------------------------------------

def create_tables(engine: sqlalchemy.engine.Engine) -> None:
    """Crea las 10 tablas si no existen (idempotente)."""
    try:
        metadata.create_all(engine, checkfirst=True)
    except SQLAlchemyError as exc:
        raise SQLAlchemyError(f"Error al crear las tablas del esquema: {exc}") from exc


# ---------------------------------------------------------------------------
# create_indexes  — crea índices si no existen (idempotente)
# ---------------------------------------------------------------------------

def create_indexes(engine: sqlalchemy.engine.Engine) -> None:
    """
    Crea los índices de rendimiento en interacciones y productos.
    Usa CREATE INDEX IF NOT EXISTS para ser idempotente.
    Se ejecuta al arrancar la app para garantizar que los índices existan
    incluso en bases de datos creadas antes de esta versión.
    """
    index_ddl = [
        "CREATE INDEX IF NOT EXISTS ix_interacciones_user_action   ON interacciones (user_action)",
        "CREATE INDEX IF NOT EXISTS ix_interacciones_is_conversion  ON interacciones (is_conversion)",
        "CREATE INDEX IF NOT EXISTS ix_interacciones_drop_off_flag  ON interacciones (drop_off_flag)",
        "CREATE INDEX IF NOT EXISTS ix_interacciones_timestamp_utc  ON interacciones (timestamp_utc)",
        "CREATE INDEX IF NOT EXISTS ix_interacciones_session_id     ON interacciones (session_id)",
        "CREATE INDEX IF NOT EXISTS ix_interacciones_user_id        ON interacciones (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_interacciones_product_id     ON interacciones (product_id)",
        "CREATE INDEX IF NOT EXISTS ix_productos_price              ON productos (price)",
    ]
    try:
        with engine.begin() as conn:
            for ddl in index_ddl:
                conn.execute(text(ddl))
    except SQLAlchemyError as exc:
        # No fatal — log but don't crash the app
        import logging
        logging.warning("No se pudieron crear algunos índices: %s", exc)
