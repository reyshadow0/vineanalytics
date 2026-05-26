"""
audit.py — Registro de eventos en StarRocks.
"""

import logging
from datetime import datetime
from db_manager import get_conn


def registrar_evento(usuario: str, rol: str, accion: str,
                     detalle: str = None, ip: str = None) -> None:
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM auditoria")
        new_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO auditoria (id, usuario, rol, accion, detalle, ip, fecha) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_id, usuario, rol, accion, detalle, ip, datetime.now()),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        logging.error("Error al registrar evento de auditoría: %s", exc)


def get_eventos(usuario: str = None, accion: str = None,
                fecha: str = None, limit: int = 500) -> list[dict]:
    conn = get_conn()
    cur  = conn.cursor(dictionary=True)
    try:
        conditions, params = [], []
        if usuario:
            conditions.append("usuario LIKE %s")
            params.append(f"%{usuario}%")
        if accion:
            conditions.append("accion LIKE %s")
            params.append(f"%{accion}%")
        if fecha:
            conditions.append("DATE(fecha) = %s")
            params.append(fecha)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        cur.execute(
            f"SELECT id, fecha, usuario, rol, accion, detalle, ip "
            f"FROM auditoria {where} ORDER BY id DESC LIMIT %s",
            params,
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()
