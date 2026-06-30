"""
models_customer_success.py — Lógica de negocio de CU-O14 «Registrar onboarding y
ticket de soporte» (OP10 · paquete `customer-success`).

Persistencia 100 % operacional en PocketBase (RNF-1001, RT-01): `onboarding`,
`tickets` y `acciones_retencion`. NO se escribe al DW ni a ClickHouse: no se
saltan capas. El uso/adopción (CU-O15) se consulta aparte, AGREGADO en ClickHouse
(serving.uso_por_cliente, RN-1102); aquí solo vive el seguimiento operacional.

Patrón pb_client de CU-O08/CU-O13/CU-O16: el cliente PocketBase se inyecta por
parámetro para poder probar las reglas SIN Docker (FakePB en memoria).

Reglas implementadas:
  - Regla del enunciado: un onboarding/ticket se asocia a una CUENTA EXISTENTE
    (colección `clientes` de CU-O08); una cuenta inexistente se rechaza.
  - RN-1101  Ciclo de vida del ticket; transiciones inválidas se rechazan.
  - RN-1104  Onboarding registrado para toda cuenta nueva (idempotente: 1 por cuenta).
  - RN-1103  Una alerta de churn (OP9) prioriza y vincula una acción de retención.
  - RF-1003  Cálculo de tiempos de atención (primera respuesta / resolución).
  - RF-1004  Captura de NPS por cuenta (0..10).
  - RF-1007  Reporte de adopción/soporte por cuenta (parte operacional).
"""

from __future__ import annotations

import json
from datetime import datetime

from pb_client import PBClient, get_client

COL_CLIENTES   = "clientes"
COL_ONBOARDING = "onboarding"
COL_TICKETS    = "tickets"
COL_RETENCION  = "acciones_retencion"
COL_ALERTAS    = "alertas"

# ── Onboarding: estados (spec §9) y pasos por defecto ─────────────────────────
ONB_PENDIENTE   = "PENDIENTE"
ONB_EN_PROGRESO = "EN_PROGRESO"
ONB_COMPLETADO  = "COMPLETADO"
ONB_ESTANCADO   = "ESTANCADO"

_ONB_TRANSICIONES: dict[str, set[str]] = {
    ONB_PENDIENTE:   {ONB_EN_PROGRESO, ONB_ESTANCADO},
    ONB_EN_PROGRESO: {ONB_COMPLETADO, ONB_ESTANCADO},
    ONB_ESTANCADO:   {ONB_EN_PROGRESO, ONB_COMPLETADO},
    ONB_COMPLETADO:  set(),                       # terminal
}

PASOS_ONBOARDING_DEFAULT = [
    "alta", "configuracion", "primer_dashboard", "capacitacion", "activacion",
]

# ── Ticket: estados (spec §9 · RN-1101) ───────────────────────────────────────
T_ABIERTO    = "ABIERTO"
T_EN_PROCESO = "EN_PROCESO"
T_RESUELTO   = "RESUELTO"
T_CERRADO    = "CERRADO"
T_REABIERTO  = "REABIERTO"

# Ciclo nominal abierto→en_proceso→resuelto→cerrado; reapertura desde resuelto/cerrado.
_TICKET_TRANSICIONES: dict[str, set[str]] = {
    T_ABIERTO:    {T_EN_PROCESO, T_RESUELTO, T_CERRADO},
    T_EN_PROCESO: {T_RESUELTO, T_CERRADO},
    T_RESUELTO:   {T_CERRADO, T_REABIERTO},
    T_CERRADO:    {T_REABIERTO},                  # CERRADO→EN_PROCESO sin reabrir: NO (Esc-1105)
    T_REABIERTO:  {T_EN_PROCESO, T_RESUELTO, T_CERRADO},
}


