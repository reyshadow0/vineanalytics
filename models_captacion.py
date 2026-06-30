"""
models_captacion.py — Lógica de negocio de CU-O09 «Ejecutar campaña de captación
automatizada» y CU-O10 «Registrar conversión del embudo» (OP6 · paquete
`captacion-conversion` · Growth & Marketing).

Persistencia 100 % operacional en PocketBase (RNF-603, RT-01): `campanas`,
`eventos_campana`, `leads`, `eventos_conversion`. NO se escribe al DW ni a
ClickHouse: la app no salta capas. El ETL (OP2) proyecta los eventos a
`Fact_Campana`/`Fact_Conversion` (RF-603/RF-605), igual que CU-O08 con
`eventos_suscripcion`→`Fact_Suscripcion`.

Patrón pb_client de CU-O08/CU-O13/CU-O14: el cliente PocketBase se inyecta por
parámetro para probar las reglas SIN Docker (FakePB en memoria).

Reglas implementadas:
  - Regla del enunciado: una campaña/conversión se asocia a un canal y mercado
    EXISTENTES (catálogos `canales_adquisicion`/`mercados`).
  - RN-701  Toda campaña pertenece a un canal y un mercado.
  - RN-702  Deduplicación de leads (un prospecto = un solo lead).
  - RN-703  Atribución ÚNICA de la conversión a una campaña/canal de origen.
  - RF-602/RNF-601  Ejecución automatizada y reanudable de la campaña.
  - RF-603  Registro de impresiones/clics/gasto/leads en eventos_campana.
  - Regla del enunciado (anti-doble-conteo): la MISMA conversión de un lead en la
    MISMA etapa no se cuenta dos veces (idempotencia por (lead, etapa)).
  - RF-606  Atribución first-touch a la campaña/canal que captó el lead.
  - RF-607/RN-704  Insumos de CAC y tasa de conversión (fórmulas canónicas).
  - RF-608/RN-705  Una conversión a `cliente` origina alta en `suscripciones`
    (OP5) sin duplicar la cuenta.
  - RN-706  Caída de conversión bajo umbral emite señal al bus de alertas (OP9).

Modelo de atribución (RNF-602, único y documentado): **first-touch**. Cada lead se
deduplica por su clave natural (RN-702) y se asocia, en su PRIMER registro, a
exactamente UNA campaña/canal de origen (la que lo captó). Toda conversión de ese
lead se atribuye a esa campaña/canal, sin importar cuántas campañas reclamen luego
al prospecto (Esc-604: doble atribución resuelta a una sola).
"""

from __future__ import annotations

from datetime import datetime

from pb_client import PBClient, get_client

COL_CANALES   = "canales_adquisicion"
COL_MERCADOS  = "mercados"
COL_CAMPANAS  = "campanas"
COL_EV_CAMP   = "eventos_campana"
COL_LEADS     = "leads"
COL_EV_CONV   = "eventos_conversion"
COL_CLIENTES  = "clientes"

# ── Estados de campaña (spec §9) ──────────────────────────────────────────────
C_BORRADOR     = "BORRADOR"
C_PROGRAMADA   = "PROGRAMADA"
C_EN_EJECUCION = "EN_EJECUCION"
C_PAUSADA      = "PAUSADA"
C_FINALIZADA   = "FINALIZADA"

# BORRADOR→PROGRAMADA→EN_EJECUCION→FINALIZADA; PAUSADA↔EN_EJECUCION (reanudable).
_CAMP_TRANSICIONES: dict[str, set[str]] = {
    C_BORRADOR:     {C_PROGRAMADA},
    C_PROGRAMADA:   {C_EN_EJECUCION, C_PAUSADA, C_FINALIZADA},
    C_EN_EJECUCION: {C_PAUSADA, C_FINALIZADA},
    C_PAUSADA:      {C_EN_EJECUCION, C_FINALIZADA},     # reanudable (RNF-601)
    C_FINALIZADA:   set(),                               # terminal
}
# Estados desde los que una corrida de ejecución es válida.
_EJECUTABLES = {C_PROGRAMADA, C_EN_EJECUCION, C_PAUSADA}

