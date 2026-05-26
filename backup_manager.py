"""
backup_manager.py — Respaldos en JSON y monitoreo de StarRocks.
"""

import os
import json
import logging
import threading
import time
from datetime import datetime

from db_manager import get_conn

BACKUP_DIR = "backups"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BackupManager")

db_status = "online"


def ensure_backup_dir() -> None:
    os.makedirs(BACKUP_DIR, exist_ok=True)


# ── Health check ──────────────────────────────────────────────────────────────

def check_db_health() -> None:
    global db_status
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
        conn.close()
        db_status = "online"
    except Exception as exc:
        logger.warning("StarRocks no responde: %s", exc)
        db_status = "caida"


def get_db_status() -> str:
    return db_status


# ── Backup: exporta usuarios y auditoría a JSON ───────────────────────────────

def create_backup(backup_type: str = "manual") -> tuple[bool, str]:
    ensure_backup_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename  = f"vinanalytics_{timestamp}_{backup_type}.json"
    filepath  = os.path.join(BACKUP_DIR, filename)

    try:
        conn = get_conn()
        cur  = conn.cursor(dictionary=True)

        cur.execute("SELECT id, username, rol, activo, created_at FROM usuarios_sistema")
        usuarios = cur.fetchall()
        for u in usuarios:
            if u.get("created_at"):
                u["created_at"] = str(u["created_at"])

        cur.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT 5000")
        auditoria = cur.fetchall()
        for a in auditoria:
            if a.get("fecha"):
                a["fecha"] = str(a["fecha"])

        cur.close()
        conn.close()

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"usuarios": usuarios, "auditoria": auditoria}, f,
                      ensure_ascii=False, indent=2)

        logger.info("Respaldo creado: %s", filepath)
        return True, filepath
    except Exception as exc:
        logger.error("Error al crear respaldo: %s", exc)
        return False, str(exc)


def restore_backup(filename: str) -> tuple[bool, str]:
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        return False, "Archivo no encontrado"
    if not filename.endswith(".json"):
        return False, "Solo se soportan respaldos .json"

    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        conn = get_conn()
        cur  = conn.cursor()

        for u in data.get("usuarios", []):
            cur.execute(
                "INSERT INTO usuarios_sistema (id, username, password_hash, rol, activo, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (u["id"], u["username"], u["password_hash"],
                 u["rol"], u["activo"], u.get("created_at")),
            )
        conn.commit()
        cur.close()
        conn.close()
        return True, "Restauración completada"
    except Exception as exc:
        logger.error("Error al restaurar: %s", exc)
        return False, str(exc)


def delete_backup(filename: str) -> bool:
    filepath = os.path.join(BACKUP_DIR, filename)
    try:
        os.remove(filepath)
        return True
    except OSError:
        return False


def list_backups() -> list[dict]:
    ensure_backup_dir()
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".json"):
            filepath = os.path.join(BACKUP_DIR, f)
            stat = os.stat(filepath)
            size_kb = round(stat.st_size / 1024, 1)
            btype = "Manual"
            if "_diario" in f:   btype = "Diario"
            elif "_semanal" in f: btype = "Semanal"
            elif "_mensual" in f: btype = "Mensual"
            backups.append({
                "filename":  f,
                "date":      datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "size":      f"{size_kb} KB",
                "type":      btype,
                "timestamp": stat.st_mtime,
            })
    return sorted(backups, key=lambda x: x["timestamp"], reverse=True)


def get_recovery_history() -> list[dict]:
    history_file = os.path.join(BACKUP_DIR, "recovery_history.json")
    if os.path.exists(history_file):
        try:
            with open(history_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


# ── Monitor en background ─────────────────────────────────────────────────────

def _monitor_loop() -> None:
    while True:
        check_db_health()
        time.sleep(30)


def start_monitor() -> None:
    t = threading.Thread(target=_monitor_loop, daemon=True)
    t.start()
    logger.info("Monitor StarRocks iniciado.")