# ── Errores de negocio (mapean a 4xx en la API) ───────────────────────────────
class CustomerSuccessError(Exception):
    def __init__(self, codigo: str, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


class CuentaInexistente(CustomerSuccessError): ...          # regla del enunciado
class TransicionTicketInvalida(CustomerSuccessError): ...   # RN-1101
class TransicionOnboardingInvalida(CustomerSuccessError): ...
class NpsInvalido(CustomerSuccessError): ...                # RF-1004
class RegistroInexistente(CustomerSuccessError): ...


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cli(client: PBClient | None) -> PBClient:
    return client or get_client()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "").strip())
    except ValueError:
        return None


def _minutos(desde: str | None, hasta: str | None) -> float | None:
    """Minutos entre dos timestamps ISO (RF-1003). None si falta alguno."""
    a, b = _parse(desde), _parse(hasta)
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() / 60.0, 2)


def _cuenta_o_error(client: PBClient, cuenta_id: str) -> dict:
    """La cuenta DEBE existir en `clientes` (regla del enunciado / RN-1104)."""
    cuenta = client.find_one(COL_CLIENTES, id=cuenta_id) if cuenta_id else None
    if cuenta is None:
        raise CuentaInexistente(
            "cuenta_inexistente",
            f"No existe la cuenta {cuenta_id!r}; un onboarding/ticket debe "
            f"asociarse a una cuenta existente.",
            {"cuenta": cuenta_id})
    return cuenta


# ══════════════════════════════════════════════════════════════════════════════
# CU-O14 · Onboarding (RF-1001, RN-1104)
# ══════════════════════════════════════════════════════════════════════════════

def iniciar_onboarding(cuenta_id: str, pasos: list[str] | None = None,
                       responsable: str = "Customer Success",
                       client: PBClient | None = None) -> dict:
    """Registra el onboarding de una cuenta nueva (RF-1001).

    - La cuenta debe existir (regla del enunciado).
    - Idempotente (RN-1104): si la cuenta ya tiene onboarding, lo devuelve sin
      duplicar. Así puede dispararse automáticamente al alta de cuenta (OP5).
    """
    client = _cli(client)
    _cuenta_o_error(client, cuenta_id)

    existente = client.find_one(COL_ONBOARDING, cuenta=cuenta_id)
    if existente:
        return existente

    lista = list(pasos or PASOS_ONBOARDING_DEFAULT)
    ahora = _now()
    return client.create(COL_ONBOARDING, {
        "cuenta": cuenta_id,
        "estado": ONB_PENDIENTE,
        "paso": lista[0] if lista else "",
        "pasos_completados": 0,
        "pasos_totales": len(lista),
        "pasos": json.dumps(lista, ensure_ascii=False),
        "responsable": responsable,
        "notas": "",
        "iniciado_en": ahora,
        "actualizado_en": ahora,
        "completado_en": "",
    })


def avanzar_onboarding(onboarding_id: str, client: PBClient | None = None) -> dict:
    """Avanza un paso del onboarding (RF-1001). Al completar el último paso pasa a
    COMPLETADO; en caso contrario, a EN_PROGRESO con el siguiente paso."""
    client = _cli(client)
    onb = client.find_one(COL_ONBOARDING, id=onboarding_id)
    if onb is None:
        raise RegistroInexistente("onboarding_inexistente",
                                  f"No existe el onboarding {onboarding_id}.")
    if onb.get("estado") == ONB_COMPLETADO:
        return onb

    try:
        lista = json.loads(onb.get("pasos") or "[]")
    except (ValueError, TypeError):
        lista = []
    total = int(onb.get("pasos_totales") or len(lista) or 1)
    completados = min(int(onb.get("pasos_completados") or 0) + 1, total)
    ahora = _now()

    cambios = {"pasos_completados": completados, "actualizado_en": ahora}
    if completados >= total:
        cambios["estado"] = ONB_COMPLETADO
        cambios["paso"] = lista[-1] if lista else onb.get("paso", "")
        cambios["completado_en"] = ahora
    else:
        cambios["estado"] = ONB_EN_PROGRESO
        cambios["paso"] = lista[completados] if completados < len(lista) else onb.get("paso", "")
    return client.update(COL_ONBOARDING, onboarding_id, cambios)


