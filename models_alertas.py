"""
models_alertas.py — Lógica de negocio de CU-O13 «Generar alerta» (OP9 · `alertas`).

Punto ÚNICO de alertas del nivel operativo (RT-16). Implementa, sobre PocketBase
(capa operacional, patrón pb_client de CU-O08/CU-O16):

  - El **bus de señales** (`senales_alerta`): cada paquete emisor —machine-learning
    (churn/precio), observabilidad (uptime/latencia), ingesta, api, conversión—
    deja una señal normalizada; `alertas` la consume (RF-902, RN-1001).
  - La **generación/registro** de la alerta con clasificación tipo/severidad/causa
    (RF-903/904), **enrutamiento** al responsable (RF-905), **deduplicación**
    anti-tormenta (RF-906, RN-1004) y **ciclo de vida** (RF-907).

Capas (RN-1006/RT-01): aquí SOLO se habla con PocketBase. Las LECTURAS que motivan
una señal (churn de Fact_Retencion, precio de Fact_Precio_Mercado, uptime de
Fact_Disponibilidad) las hacen los paquetes emisores sobre el DW/agregaciones y
llegan ya normalizadas como señal; alertas no salta de capa.
"""

from __future__ import annotations

import json
from datetime import datetime

from pb_client import PBClient, get_client

COL_SENALES = "senales_alerta"
COL_ALERTAS = "alertas"

# ── Severidades (RF-903) ──────────────────────────────────────────────────────
INFO     = "info"
WARNING  = "warning"
CRITICAL = "critical"

# ── Ciclo de vida de la alerta (spec §9 · RF-907) ─────────────────────────────
ABIERTA    = "ABIERTA"
RECONOCIDA = "RECONOCIDA"
RESUELTA   = "RESUELTA"
SILENCIADA = "SILENCIADA"
# Una alerta sigue "viva" (agrupa duplicados) mientras no esté resuelta/silenciada.
ESTADOS_VIVOS = (ABIERTA, RECONOCIDA)

# ── Clasificación por tipo → (severidad por defecto, responsable) ─────────────
# RF-903 (severidad) + RF-905 (enrutamiento). RN-1002 churn=critical→Customer
# Success; RN-1003 precio→Ingeniería de datos; RN-1001 uptime/ingesta/api.
CLASIFICACION: dict[str, tuple[str, str]] = {
    "churn":      (CRITICAL, "Customer Success"),
    "precio":     (WARNING,  "Ingeniería de datos"),
    "uso":        (WARNING,  "Customer Success"),
    "uptime":     (CRITICAL, "DevOps"),
    "latencia":   (WARNING,  "DevOps"),
    "ingesta":    (CRITICAL, "Ingeniería de datos"),
    "api":        (WARNING,  "DevOps"),
    "ingresos":   (WARNING,  "Growth & Marketing"),
    "conversion": (WARNING,  "Growth & Marketing"),
}
RESPONSABLE_FALLBACK = "DevOps"


