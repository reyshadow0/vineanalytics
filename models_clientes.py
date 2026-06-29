"""
models_clientes.py — Lógica de negocio de CU-O08 «Registrar cuenta y suscripción
del cliente» (OP5 · paquete `suscripciones`).

Toda la persistencia es operacional en PocketBase (RN-606, RT-01). Cada cambio
emite un evento a la colección `eventos_suscripcion`, consumible por el ETL para
poblar `Fact_Suscripcion` (RF-506); esta capa NUNCA escribe en StarRocks ni
ClickHouse (no se saltan capas).

Reglas de negocio implementadas:
  - RN-601  Sin cuentas duplicadas (dedup por id_fiscal/email_corp).
  - RN-602  Solo se activa con plan válido + facturación completa.
  - RN-603  El estado vigente gobierna el acceso (acceso_vigente).
  - RN-604  Transiciones de estado válidas; las inválidas se rechazan.
  - RN-605  Cada cambio (alta/upgrade/downgrade/pausa/cancelación) emite evento.
  Regla extra del enunciado: una suscripción debe asociarse a un plan EXISTENTE
  y una cuenta no puede tener DOS suscripciones activas del mismo plan.
"""

from __future__ import annotations

from datetime import date, datetime

from pb_client import PBClient, get_client

# ── Estados y máquina de transiciones (RN-604) ────────────────────────────────
PRUEBA, ACTIVA, EN_PAUSA, CANCELADA = "PRUEBA", "ACTIVA", "EN_PAUSA", "CANCELADA"

_TRANSICIONES: dict[str, set[str]] = {
    PRUEBA:    {ACTIVA, CANCELADA},
    ACTIVA:    {EN_PAUSA, CANCELADA},
    EN_PAUSA:  {ACTIVA, CANCELADA},
    CANCELADA: set(),                 # estado terminal
}

# tipo_evento por estado destino (para Fact_Suscripcion)
_EVENTO_POR_DESTINO = {
    (PRUEBA, ACTIVA): "alta",
    (EN_PAUSA, ACTIVA): "reactivacion",
    (ACTIVA, EN_PAUSA): "pausa",
    (ACTIVA, CANCELADA): "cancelacion",
    (EN_PAUSA, CANCELADA): "cancelacion",
    (PRUEBA, CANCELADA): "cancelacion",
}

_ESTADOS_CON_ACCESO = {ACTIVA, PRUEBA}   # RN-603