def cambiar_estado_onboarding(onboarding_id: str, nuevo_estado: str,
                              client: PBClient | None = None) -> dict:
    """Transición explícita de estado del onboarding (p.ej. EN_PROGRESO→ESTANCADO)."""
    client = _cli(client)
    nuevo_estado = (nuevo_estado or "").upper()
    onb = client.find_one(COL_ONBOARDING, id=onboarding_id)
    if onb is None:
        raise RegistroInexistente("onboarding_inexistente",
                                  f"No existe el onboarding {onboarding_id}.")
    actual = onb.get("estado")
    if nuevo_estado not in _ONB_TRANSICIONES.get(actual, set()):
        raise TransicionOnboardingInvalida(
            "transicion_invalida",
            f"Transición de onboarding no permitida: {actual} → {nuevo_estado}.",
            {"estado_actual": actual,
             "permitidas": sorted(_ONB_TRANSICIONES.get(actual, set()))})
    cambios = {"estado": nuevo_estado, "actualizado_en": _now()}
    if nuevo_estado == ONB_COMPLETADO:
        cambios["completado_en"] = _now()
        cambios["pasos_completados"] = int(onb.get("pasos_totales") or 0)
    return client.update(COL_ONBOARDING, onboarding_id, cambios)


# ══════════════════════════════════════════════════════════════════════════════
# CU-O14 · Tickets de soporte (RF-1002, RF-1003, RN-1101)
# ══════════════════════════════════════════════════════════════════════════════

def abrir_ticket(cuenta_id: str, asunto: str, *, categoria: str = "consulta",
                 prioridad: str = "media", responsable: str = "Customer Success",
                 usuario: str = "cs", ahora: str | None = None,
                 client: PBClient | None = None) -> dict:
    """Abre un ticket clasificado y asociado a una cuenta existente (RF-1002).
    `ahora` permite fijar el instante de apertura (pruebas de tiempos)."""
    client = _cli(client)
    _cuenta_o_error(client, cuenta_id)
    if not str(asunto or "").strip():
        raise CustomerSuccessError("asunto_requerido", "El asunto es obligatorio.")

    momento = ahora or _now()
    return client.create(COL_TICKETS, {
        "cuenta": cuenta_id,
        "asunto": str(asunto).strip(),
        "categoria": categoria,
        "prioridad": prioridad,
        "estado": T_ABIERTO,
        "responsable": responsable,
        "usuario": usuario,
        "nps": -1,
        "satisfaccion": "",
        "abierto_en": momento,
        "primera_respuesta_en": "",
        "resuelto_en": "",
        "cerrado_en": "",
        "reabierto_en": "",
        "tiempo_primera_respuesta_min": None,
        "tiempo_resolucion_min": None,
    })


