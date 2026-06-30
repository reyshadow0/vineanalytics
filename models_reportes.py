"""
models_reportes.py — Persistencia operacional del reporte diario CU-O16 (OP11).

Registra cada generación del reporte operativo diario en PocketBase (colección
`reportes_operativos`) para auditoría y reproducibilidad (RN-1205) y como evento
de generación (éxito/bloqueo/fallo) para observabilidad (§8). Respeta la
arquitectura de capas: aquí SOLO se habla con PocketBase (metadatos
operacionales); las CIFRAS del reporte se leen de ClickHouse en
`reportes/reporte_diario.py` (RN-1202).

Reutiliza el patrón pb_client de CU-O08/CU-O06 (sellos_calidad/publicaciones).
"""

from __future__ import annotations

import json
from datetime import datetime

from pb_client import PBClient, get_client

COLECCION = "reportes_operativos"


def _cli(client: PBClient | None) -> PBClient:
    return client or get_client()


def registrar_reporte(reporte: dict, client: PBClient | None = None) -> dict:
    """Crea/actualiza el registro del reporte del día (upsert por fecha → idempotente).

    Guarda el estado (PUBLICADO/BLOQUEADO_SIN_CALIDAD/FALLIDO), el período, el sello
    de calidad usado y el documento completo serializado (auditoría)."""
    client = _cli(client)
    data = {
        "fecha": reporte.get("fecha"),
        "periodo": str(reporte.get("periodo") or ""),
        "estado": reporte.get("estado"),
        "calidad_ok": bool(reporte.get("calidad_ok")),
        "sello": reporte.get("sello") or "",
        "documento": json.dumps(reporte, ensure_ascii=False),
        "generado_en": reporte.get("generado_en") or datetime.now().isoformat(timespec="seconds"),
    }
    existente = client.find_one(COLECCION, fecha=data["fecha"])
    if existente:
        return client.update(COLECCION, existente["id"], data)
    return client.create(COLECCION, data)


def ultimo_reporte(client: PBClient | None = None) -> dict | None:
    """Devuelve el reporte más reciente registrado (para el endpoint/consulta)."""
    client = _cli(client)
    regs = client.find(COLECCION)
    if not regs:
        return None
    regs.sort(key=lambda r: str(r.get("fecha") or ""), reverse=True)
    return regs[0]
