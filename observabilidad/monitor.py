"""
observabilidad/monitor.py — CU-O11 «Monitorear uptime y latencia» (OP7), tarea del DAG.

Mide de forma REAL la disponibilidad (uptime) y la latencia de los servicios del
pipeline (StarRocks, ClickHouse, PocketBase), las persiste en `Fact_Disponibilidad`
por región (Dim_Mercado) y evalúa los SLO. Ante un incumplimiento emite una señal
al bus de `alertas` (CU-O13) y registra el incidente con duración y región (RF-706).

Responsabilidad: **medir, registrar y señalar** — NO remedia (RN-805).

Capas (RN-803/RT-01): las MEDICIONES van a `Fact_Disponibilidad` en StarRocks (el
dashboard de disponibilidad las lee agregadas de ClickHouse en el ciclo siguiente).
El historial de INCIDENTES y la señal a alertas son operacionales (PocketBase).

Diseño:
  - Funciones puras (`consolidar`, `filas_disponibilidad`, `evaluar_slo`,
    `incidentes_de`) → se prueban sin Docker.
  - Sondas (`probar_servicios`) y persistencia inyectables.
  - Idempotente: reemplaza las filas del período medido (DELETE id_tiempo + INSERT);
    el historial sintético de meses previos (seed fuera del DAG) se conserva.

Ejecución (tarea del DAG, tras el gate de calidad del DW):
    docker exec vinanalytics-runner python -m observabilidad.monitor
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── SLO / umbrales (RN-801) ───────────────────────────────────────────────────
UPTIME_SLO_PCT   = 99.9    # uptime > 99.9 % mensual
LATENCIA_SLO_MS  = 200.0   # latencia < 200 ms promedio
N_MUESTRAS       = 3       # sondas por servicio en la ventana de muestreo

# Servicios monitoreados del pipeline (RNF-701: todos los servicios + API).
SERVICIOS = ("starrocks", "clickhouse", "pocketbase")


# ══════════════════════════════════════════════════════════════════════════════
# Sondas reales (latencia + arriba/abajo) — inyectables para pruebas
# ══════════════════════════════════════════════════════════════════════════════
def _probar_starrocks() -> tuple[bool, float]:
    import mysql.connector
    from config import (STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
                        STARROCKS_USER, STARROCKS_PASS)
    t0 = time.perf_counter()
    try:
        c = mysql.connector.connect(host=STARROCKS_HOST, port=STARROCKS_PORT,
                                    database=STARROCKS_DB, user=STARROCKS_USER,
                                    password=STARROCKS_PASS, connection_timeout=5)
        cur = c.cursor(); cur.execute("SELECT 1"); cur.fetchall(); cur.close(); c.close()
        return True, (time.perf_counter() - t0) * 1000.0
    except Exception:
        return False, (time.perf_counter() - t0) * 1000.0


def _probar_clickhouse() -> tuple[bool, float]:
    from config import (CLICKHOUSE_HOST, CLICKHOUSE_PORT, CLICKHOUSE_USER,
                        CLICKHOUSE_PASS)
    t0 = time.perf_counter()
    try:
        import clickhouse_connect
        c = clickhouse_connect.get_client(host=CLICKHOUSE_HOST, port=CLICKHOUSE_PORT,
                                          username=CLICKHOUSE_USER, password=CLICKHOUSE_PASS,
                                          connect_timeout=5)
        c.query("SELECT 1"); c.close()
        return True, (time.perf_counter() - t0) * 1000.0
    except Exception:
        return False, (time.perf_counter() - t0) * 1000.0


def _probar_pocketbase() -> tuple[bool, float]:
    import requests
    from config import POCKETBASE_URL
    t0 = time.perf_counter()
    try:
        r = requests.get(f"{POCKETBASE_URL.rstrip('/')}/api/health", timeout=5)
        return r.status_code == 200, (time.perf_counter() - t0) * 1000.0
    except Exception:
        return False, (time.perf_counter() - t0) * 1000.0


_SONDAS = {"starrocks": _probar_starrocks, "clickhouse": _probar_clickhouse,
           "pocketbase": _probar_pocketbase}


def probar_servicios(servicios=SERVICIOS, muestras: int = N_MUESTRAS, sondas=None) -> list[dict]:
    """Sondea cada servicio `muestras` veces y devuelve una medición por servicio:
    {servicio, intentos, exitosos, latencias[]}. `sondas` es inyectable en pruebas."""
    sondas = sondas or _SONDAS
    mediciones = []
    for nombre in servicios:
        fn = sondas.get(nombre)
        if fn is None:
            continue
        exitosos, latencias = 0, []
        for _ in range(max(1, muestras)):
            ok, ms = fn()
            if ok:
                exitosos += 1
                latencias.append(round(ms, 2))
        mediciones.append({"servicio": nombre, "intentos": max(1, muestras),
                           "exitosos": exitosos, "latencias": latencias})
    return mediciones


# ══════════════════════════════════════════════════════════════════════════════
# Consolidación (funciones PURAS · RF-702) — uptime = operativo/total × 100
# ══════════════════════════════════════════════════════════════════════════════
def consolidar(mediciones: list[dict]) -> dict:
    """RF-702: uptime global = Σexitosos/Σintentos × 100; latencia = promedio de las
    sondas exitosas; incidentes = nº de servicios con alguna sonda caída."""
    intentos = sum(m["intentos"] for m in mediciones) or 1
    exitosos = sum(m["exitosos"] for m in mediciones)
    latencias = [l for m in mediciones for l in m["latencias"]]
    caidos = [m["servicio"] for m in mediciones if m["exitosos"] < m["intentos"]]
    uptime = round(exitosos / intentos * 100.0, 3)
    latencia = round(sum(latencias) / len(latencias), 2) if latencias else 0.0
    return {"uptime": uptime, "latencia_ms": latencia,
            "incidentes": len(caidos), "caidos": caidos,
            "servicios": len(mediciones)}


def filas_disponibilidad(consolidado: dict, regiones: list[tuple[int, str]],
                         id_tiempo: int) -> list[tuple]:
    """RF-703: una fila de `fact_disponibilidad` por región (Dim_Mercado) con la
    medición real. La infra es centralizada y sirve a todas las regiones, así que
    la métrica medida se atribuye a cada región (no se fabrica varianza sintética).
    `id_disponibilidad` es determinista (id_tiempo*1000+id_mercado) → idempotente."""
    filas = []
    for id_mercado, _pais in regiones:
        filas.append((
            id_tiempo * 1000 + int(id_mercado),   # id_disponibilidad determinista
            id_tiempo,
            int(id_mercado),
            float(consolidado["uptime"]),
            float(consolidado["latencia_ms"]),
            int(consolidado["incidentes"]),
            0,                                     # despliegues (no medidos aquí)
            0.0,                                   # time_to_market_dias
            0.0,                                   # costo_cloud
        ))
    return filas


# ══════════════════════════════════════════════════════════════════════════════
# Evaluación de SLO (RF-704 / RN-802) → señales por región
# ══════════════════════════════════════════════════════════════════════════════
def evaluar_slo(consolidado: dict, regiones: list[tuple[int, str]], id_tiempo: int,
                uptime_slo: float = UPTIME_SLO_PCT,
                latencia_slo: float = LATENCIA_SLO_MS) -> list[dict]:
    """RF-704: estado del SLO y señales a `alertas` por región incumplida.
    uptime < SLO → señal `uptime` (critical); latencia > SLO → señal `latencia`."""
    senales = []
    up, lat = consolidado["uptime"], consolidado["latencia_ms"]
    for id_mercado, pais in regiones:
        if up < uptime_slo:
            senales.append({
                "tipo": "uptime", "severidad": "critical",
                "clave": f"slo:uptime:{id_mercado}:{id_tiempo}",
                "entidad": pais, "valor": up, "umbral": uptime_slo,
                "id_tiempo": id_tiempo,
                "causa": f"Uptime {up:.3f}% < SLO {uptime_slo}% en {pais}",
                "payload": {"region": pais, "id_mercado": id_mercado,
                            "caidos": consolidado["caidos"]},
            })
        if lat > latencia_slo:
            senales.append({
                "tipo": "latencia", "severidad": "warning",
                "clave": f"slo:latencia:{id_mercado}:{id_tiempo}",
                "entidad": pais, "valor": lat, "umbral": latencia_slo,
                "id_tiempo": id_tiempo,
                "causa": f"Latencia {lat:.0f} ms > SLO {latencia_slo:.0f} ms en {pais}",
                "payload": {"region": pais, "id_mercado": id_mercado},
            })
    return senales


def incidentes_de(mediciones: list[dict], id_tiempo: int,
                  region: str = "multi-región") -> list[dict]:
    """RF-706: un incidente por servicio caído, con duración estimada y región.
    La duración se estima desde las sondas fallidas (proporción de la ventana)."""
    incidentes = []
    ahora = datetime.now().isoformat(timespec="seconds")
    for m in mediciones:
        fallidos = m["intentos"] - m["exitosos"]
        if fallidos <= 0:
            continue
        # ventana nominal de 30 min/run → duración ≈ proporción caída de la ventana
        duracion_min = round(30.0 * fallidos / m["intentos"], 1)
        incidentes.append({
            "clave": f"inc:{m['servicio']}:{id_tiempo}",
            "servicio": m["servicio"], "region": region,
            "severidad": "critical" if m["exitosos"] == 0 else "warning",
            "causa": ("servicio caído" if m["exitosos"] == 0
                      else "degradación parcial del servicio"),
            "estado": "ABIERTO" if m["exitosos"] == 0 else "RECUPERADO",
            "uptime": round(m["exitosos"] / m["intentos"] * 100.0, 3),
            "latencia_ms": round(sum(m["latencias"]) / len(m["latencias"]), 2)
                            if m["latencias"] else 0.0,
            "duracion_min": duracion_min, "id_tiempo": id_tiempo,
            "inicio": ahora, "fin": "" if m["exitosos"] == 0 else ahora,
        })
    return incidentes


# ══════════════════════════════════════════════════════════════════════════════
# Lecturas / persistencia (inyectables) — StarRocks (DW) + PocketBase (operacional)
# ══════════════════════════════════════════════════════════════════════════════
def _conn_sr():
    import mysql.connector
    from config import (STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
                        STARROCKS_USER, STARROCKS_PASS)
    return mysql.connector.connect(host=STARROCKS_HOST, port=STARROCKS_PORT,
                                   database=STARROCKS_DB, user=STARROCKS_USER,
                                   password=STARROCKS_PASS, connection_timeout=20)


def leer_regiones(conn_factory=None) -> tuple[int | None, list[tuple[int, str]]]:
    """Devuelve (id_tiempo_más_reciente, [(id_mercado, pais), ...]) desde StarRocks."""
    conn = (conn_factory or _conn_sr)()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(id_tiempo) FROM dim_tiempo")
        row = cur.fetchone()
        id_tiempo = int(row[0]) if row and row[0] is not None else None
        cur.execute("SELECT id_mercado, pais FROM dim_mercado ORDER BY id_mercado")
        regiones = [(int(r[0]), r[1]) for r in cur.fetchall()]
        cur.close()
        return id_tiempo, regiones
    finally:
        conn.close()


_COLS_DISP = ["id_disponibilidad", "id_tiempo", "id_mercado", "uptime",
              "latencia_ms", "incidentes", "despliegues", "time_to_market_dias",
              "costo_cloud"]


def persistir_disponibilidad(filas: list[tuple], id_tiempo: int,
                             conn_factory=None) -> int:
    """RF-703/RN-803: persiste las mediciones en `fact_disponibilidad` (StarRocks).
    Idempotente: reemplaza SOLO el período medido (DELETE id_tiempo + INSERT); el
    historial de meses previos se conserva."""
    if not filas:
        return 0
    conn = (conn_factory or _conn_sr)()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM fact_disponibilidad WHERE id_tiempo = %s", (id_tiempo,))
        placeholders = ", ".join(["%s"] * len(_COLS_DISP))
        cur.executemany(
            f"INSERT INTO fact_disponibilidad ({', '.join(_COLS_DISP)}) "
            f"VALUES ({placeholders})", filas)
        conn.commit()
        cur.close()
        return len(filas)
    finally:
        conn.close()


def registrar_incidentes(incidentes: list[dict], client=None) -> int:
    """RF-706: registra el historial de incidentes en PocketBase (upsert por clave)."""
    if not incidentes:
        return 0
    from pb_client import get_client
    client = client or get_client()
    n = 0
    for inc in incidentes:
        existente = client.find_one("incidentes", clave=inc["clave"])
        if existente:
            client.update("incidentes", existente["id"], inc)
        else:
            client.create("incidentes", inc)
        n += 1
    return n


def emitir_senales(senales: list[dict], client=None) -> int:
    """RF-704/RN-802: emite cada señal de SLO incumplido al bus de `alertas`."""
    import models_alertas as ma
    n = 0
    for s in senales:
        ma.emitir_senal(origen="observabilidad", tipo=s["tipo"], clave=s["clave"],
                        causa=s["causa"], severidad=s["severidad"],
                        entidad=s["entidad"], valor=s["valor"], umbral=s["umbral"],
                        id_tiempo=s["id_tiempo"], payload=s.get("payload"),
                        client=client)
        n += 1
    return n


# ══════════════════════════════════════════════════════════════════════════════
# Orquestación de la tarea
# ══════════════════════════════════════════════════════════════════════════════
def monitorear(*, mediciones=None, regiones=None, id_tiempo=None,
               conn_factory=None, client=None, persistir=True) -> dict:
    """Flujo: medir → consolidar → persistir disponibilidad → registrar incidentes
    → evaluar SLO → emitir señales. Todo inyectable para pruebas sin Docker."""
    if mediciones is None:
        mediciones = probar_servicios()
    if id_tiempo is None or regiones is None:
        _idt, _reg = leer_regiones(conn_factory)
        id_tiempo = id_tiempo if id_tiempo is not None else _idt
        regiones = regiones if regiones is not None else _reg
    if id_tiempo is None or not regiones:
        return {"ok": False, "motivo": "Sin Dim_Tiempo/Dim_Mercado en el DW."}

    consolidado = consolidar(mediciones)
    filas = filas_disponibilidad(consolidado, regiones, id_tiempo)
    incidentes = incidentes_de(mediciones, id_tiempo)
    senales = evaluar_slo(consolidado, regiones, id_tiempo)

    persistidas = inc_reg = sen_emit = 0
    if persistir:
        persistidas = persistir_disponibilidad(filas, id_tiempo, conn_factory)
        inc_reg = registrar_incidentes(incidentes, client)
        sen_emit = emitir_senales(senales, client)

    estado_slo = "INCUMPLIDO" if senales else "EN_CUMPLIMIENTO"
    return {"ok": True, "id_tiempo": id_tiempo, "regiones": len(regiones),
            "consolidado": consolidado, "estado_slo": estado_slo,
            "filas_persistidas": persistidas, "incidentes": inc_reg,
            "incidentes_detalle": incidentes, "senales_emitidas": sen_emit,
            "senales_detalle": senales}


def main() -> int:
    res = monitorear()
    print("\n" + "=" * 56)
    print("OBSERVABILIDAD — uptime y latencia (CU-O11)")
    print("=" * 56)
    if not res.get("ok"):
        print(f"  [WARN] {res.get('motivo')}")
        return 0
    c = res["consolidado"]
    print(f"  Período (Dim_Tiempo):   {res['id_tiempo']}  ·  regiones: {res['regiones']}")
    print(f"  Uptime medido:          {c['uptime']:.3f}%  (SLO > {UPTIME_SLO_PCT}%)")
    print(f"  Latencia promedio:      {c['latencia_ms']:.1f} ms (SLO < {LATENCIA_SLO_MS:.0f} ms)")
    print(f"  Servicios caídos:       {c['caidos'] or '—'}")
    print(f"  Fact_Disponibilidad:    {res['filas_persistidas']} filas (idempotente)")
    print(f"  Incidentes registrados: {res['incidentes']}")
    print(f"  Estado SLO:             {res['estado_slo']}  →  señales: {res['senales_emitidas']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