class AlertaError(Exception):
    def __init__(self, codigo: str, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cli(client: PBClient | None) -> PBClient:
    return client or get_client()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def clasificar(tipo: str, severidad: str | None = None) -> tuple[str, str]:
    """RF-903/905: deriva (severidad, responsable) del tipo de la señal.
    Si la señal trae una severidad explícita, se respeta; el responsable se
    enruta SIEMPRE por tipo (RF-905)."""
    sev_def, responsable = CLASIFICACION.get((tipo or "").lower(),
                                             (WARNING, RESPONSABLE_FALLBACK))
    return (severidad or sev_def), responsable


# ══════════════════════════════════════════════════════════════════════════════
# Bus de señales (RF-902) — lo escriben los paquetes emisores
# ══════════════════════════════════════════════════════════════════════════════

def emitir_senal(origen: str, tipo: str, clave: str, *, causa: str = "",
                 severidad: str | None = None, entidad: str = "",
                 valor: float | None = None, umbral: float | None = None,
                 id_tiempo: int | None = None, payload: dict | None = None,
                 fecha: str | None = None, client: PBClient | None = None) -> dict:
    """Emite una señal al bus (RF-902). Idempotente por (origen, clave, id_tiempo):
    reemitir la MISMA condición en el MISMO período actualiza la señal en vez de
    apilar otra (evita ruido y hace el DAG reejecutable sin duplicar)."""
    client = _cli(client)
    data = {
        "origen": origen, "tipo": tipo, "clave": clave, "causa": causa,
        "severidad": severidad or "", "entidad": entidad,
        "valor": float(valor) if valor is not None else None,
        "umbral": float(umbral) if umbral is not None else None,
        "id_tiempo": int(id_tiempo) if id_tiempo is not None else None,
        "payload": _dump(payload or {}),
        "fecha": fecha or _now(),
    }
    existente = client.find_one(COL_SENALES, origen=origen, clave=clave,
                                id_tiempo=data["id_tiempo"])
    if existente:
        # Conserva `procesada` para no reprocesar en una reejecución (idempotencia).
        return client.update(COL_SENALES, existente["id"], data)
    data["procesada"] = False
    return client.create(COL_SENALES, data)


def senales_pendientes(client: PBClient | None = None) -> list[dict]:
    """Señales aún no convertidas en alerta (procesada=false)."""
    client = _cli(client)
    return [s for s in client.find(COL_SENALES) if not s.get("procesada")]


def marcar_procesada(senal_id: str, client: PBClient | None = None) -> dict:
    client = _cli(client)
    return client.update(COL_SENALES, senal_id, {"procesada": True})


# ══════════════════════════════════════════════════════════════════════════════
# Generación y registro de la alerta (RF-904) con dedup (RF-906) y enrutamiento
# ══════════════════════════════════════════════════════════════════════════════

def _alerta_viva(client: PBClient, clave: str) -> dict | None:
    """Alerta con la misma `clave` que aún agrupa duplicados (no resuelta)."""
    for a in client.find(COL_ALERTAS, clave=clave):
        if a.get("estado") in ESTADOS_VIVOS:
            return a
    return None


def generar_alerta(tipo: str, clave: str, *, causa: str = "", origen: str = "",
                   severidad: str | None = None, entidad: str = "",
                   valor: float | None = None, umbral: float | None = None,
                   id_tiempo: int | None = None, payload: dict | None = None,
                   client: PBClient | None = None) -> tuple[dict, bool]:
    """RF-903/904/905/906: genera (o agrupa) una alerta.

    Deduplicación (RN-1004): si ya existe una alerta VIVA con la misma `clave`, la
    nueva señal NO crea otra: se agrupa incrementando `ocurrencias` y refrescando
    `ultima_vez`/valor. Devuelve `(alerta, creada)` donde `creada=False` indica que
    se agrupó con una existente.
    """
    client = _cli(client)
    sev, responsable = clasificar(tipo, severidad)
    ahora = _now()

    existente = _alerta_viva(client, clave)
    if existente:  # ── dedup / agrupación anti-tormenta (RF-906) ──
        actualizada = client.update(COL_ALERTAS, existente["id"], {
            "ocurrencias": int(existente.get("ocurrencias") or 1) + 1,
            "ultima_vez": ahora,
            "valor": float(valor) if valor is not None else existente.get("valor"),
        })
        return actualizada, False

    alerta = client.create(COL_ALERTAS, {
        "tipo": tipo, "severidad": sev, "causa": causa, "origen": origen,
        "responsable": responsable, "entidad": entidad, "clave": clave,
        "estado": ABIERTA, "ocurrencias": 1,
        "valor": float(valor) if valor is not None else None,
        "umbral": float(umbral) if umbral is not None else None,
        "id_tiempo": int(id_tiempo) if id_tiempo is not None else None,
        "payload": _dump(payload or {}),
        "primera_vez": ahora, "ultima_vez": ahora,
    })
    return alerta, True


def procesar_senal(senal: dict, client: PBClient | None = None) -> tuple[dict, bool]:
    """Convierte UNA señal del bus en alerta (clasifica + dedup) y la marca procesada."""
    client = _cli(client)
    payload = senal.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload) if payload else {}
        except (ValueError, TypeError):
            payload = {"raw": payload}
    alerta, creada = generar_alerta(
        tipo=senal.get("tipo"), clave=senal.get("clave"),
        causa=senal.get("causa", ""), origen=senal.get("origen", ""),
        severidad=senal.get("severidad") or None, entidad=senal.get("entidad", ""),
        valor=senal.get("valor"), umbral=senal.get("umbral"),
        id_tiempo=senal.get("id_tiempo"), payload=payload, client=client)
    if senal.get("id"):
        marcar_procesada(senal["id"], client)
    return alerta, creada