# ── Errores de negocio ────────────────────────────────────────────────────────
class ReglaNegocioError(Exception):
    """Violación de una regla de negocio (mapea a 4xx en la API)."""
    def __init__(self, codigo: str, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


class ClienteDuplicado(ReglaNegocioError): ...        # RN-601
class ClienteInexistente(ReglaNegocioError): ...
class PlanInexistente(ReglaNegocioError): ...         # regla 1 del enunciado
class SuscripcionActivaDuplicada(ReglaNegocioError):  # regla 2 del enunciado
    ...
class FacturacionIncompleta(ReglaNegocioError): ...   # RN-602
class TransicionInvalida(ReglaNegocioError): ...      # RN-604


# ── Helpers ───────────────────────────────────────────────────────────────────
def _cli(client: PBClient | None) -> PBClient:
    return client or get_client()


def _hoy() -> str:
    return date.today().isoformat()


def _facturacion_valida(facturacion: dict | None) -> bool:
    """RN-602/RNF-505: completa y sin número de tarjeta en claro."""
    if not facturacion:
        return False
    requeridos = ("titular", "metodo_pago_token")
    if not all(str(facturacion.get(k, "")).strip() for k in requeridos):
        return False
    # Defensa: rechazar si llega un PAN (16 dígitos) en claro.
    bruto = "".join(ch for ch in str(facturacion.get("metodo_pago_token", "")) if ch.isdigit())
    if len(bruto) >= 13:
        return False
    return True


def _mrr(monto: float, periodo: str) -> float:
    return round(monto / 12.0, 2) if periodo == "anual" else round(float(monto), 2)


def _emit_evento(client: PBClient, susc: dict, tipo_evento: str,
                 mrr_delta: float, usuario: str) -> dict:
    """Persiste un evento en PocketBase para que el ETL pueble Fact_Suscripcion."""
    return client.create("eventos_suscripcion", {
        "suscripcion": susc.get("id", ""),
        "cliente": susc["cliente"],
        "plan": susc["plan"],
        "tipo_evento": tipo_evento,
        "monto": float(susc.get("monto", 0)),
        "mrr_delta": round(float(mrr_delta), 2),
        "estado": susc["estado"],
        "usuario": usuario,
        "fecha": datetime.now().isoformat(),
    })


# ── RF-501 · Alta de cuenta de cliente (con dedup RN-601) ─────────────────────
def crear_cliente(datos: dict, client: PBClient | None = None) -> dict:
    client = _cli(client)
    razon = str(datos.get("razon_social", "")).strip()
    if not razon:
        raise ReglaNegocioError("razon_social_requerida",
                                "La razón social es obligatoria.")

    id_fiscal = str(datos.get("id_fiscal", "")).strip()
    email = str(datos.get("email_corp", "")).strip().lower()
    if not id_fiscal and not email:
        raise ReglaNegocioError(
            "identificador_requerido",
            "Se requiere id_fiscal o email_corp para deduplicar la cuenta.")

    # RN-601: rechaza alta duplicada devolviendo el id existente.
    for campo, valor in (("id_fiscal", id_fiscal), ("email_corp", email)):
        if valor:
            existente = client.find_one("clientes", **{campo: valor})
            if existente:
                raise ClienteDuplicado(
                    "cuenta_duplicada",
                    f"Ya existe una cuenta con {campo}={valor}.",
                    {"id_existente": existente["id"], "campo": campo})

    return client.create("clientes", {
        "razon_social": razon,
        "id_fiscal": id_fiscal,
        "email_corp": email,
        "tipo": str(datos.get("tipo", "")),
        "tamano": str(datos.get("tamano", "")),
        "segmento": str(datos.get("segmento", "")),
        "mercado": str(datos.get("mercado", "")),
        "fecha_alta": _hoy(),
    })


# ── RF-502/504 · Alta de suscripción ──────────────────────────────────────────
def crear_suscripcion(cliente_id: str, plan_codigo: str, periodo: str = "mensual",
                      facturacion: dict | None = None, monto: float | None = None,
                      moneda: str = "USD", usuario: str = "admin",
                      client: PBClient | None = None) -> dict:
    client = _cli(client)

    # La cuenta debe existir.
    cliente = client.find_one("clientes", id=cliente_id)
    if cliente is None:
        raise ClienteInexistente("cliente_inexistente",
                                 f"No existe la cuenta {cliente_id}.")

    # Regla 1: el plan debe EXISTIR (rechaza si no).
    plan = client.find_one("planes", codigo=plan_codigo)
    if plan is None:
        raise PlanInexistente("plan_inexistente",
                              f"El plan '{plan_codigo}' no existe.")

    # Regla 2: la cuenta no puede tener DOS suscripciones activas del mismo plan.
    duplicada = client.find_one("suscripciones", cliente=cliente_id,
                                plan=plan_codigo, estado=ACTIVA)
    if duplicada:
        raise SuscripcionActivaDuplicada(
            "suscripcion_activa_duplicada",
            f"La cuenta ya tiene una suscripción ACTIVA al plan '{plan_codigo}'.",
            {"id_existente": duplicada["id"]})

    if monto is None:
        base = float(plan["precio_mensual"])
        monto = round(base * 12, 2) if periodo == "anual" else base

    # RN-602: solo se activa con facturación completa; si no, queda en PRUEBA.
    activable = _facturacion_valida(facturacion)
    estado = ACTIVA if activable else PRUEBA
    token = str((facturacion or {}).get("metodo_pago_token", ""))[-4:] if activable else ""

    susc = client.create("suscripciones", {
        "cliente": cliente_id,
        "plan": plan_codigo,
        "monto": float(monto),
        "moneda": moneda,
        "periodo": periodo,
        "estado": estado,
        "inicio": _hoy(),
        "fin": "",
        "facturacion_ok": activable,
        "metodo_pago": f"****{token}" if token else "",
    })

    # RN-605: el alta emite evento. Si quedó en PRUEBA, mrr_delta = 0.
    tipo = "alta" if estado == ACTIVA else "alta_prueba"
    delta = _mrr(monto, periodo) if estado == ACTIVA else 0.0
    _emit_evento(client, susc, tipo, delta, usuario)
    return susc


# ── RF-505 · Ciclo de vida / máquina de estados (RN-604) ──────────────────────
def cambiar_estado(suscripcion_id: str, nuevo_estado: str, usuario: str = "admin",
                   client: PBClient | None = None) -> dict:
    client = _cli(client)
    nuevo_estado = nuevo_estado.upper()

    susc = client.find_one("suscripciones", id=suscripcion_id)
    if susc is None:
        raise ReglaNegocioError("suscripcion_inexistente",
                                f"No existe la suscripción {suscripcion_id}.")

    actual = susc["estado"]
    if nuevo_estado not in _TRANSICIONES.get(actual, set()):
        raise TransicionInvalida(
            "transicion_invalida",
            f"Transición no permitida: {actual} → {nuevo_estado}.",
            {"estado_actual": actual, "permitidas": sorted(_TRANSICIONES.get(actual, set()))})

    # RN-602: pasar a ACTIVA exige facturación válida.
    if nuevo_estado == ACTIVA and not susc.get("facturacion_ok"):
        raise FacturacionIncompleta(
            "facturacion_incompleta",
            "No se puede activar sin datos de facturación válidos.")

    cambios = {"estado": nuevo_estado}
    if nuevo_estado == CANCELADA:
        cambios["fin"] = _hoy()
    actualizada = client.update("suscripciones", suscripcion_id, cambios)

    # RN-605: emitir evento del cambio.
    tipo = _EVENTO_POR_DESTINO.get((actual, nuevo_estado), "cambio_estado")
    base_mrr = _mrr(float(susc["monto"]), susc["periodo"])
    delta = {ACTIVA: base_mrr, EN_PAUSA: -base_mrr, CANCELADA: -base_mrr}.get(nuevo_estado, 0.0)
    _emit_evento(client, actualizada, tipo, delta, usuario)
    return actualizada


# ── RF-505/RN-605 · Upgrade / downgrade de plan ───────────────────────────────
def cambiar_plan(suscripcion_id: str, nuevo_plan_codigo: str, usuario: str = "admin",
                 client: PBClient | None = None) -> dict:
    client = _cli(client)

    susc = client.find_one("suscripciones", id=suscripcion_id)
    if susc is None:
        raise ReglaNegocioError("suscripcion_inexistente",
                                f"No existe la suscripción {suscripcion_id}.")
    if susc["estado"] == CANCELADA:
        raise TransicionInvalida("suscripcion_cancelada",
                                 "No se puede cambiar el plan de una suscripción cancelada.")

    nuevo_plan = client.find_one("planes", codigo=nuevo_plan_codigo)
    if nuevo_plan is None:
        raise PlanInexistente("plan_inexistente",
                              f"El plan '{nuevo_plan_codigo}' no existe.")
    plan_actual = client.find_one("planes", codigo=susc["plan"])

    # Regla 2 también aplica al cambiar de plan.
    if nuevo_plan_codigo != susc["plan"]:
        dup = client.find_one("suscripciones", cliente=susc["cliente"],
                              plan=nuevo_plan_codigo, estado=ACTIVA)
        if dup:
            raise SuscripcionActivaDuplicada(
                "suscripcion_activa_duplicada",
                f"La cuenta ya tiene una suscripción ACTIVA al plan '{nuevo_plan_codigo}'.",
                {"id_existente": dup["id"]})

    # Captura valores previos ANTES de actualizar (para calcular el delta de MRR).
    periodo = susc["periodo"]
    mrr_anterior = _mrr(float(susc["monto"]), periodo)
    precio_ant = float(plan_actual["precio_mensual"]) if plan_actual else 0.0

    nuevo_monto = round(float(nuevo_plan["precio_mensual"]) *
                        (12 if periodo == "anual" else 1), 2)
    actualizada = client.update("suscripciones", suscripcion_id,
                                {"plan": nuevo_plan_codigo, "monto": nuevo_monto})

    tipo = "upgrade" if float(nuevo_plan["precio_mensual"]) >= precio_ant else "downgrade"
    delta = _mrr(nuevo_monto, periodo) - mrr_anterior
    _emit_evento(client, actualizada, tipo, delta, usuario)
    return actualizada


# ── RF-507/RN-603 · Plan/estado vigente para autorizar acceso ─────────────────
def acceso_vigente(cliente_id: str, client: PBClient | None = None) -> dict:
    client = _cli(client)
    subs = client.find("suscripciones", cliente=cliente_id)
    # Prioriza una suscripción que otorgue acceso (ACTIVA/PRUEBA).
    vigente = next((s for s in subs if s["estado"] in _ESTADOS_CON_ACCESO), None)
    if vigente is None:
        return {"cliente": cliente_id, "plan": None, "estado": None,
                "autorizado": False}
    return {
        "cliente": cliente_id,
        "plan": vigente["plan"],
        "estado": vigente["estado"],
        "autorizado": vigente["estado"] in _ESTADOS_CON_ACCESO,  # RN-603
    }
