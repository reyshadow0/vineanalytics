"""
models.py — Gestión de usuarios usando StarRocks vía mysql-connector.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash
from db_manager import get_conn


def init_default_users() -> None:
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM usuarios_sistema")
        if cur.fetchone()[0] == 0:
            users = [
                (1, "admin",    generate_password_hash("admin123"),    "admin",    True, datetime.now()),
                (2, "analista1",generate_password_hash("analista123"), "analista", True, datetime.now()),
                (3, "gerente1", generate_password_hash("gerente123"),  "gerente",  True, datetime.now()),
            ]
            cur.executemany(
                "INSERT INTO usuarios_sistema "
                "(id, username, password_hash, rol, activo, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                users,
            )
            conn.commit()
    finally:
        cur.close()
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT * FROM usuarios_sistema WHERE username = %s AND activo = TRUE",
            (username,),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def get_all_users() -> list[dict]:
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, username, rol, activo, created_at FROM usuarios_sistema ORDER BY id")
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def create_user(username: str, password: str, rol: str) -> None:
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM usuarios_sistema")
        new_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO usuarios_sistema (id, username, password_hash, rol, activo, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (new_id, username, generate_password_hash(password), rol, True, datetime.now()),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def update_user(user_id: int, rol: str, activo: bool) -> None:
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT username, password_hash, created_at FROM usuarios_sistema WHERE id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "INSERT INTO usuarios_sistema (id, username, password_hash, rol, activo, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, row[0], row[1], rol, activo, row[2]),
            )
            conn.commit()
    finally:
        cur.close()
        conn.close()


def delete_user(user_id: int) -> None:
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("DELETE FROM usuarios_sistema WHERE id = %s", (user_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def username_exists(username: str) -> bool:
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM usuarios_sistema WHERE username = %s", (username,))
        return cur.fetchone()[0] > 0
    finally:
        cur.close()
        conn.close()
