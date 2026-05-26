"""
db_manager.py — Conexión a StarRocks para tablas de sistema (usuarios, auditoría).
Reemplaza completamente la dependencia de PostgreSQL.
"""

import mysql.connector
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS,
)


def get_conn() -> mysql.connector.MySQLConnection:
    return mysql.connector.connect(
        host=STARROCKS_HOST,
        port=STARROCKS_PORT,
        database=STARROCKS_DB,
        user=STARROCKS_USER,
        password=STARROCKS_PASS,
        connection_timeout=10,
    )