def transicionar_ticket(ticket_id: str, nuevo_estado: str, *,
                        ahora: str | None = None,
                        client: PBClient | None = None) -> dict:
    """Mueve el ticket por su ciclo de vida (RN-1101) y calcula tiempos (RF-1003).
    Transiciones inválidas se rechazan (Esc-1105). `ahora` fija el instante."""
    client = _cli(client)
    nuevo_estado = (nuevo_estado or "").upper()
    t = client.find_one(COL_TICKETS, id=ticket_id)
    if t is None:
        raise RegistroInexistente("ticket_inexistente",
                                  f"No existe el ticket {ticket_id}.")

    actual = t.get("estado")
    if nuevo_estado not in _TICKET_TRANSICIONES.get(actual, set()):
        raise TransicionTicketInvalida(
            "transicion_invalida",
            f"Transición de ticket no permitida: {actual} → {nuevo_estado}.",
            {"estado_actual": actual,
             "permitidas": sorted(_TICKET_TRANSICIONES.get(actual, set()))})

    momento = ahora or _now()
    abierto_en = t.get("abierto_en")
    cambios: dict = {"estado": nuevo_estado}

    if nuevo_estado == T_EN_PROCESO and not t.get("primera_respuesta_en"):
        cambios["primera_respuesta_en"] = momento
        cambios["tiempo_primera_respuesta_min"] = _minutos(abierto_en, momento)

    elif nuevo_estado == T_RESUELTO:
        # Si se resuelve sin pasar por EN_PROCESO, la primera respuesta es ahora.
        if not t.get("primera_respuesta_en"):
            cambios["primera_respuesta_en"] = momento
            cambios["tiempo_primera_respuesta_min"] = _minutos(abierto_en, momento)
        cambios["resuelto_en"] = momento
        cambios["tiempo_resolucion_min"] = _minutos(abierto_en, momento)

    elif nuevo_estado == T_CERRADO:
        cambios["cerrado_en"] = momento
        if not t.get("resuelto_en"):
            cambios["resuelto_en"] = momento
            if t.get("tiempo_resolucion_min") in (None, ""):
                cambios["tiempo_resolucion_min"] = _minutos(abierto_en, momento)

    elif nuevo_estado == T_REABIERTO:
        cambios["reabierto_en"] = momento
        cambios["resuelto_en"] = ""
        cambios["cerrado_en"] = ""

    return client.update(COL_TICKETS, ticket_id, cambios)


def registrar_satisfaccion(ticket_id: str, nps: int, comentario: str = "",
                           client: PBClient | None = None) -> dict:
    """Captura la señal de satisfacción/NPS del ticket (RF-1004). NPS válido 0..10."""
    client = _cli(client)
    try:
        valor = int(nps)
    except (TypeError, ValueError):
        raise NpsInvalido("nps_invalido", "El NPS debe ser un entero entre 0 y 10.")
    if not 0 <= valor <= 10:
        raise NpsInvalido("nps_invalido", "El NPS debe estar entre 0 y 10.",
                          {"nps": valor})

    t = client.find_one(COL_TICKETS, id=ticket_id)
    if t is None:
        raise RegistroInexistente("ticket_inexistente",
                                  f"No existe el ticket {ticket_id}.")
    return client.update(COL_TICKETS, ticket_id, {
        "nps": valor,
        "satisfaccion": _clasificar_nps(valor),
        "notas": comentario or t.get("notas", ""),
    })


def _clasificar_nps(valor: int) -> str:
    if valor >= 9:
        return "promotor"
    if valor >= 7:
        return "pasivo"
    return "detractor"


# ══════════════════════════════════════════════════════════════════════════════
# CU-O14/CU-O15 · Vínculo con alertas de churn → acción de retención (RF-1006/RN-1103)
# ══════════════════════════════════════════════════════════════════════════════

def _churn_vivo(client: PBClient, cuenta_ref: str) -> dict | None:
    """Alerta de churn ABIERTA/RECONOCIDA cuya entidad es la cuenta dada (OP9)."""
    import models_alertas as ma
    if not cuenta_ref:
        return None
    for a in client.find(COL_ALERTAS, tipo="churn", entidad=cuenta_ref):
        if a.get("estado") in ma.ESTADOS_VIVOS:
            return a
    return None


def evaluar_retencion(cuenta_ref: str, client: PBClient | None = None) -> dict:
    """Lectura SIN efectos (RF-1006): ¿hay alerta de churn viva sobre la cuenta?
    Devuelve la prioridad de retención para acompañar la consulta de uso (CU-O15)."""
    client = _cli(client)
    alerta = _churn_vivo(client, cuenta_ref)
    if alerta is None:
        return {"prioridad": "normal", "en_riesgo": False, "alerta": None}
    return {
        "prioridad": "alta", "en_riesgo": True,
        "alerta": {"id": alerta.get("id"), "severidad": alerta.get("severidad"),
                   "causa": alerta.get("causa"), "estado": alerta.get("estado"),
                   "ocurrencias": alerta.get("ocurrencias")},
    }