# ── Etapas del embudo (spec §9) ───────────────────────────────────────────────
E_LEAD       = "LEAD"
E_OPORTUNIDAD = "OPORTUNIDAD"
E_CLIENTE    = "CLIENTE"
E_PERDIDO    = "PERDIDO"
_ETAPAS = {E_LEAD, E_OPORTUNIDAD, E_CLIENTE, E_PERDIDO}
_ORDEN_ETAPA = {E_LEAD: 0, E_OPORTUNIDAD: 1, E_CLIENTE: 2}  # PERDIDO no avanza


# ── Errores de negocio (mapean a 4xx en la API) ───────────────────────────────
class CaptacionError(Exception):
    def __init__(self, codigo: str, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje
        self.detalle = detalle or {}


class CanalInexistente(CaptacionError): ...          # RN-701 / enunciado
class MercadoInexistente(CaptacionError): ...        # RN-701
class CampanaInexistente(CaptacionError): ...
class LeadInexistente(CaptacionError): ...
class TransicionCampanaInvalida(CaptacionError): ...  # spec §9
class EtapaInvalida(CaptacionError): ...              # spec §9


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


def _id_tiempo(ahora: str | None = None) -> int:
    """Período Dim_Tiempo en formato YYYYMM (igual que el resto del DW)."""
    dt = _parse(ahora) or datetime.now()
    return dt.year * 100 + dt.month


def _resolver_canal(client: PBClient, valor: str) -> dict:
    """Resuelve y EXIGE un canal existente (RN-701). Acepta codigo, nombre o id_canal."""
    v = str(valor or "").strip()
    if not v:
        raise CanalInexistente("canal_requerido", "El canal de adquisición es obligatorio.")
    canal = (client.find_one(COL_CANALES, codigo=v.lower())
             or client.find_one(COL_CANALES, nombre=v))
    if canal is None and v.isdigit():
        canal = client.find_one(COL_CANALES, id_canal=int(v))
    if canal is None:
        raise CanalInexistente(
            "canal_inexistente",
            f"El canal de adquisición '{valor}' no existe en el catálogo.",
            {"canal": valor})
    return canal


def _resolver_mercado(client: PBClient, valor: str) -> dict:
    """Resuelve y EXIGE un mercado existente (RN-701). Acepta codigo/pais o id_mercado."""
    v = str(valor or "").strip()
    if not v:
        raise MercadoInexistente("mercado_requerido", "El mercado/región es obligatorio.")
    mercado = (client.find_one(COL_MERCADOS, codigo=v)
               or client.find_one(COL_MERCADOS, pais=v))
    if mercado is None and v.isdigit():
        mercado = client.find_one(COL_MERCADOS, id_mercado=int(v))
    if mercado is None:
        raise MercadoInexistente(
            "mercado_inexistente",
            f"El mercado '{valor}' no existe en el catálogo.",
            {"mercado": valor})
    return mercado


def _metricas_por_defecto(presupuesto: float) -> dict:
    """Métricas deterministas a partir del presupuesto (RF-603). Sin azar → la
    ejecución automatizada es idempotente/reproducible (RNF-601)."""
    gasto = round(float(presupuesto or 0), 2)
    impresiones = int(gasto / 10.0 * 1000)   # CPM = 10 USD
    clics = int(impresiones * 0.02)          # CTR  = 2 %
    leads = int(clics * 0.12)                # lead rate = 12 %
    return {"impresiones": impresiones, "clics": clics, "gasto": gasto, "leads": leads}


# ══════════════════════════════════════════════════════════════════════════════
# CU-O09 · Configuración y ejecución automatizada de campañas
# ══════════════════════════════════════════════════════════════════════════════

def crear_campana(nombre: str, canal: str, mercado: str, *, segmento: str = "",
                  presupuesto: float = 0.0, responsable: str = "Growth & Marketing",
                  programacion: str = "", client: PBClient | None = None) -> dict:
    """RF-601/RN-701 — define una campaña por canal y región. Exige canal y mercado
    EXISTENTES (regla del enunciado). Nace en BORRADOR (o PROGRAMADA si trae horario)."""
    client = _cli(client)
    if not str(nombre or "").strip():
        raise CaptacionError("nombre_requerido", "El nombre de la campaña es obligatorio.")
    can = _resolver_canal(client, canal)
    mer = _resolver_mercado(client, mercado)

    ahora = _now()
    estado = C_PROGRAMADA if str(programacion or "").strip() else C_BORRADOR
    return client.create(COL_CAMPANAS, {
        "nombre": str(nombre).strip(),
        "canal": can["codigo"],
        "mercado": mer["codigo"],
        "segmento": segmento,
        "presupuesto": round(float(presupuesto or 0), 2),
        "programacion": str(programacion or ""),
        "estado": estado,
        "ejecuciones": 0,
        "responsable": responsable,
        "creado_en": ahora,
        "actualizado_en": ahora,
    })


def programar_campana(campana_id: str, programacion: str,
                      client: PBClient | None = None) -> dict:
    """RF-601/RF-602 — programa una campaña BORRADOR para una fecha/hora (reanudable)."""
    client = _cli(client)
    camp = _campana_o_error(client, campana_id)
    _exigir_transicion(camp, C_PROGRAMADA)
    return client.update(COL_CAMPANAS, campana_id, {
        "estado": C_PROGRAMADA,
        "programacion": str(programacion or ""),
        "actualizado_en": _now(),
    })


def ejecutar_campana(campana_id: str, *, metricas: dict | None = None,
                     periodo: int | None = None, ahora: str | None = None,
                     client: PBClient | None = None) -> dict:
    """RF-602/RF-603 — ejecuta una corrida de la campaña y registra sus métricas.

    Idempotente y reanudable (RNF-601): las métricas del período se guardan en UNA
    fila de `eventos_campana` por (campaña, id_tiempo). Re-ejecutar el mismo período
    UPSERTA esa fila (no la duplica → anti-doble-conteo); cada corrida solo refresca
    el contador de auditoría `corrida`. La campaña pasa a EN_EJECUCION (desde
    PROGRAMADA o reanudando desde PAUSADA)."""
    client = _cli(client)
    camp = _campana_o_error(client, campana_id)
    if camp.get("estado") not in _EJECUTABLES:
        raise TransicionCampanaInvalida(
            "campana_no_ejecutable",
            f"La campaña en estado {camp.get('estado')} no puede ejecutarse; "
            f"debe estar PROGRAMADA/EN_EJECUCION/PAUSADA.",
            {"estado_actual": camp.get("estado")})

    id_tiempo = int(periodo) if periodo is not None else _id_tiempo(ahora)
    met = dict(metricas) if metricas else _metricas_por_defecto(camp.get("presupuesto", 0))
    clave = f"camp:{campana_id}:{id_tiempo}"
    momento = ahora or _now()

    existente = client.find_one(COL_EV_CAMP, clave=clave)
    nuevo = existente is None
    corrida = (int(existente.get("corrida") or 1) + 1) if existente else 1
    datos = {
        "campana": campana_id,
        "canal": camp.get("canal"),
        "mercado": camp.get("mercado"),
        "id_tiempo": id_tiempo,
        "clave": clave,
        "corrida": corrida,
        "impresiones": int(met.get("impresiones", 0)),
        "clics": int(met.get("clics", 0)),
        "gasto": round(float(met.get("gasto", 0)), 2),
        "leads": int(met.get("leads", 0)),
        "fecha": momento,
    }
    if existente:
        evento = client.update(COL_EV_CAMP, existente["id"], datos)
    else:
        evento = client.create(COL_EV_CAMP, datos)

    cambios = {"estado": C_EN_EJECUCION, "actualizado_en": momento}
    if nuevo:   # solo una corrida NUEVA suma a `ejecuciones` (idempotencia)
        cambios["ejecuciones"] = int(camp.get("ejecuciones") or 0) + 1
    camp = client.update(COL_CAMPANAS, campana_id, cambios)
    return {"campana": camp, "evento": evento, "nuevo": nuevo, "corrida": corrida}


def cambiar_estado_campana(campana_id: str, nuevo_estado: str,
                           client: PBClient | None = None) -> dict:
    """Transición explícita del ciclo de vida (pausar/reanudar/finalizar, spec §9)."""
    client = _cli(client)
    nuevo_estado = (nuevo_estado or "").upper()
    camp = _campana_o_error(client, campana_id)
    _exigir_transicion(camp, nuevo_estado)
    return client.update(COL_CAMPANAS, campana_id, {
        "estado": nuevo_estado, "actualizado_en": _now(),
    })


def ejecutar_pendientes(ahora: str | None = None,
                        client: PBClient | None = None) -> dict:
    """RF-602/RNF-601 — ejecuta automáticamente las campañas PROGRAMADAS cuya
    programación ya venció. Punto de entrada del orquestador (Airflow). Idempotente:
    re-ejecutar el mismo período no duplica métricas (upsert por período)."""
    client = _cli(client)
    momento = ahora or _now()
    corte = _parse(momento)
    ejecutadas: list[dict] = []
    for camp in client.find(COL_CAMPANAS, estado=C_PROGRAMADA):
        prog = _parse(camp.get("programacion"))
        if prog is not None and corte is not None and prog > corte:
            continue   # aún no llega su horario
        res = ejecutar_campana(camp["id"], ahora=momento, client=client)
        ejecutadas.append({"campana": camp["id"], "nombre": camp.get("nombre"),
                           "evento": res["evento"]["id"], "corrida": res["corrida"]})
    return {"ejecutadas": len(ejecutadas), "detalle": ejecutadas}


# ── Helpers de campaña ────────────────────────────────────────────────────────
def _campana_o_error(client: PBClient, campana_id: str) -> dict:
    camp = client.find_one(COL_CAMPANAS, id=campana_id) if campana_id else None
    if camp is None:
        raise CampanaInexistente("campana_inexistente",
                                 f"No existe la campaña {campana_id!r}.",
                                 {"campana": campana_id})
    return camp


def _exigir_transicion(camp: dict, nuevo_estado: str) -> None:
    actual = camp.get("estado")
    if nuevo_estado not in _CAMP_TRANSICIONES.get(actual, set()):
        raise TransicionCampanaInvalida(
            "transicion_invalida",
            f"Transición de campaña no permitida: {actual} → {nuevo_estado}.",
            {"estado_actual": actual,
             "permitidas": sorted(_CAMP_TRANSICIONES.get(actual, set()))})


# ══════════════════════════════════════════════════════════════════════════════
# CU-O09/CU-O10 · Leads (dedup RN-702) + atribución first-touch (RN-703)
# ══════════════════════════════════════════════════════════════════════════════

def registrar_lead(clave: str, campana_id: str, *, prospecto: str = "",
                   ahora: str | None = None, client: PBClient | None = None) -> dict:
    """RF-604/RN-702 — registra un lead deduplicado por su clave natural.

    Atribución first-touch (RN-703): el lead queda asociado a la campaña/canal que
    lo CAPTÓ. Si el mismo prospecto (misma `clave`) llega otra vez —aunque sea por
    OTRA campaña—, NO se cuenta de nuevo ni se re-atribuye (Esc-602/Esc-604):
    devuelve el lead existente con su atribución original."""
    client = _cli(client)
    clave = str(clave or "").strip()
    if not clave:
        raise CaptacionError("clave_lead_requerida",
                             "La clave natural del prospecto es obligatoria (dedup).")
    camp = _campana_o_error(client, campana_id)

    existente = client.find_one(COL_LEADS, clave=clave)
    if existente:   # RN-702/Esc-604: dedup + atribución inmutable
        return {"lead": existente, "nuevo": False, "duplicado": True,
                "atribucion": {"campana": existente.get("campana_origen"),
                               "canal": existente.get("canal_origen")}}

    momento = ahora or _now()
    lead = client.create(COL_LEADS, {
        "clave": clave,
        "prospecto": prospecto or clave,
        "campana_origen": campana_id,
        "canal_origen": camp.get("canal"),
        "mercado": camp.get("mercado"),
        "etapa": E_LEAD,
        "id_tiempo": _id_tiempo(momento),
        "creado_en": momento,
        "actualizado_en": momento,
    })
    return {"lead": lead, "nuevo": True, "duplicado": False,
            "atribucion": {"campana": campana_id, "canal": camp.get("canal")}}


# ══════════════════════════════════════════════════════════════════════════════
# CU-O10 · Registro de conversión con atribución y anti-doble-conteo
# ══════════════════════════════════════════════════════════════════════════════

def registrar_conversion(lead_ref: str, etapa: str, *, fuente: str = "embudo",
                         resultado: str = "en_progreso", ahora: str | None = None,
                         entregar_alta: bool = True,
                         client: PBClient | None = None) -> dict:
    """RF-605/RF-606 — registra una conversión del embudo atribuida a su campaña/canal.

    Anti-doble-conteo (regla del enunciado): la conversión se identifica por
    (lead, etapa). Registrar DOS veces la misma conversión de un lead en la misma
    etapa NO la cuenta dos veces: devuelve la existente con `contada=False`.

    Atribución (RN-703): SIEMPRE a la campaña/canal de ORIGEN del lead (first-touch),
    no a quien registre la conversión. Si la etapa es `cliente`, se entrega el alta a
    `suscripciones` (OP5) sin duplicar la cuenta (RF-608/RN-705)."""
    client = _cli(client)
    etapa = (etapa or "").upper()
    if etapa not in _ETAPAS:
        raise EtapaInvalida("etapa_invalida",
                            f"Etapa de embudo inválida: {etapa!r}.",
                            {"permitidas": sorted(_ETAPAS)})

    lead = (client.find_one(COL_LEADS, id=lead_ref)
            or client.find_one(COL_LEADS, clave=str(lead_ref)))
    if lead is None:
        raise LeadInexistente("lead_inexistente",
                              f"No existe el lead {lead_ref!r}; toda conversión "
                              f"parte de un lead captado.", {"lead": lead_ref})

    clave = f"conv:{lead['id']}:{etapa}"
    existente = client.find_one(COL_EV_CONV, clave=clave)
    if existente:   # anti-doble-conteo: misma conversión del lead en la misma etapa
        return {"conversion": existente, "contada": False,
                "atribucion": {"campana": existente.get("campana_atribuida"),
                               "canal": existente.get("canal")},
                "alta": (client.find_one(COL_CLIENTES, id=existente.get("cliente"))
                         if existente.get("cliente") else None)}

    momento = ahora or _now()
    campana_atribuida = lead.get("campana_origen")   # RN-703: atribución única
    canal = lead.get("canal_origen")
    mercado = lead.get("mercado")

    evento = client.create(COL_EV_CONV, {
        "lead": lead["id"],
        "clave": clave,
        "etapa": etapa,
        "fuente": fuente,
        "resultado": resultado,
        "campana_atribuida": campana_atribuida,
        "canal": canal,
        "mercado": mercado,
        "cliente": "",
        "id_tiempo": _id_tiempo(momento),
        "fecha": momento,
    })

    # Avanza la etapa del lead si la conversión progresa en el embudo.
    _avanzar_lead(client, lead, etapa, momento)

    # RF-608/RN-705: conversión a `cliente` → alta en suscripciones sin duplicar.
    alta = None
    if etapa == E_CLIENTE and entregar_alta:
        alta = _entregar_alta(client, lead, evento)

    return {"conversion": evento, "contada": True,
            "atribucion": {"campana": campana_atribuida, "canal": canal},
            "alta": alta}


def _avanzar_lead(client: PBClient, lead: dict, etapa: str, momento: str) -> None:
    cambios = {"actualizado_en": momento}
    if etapa == E_PERDIDO:
        cambios["etapa"] = E_PERDIDO
    elif _ORDEN_ETAPA.get(etapa, -1) > _ORDEN_ETAPA.get(lead.get("etapa"), -1):
        cambios["etapa"] = etapa
    client.update(COL_LEADS, lead["id"], cambios)


def _entregar_alta(client: PBClient, lead: dict, evento: dict) -> dict | None:
    """RF-608/RN-705 — entrega la conversión a `suscripciones` (OP5): crea la cuenta
    si no existe; si ya existe (dedup RN-601), la reutiliza SIN duplicar (Esc-605)."""
    import models_clientes as mc
    razon = lead.get("prospecto") or lead.get("clave")
    try:
        cli = mc.crear_cliente({
            "razon_social": razon,
            "id_fiscal": lead.get("clave"),
            "mercado": lead.get("mercado", ""),
            "segmento": "",
        }, client=client)
    except mc.ClienteDuplicado as e:   # cuenta ya existe → reusar, no duplicar
        cli = client.find_one(COL_CLIENTES, id=e.detalle.get("id_existente"))
    except Exception as exc:           # OP5 no disponible: no romper la conversión
        print(f"[WARN] Hand-off de conversión→alta (RF-608) no completado: {exc}")
        return None
    if cli:
        client.update(COL_EV_CONV, evento["id"], {"cliente": cli["id"]})
    return cli


# ══════════════════════════════════════════════════════════════════════════════
# CU-O10 · Insumos de CAC y tasa de conversión (RF-607/RN-704)
# ══════════════════════════════════════════════════════════════════════════════

def indicadores_captacion(periodo: int | None = None,
                          client: PBClient | None = None) -> dict:
    """RF-607/RN-704 — insumos canónicos consumibles por el DW/reportes:

        CAC                = gasto_marketing / nuevos_clientes
        tasa_conversion(%) = conversiones / leads × 100

    `nuevos_clientes`/`conversiones` = conversiones en etapa `cliente` (únicas por
    lead, ya anti-duplicadas). `leads` = leads deduplicados (RN-702)."""
    client = _cli(client)
    f_camp = {"id_tiempo": int(periodo)} if periodo is not None else {}
    eventos_camp = client.find(COL_EV_CAMP, **f_camp)
    gasto = round(sum(float(e.get("gasto") or 0) for e in eventos_camp), 2)

    leads = client.find(COL_LEADS, **({"id_tiempo": int(periodo)} if periodo is not None else {}))
    n_leads = len(leads)

    conv = client.find(COL_EV_CONV, **({"id_tiempo": int(periodo), "etapa": E_CLIENTE}
                                       if periodo is not None else {"etapa": E_CLIENTE}))
    nuevos = len(conv)

    tasa = round(nuevos / n_leads * 100, 2) if n_leads else 0.0
    cac = round(gasto / nuevos, 2) if nuevos else 0.0
    return {
        "periodo": periodo,
        "gasto_marketing": gasto,
        "leads": n_leads,
        "conversiones": nuevos,
        "nuevos_clientes": nuevos,
        "tasa_conversion": tasa,
        "cac": cac,
    }


# ══════════════════════════════════════════════════════════════════════════════
# RN-706 · Caída de conversión → señal al bus de alertas (CU-O13/OP9)
# ══════════════════════════════════════════════════════════════════════════════

def evaluar_caida_conversion(periodo: int | None = None, *, umbral: float = 5.0,
                             mercado: str = "global",
                             client: PBClient | None = None) -> dict:
    """RN-706 — si la tasa de conversión cae bajo `umbral` (con leads suficientes),
    emite una señal `conversion` al bus (senales_alerta) que `alertas` (OP9) convierte
    en alerta enrutada a Growth & Marketing. Reusa el bus de CU-O13 (no salta capas)."""
    client = _cli(client)
    ind = indicadores_captacion(periodo, client)
    tasa = ind["tasa_conversion"]
    if ind["leads"] > 0 and tasa < umbral:
        import models_alertas as ma
        senal = ma.emitir_senal(
            origen="conversion", tipo="conversion",
            clave=f"conversion:{mercado}:{periodo}",
            causa=f"Tasa de conversión {tasa}% por debajo del umbral {umbral}%.",
            severidad=ma.WARNING, entidad=mercado, valor=tasa, umbral=umbral,
            id_tiempo=periodo, payload={"indicadores": ind}, client=client)
        return {"alerta": True, "senal": senal, "tasa": tasa, "umbral": umbral,
                "indicadores": ind}
    return {"alerta": False, "tasa": tasa, "umbral": umbral, "indicadores": ind}