def procesar_pendientes(client: PBClient | None = None) -> dict:
    """Drena el bus: convierte todas las señales pendientes en alertas (con dedup).
    Es el corazón de la tarea `alertas` del DAG. Idempotente: una señal ya
    procesada no se reprocesa; una condición sostenida no duplica alerta."""
    client = _cli(client)
    pendientes = senales_pendientes(client)
    creadas, agrupadas = 0, 0
    generadas: list[dict] = []
    for s in pendientes:
        alerta, creada = procesar_senal(s, client)
        generadas.append(alerta)
        creadas += int(creada)
        agrupadas += int(not creada)
    return {"pendientes": len(pendientes), "creadas": creadas,
            "agrupadas": agrupadas, "alertas": generadas}


# ── Ciclo de vida (RF-907) ────────────────────────────────────────────────────
def _transicion(alerta_id: str, nuevo: str, client: PBClient | None = None) -> dict:
    client = _cli(client)
    a = client.find_one(COL_ALERTAS, id=alerta_id)
    if a is None:
        raise AlertaError("alerta_inexistente", f"No existe la alerta {alerta_id}.")
    return client.update(COL_ALERTAS, alerta_id,
                         {"estado": nuevo, "ultima_vez": _now()})


def reconocer(alerta_id: str, client: PBClient | None = None) -> dict:
    return _transicion(alerta_id, RECONOCIDA, client)


def resolver(alerta_id: str, client: PBClient | None = None) -> dict:
    return _transicion(alerta_id, RESUELTA, client)


def silenciar(alerta_id: str, client: PBClient | None = None) -> dict:
    return _transicion(alerta_id, SILENCIADA, client)


# ── Reporte de alertas para reportes-operativos (OP11 · §8) ───────────────────
def reporte_alertas(client: PBClient | None = None) -> dict:
    """Resumen auditable de alertas (consumible por CU-O16/OP11)."""
    client = _cli(client)
    alertas = client.find(COL_ALERTAS)
    por_estado: dict[str, int] = {}
    por_severidad: dict[str, int] = {}
    por_tipo: dict[str, int] = {}
    for a in alertas:
        por_estado[a.get("estado")] = por_estado.get(a.get("estado"), 0) + 1
        por_severidad[a.get("severidad")] = por_severidad.get(a.get("severidad"), 0) + 1
        por_tipo[a.get("tipo")] = por_tipo.get(a.get("tipo"), 0) + 1
    abiertas = [a for a in alertas if a.get("estado") in ESTADOS_VIVOS]
    abiertas.sort(key=lambda a: str(a.get("ultima_vez") or ""), reverse=True)
    return {
        "total": len(alertas),
        "abiertas": len(abiertas),
        "por_estado": por_estado,
        "por_severidad": por_severidad,
        "por_tipo": por_tipo,
        "ultimas": abiertas[:20],
    }