def vincular_retencion(cuenta_ref: str, responsable: str = "Customer Success",
                       client: PBClient | None = None) -> dict:
    """RN-1103: una alerta de churn viva PRIORIZA y VINCULA una acción de retención.

    Idempotente por (cuenta, alerta): no apila acciones para la misma alerta. Si no
    hay churn vivo sobre la cuenta, no crea acción y lo informa."""
    client = _cli(client)
    alerta = _churn_vivo(client, cuenta_ref)
    if alerta is None:
        return {"vinculada": False, "prioridad": "normal", "accion": None,
                "motivo": "Sin alerta de churn viva para la cuenta."}

    existente = client.find_one(COL_RETENCION, cuenta=cuenta_ref,
                                alerta=alerta.get("id"))
    if existente:
        return {"vinculada": True, "prioridad": "alta", "accion": existente,
                "alerta": alerta.get("id")}

    ahora = _now()
    accion = client.create(COL_RETENCION, {
        "cuenta": cuenta_ref,
        "alerta": alerta.get("id"),
        "tipo": "churn",
        "severidad": alerta.get("severidad", "critical"),
        "causa": alerta.get("causa", ""),
        "prioridad": "alta",
        "estado": "PENDIENTE",
        "responsable": responsable,
        "creado_en": ahora,
        "actualizado_en": ahora,
    })
    return {"vinculada": True, "prioridad": "alta", "accion": accion,
            "alerta": alerta.get("id")}


# ══════════════════════════════════════════════════════════════════════════════
# RF-1007 · Reporte de adopción/soporte por cuenta (parte operacional)
# ══════════════════════════════════════════════════════════════════════════════

def reporte_soporte(cuenta_id: str, client: PBClient | None = None) -> dict:
    """Métricas operacionales de soporte/onboarding por cuenta (RF-1007, RN-1105).

    Auditable y consumible por reportes (OP11) / BSC de cliente. El uso/adopción
    (sesiones/funciones) NO se calcula aquí: se consulta agregado en ClickHouse
    (CU-O15, serving.uso_por_cliente) para no saltar capas (RN-1102)."""
    client = _cli(client)
    _cuenta_o_error(client, cuenta_id)

    onb = client.find_one(COL_ONBOARDING, cuenta=cuenta_id)
    tickets = client.find(COL_TICKETS, cuenta=cuenta_id)

    por_estado: dict[str, int] = {}
    tr_resol: list[float] = []
    tr_resp: list[float] = []
    nps_vals: list[int] = []
    for t in tickets:
        por_estado[t.get("estado")] = por_estado.get(t.get("estado"), 0) + 1
        if t.get("tiempo_resolucion_min") not in (None, ""):
            tr_resol.append(float(t["tiempo_resolucion_min"]))
        if t.get("tiempo_primera_respuesta_min") not in (None, ""):
            tr_resp.append(float(t["tiempo_primera_respuesta_min"]))
        if t.get("nps") not in (None, "", -1):
            nps_vals.append(int(t["nps"]))

    abiertos = sum(por_estado.get(e, 0) for e in (T_ABIERTO, T_EN_PROCESO, T_REABIERTO))
    prom = lambda xs: round(sum(xs) / len(xs), 2) if xs else None

    return {
        "cuenta": cuenta_id,
        "onboarding": {
            "estado": (onb or {}).get("estado"),
            "pasos_completados": (onb or {}).get("pasos_completados"),
            "pasos_totales": (onb or {}).get("pasos_totales"),
        } if onb else None,
        "tickets": {
            "total": len(tickets),
            "abiertos": abiertos,
            "por_estado": por_estado,
            "tiempo_resolucion_prom_min": prom(tr_resol),
            "primera_respuesta_prom_min": prom(tr_resp),
            "nps_respuestas": len(nps_vals),
            "nps_promedio": prom([float(v) for v in nps_vals]),
        },
        "retencion": evaluar_retencion(cuenta_id, client),
    }
