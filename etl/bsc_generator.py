"""
Generador de datos sintéticos para el Balanced Scorecard corporativo.

Puebla las tablas Fact-Dim de negocio (db/bsc_setup.py) con 24 meses de series
temporales coherentes con las metas del documento de Desarrollo Empresarial:

  · Crecimiento de MRR ≈ 30 % anual          · Churn < 4 % mensual
  · % ingresos vía API → ~33 %               · NPS ≥ 50
  · Conversión del embudo → ~8.5 %           · Adopción ≥ 70 %
  · Uptime > 99.9 %                          · Time-to-market < 1 día
  · CAC internacional a la baja              · LTV/CAC ≥ 3

Es idempotente: TRUNCATE + INSERT en cada tabla. Determinista vía SEED.
Las dimensiones vitivinícolas (fact_resenas, dim_pais…) no se tocan.

────────────────────────────────────────────────────────────────────────────
SEED SINTÉTICO / DEMO — FUERA DEL DAG DE PRODUCCIÓN.
Excepción documentada al Principio VI (transformación declarativa en DBT) y al
orden de capas (Princ. Arq.): este generador inserta datos de demostración
DIRECTAMENTE en StarRocks, sin pasar por Parquet/staging ni por DBT. Su único
fin es poblar el Balanced Scorecard para la demo cuando no hay datos reales.
NO debe invocarse desde el DAG de Airflow del pipeline productivo
(ingesta → calidad → ETL/DBT → calidad → agregaciones). Para datos reales, el
flujo declarativo vive en dbt_vinanalytics/ + quality/ (Fases 1–N).
────────────────────────────────────────────────────────────────────────────
"""

import random
import sys
from datetime import date
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS,
)

SEED       = 42
N_MESES    = 24
END_YEAR   = 2026
END_MONTH  = 6

MESES_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# ── Catálogos de dimensiones ─────────────────────────────────────────────────
MERCADOS = [
    (1, "Argentina",       "América Latina"),
    (2, "Chile",           "América Latina"),
    (3, "México",          "América Latina"),
    (4, "Brasil",          "América Latina"),
    (5, "Perú",            "América Latina"),
    (6, "Colombia",        "América Latina"),
    (7, "España",          "Europa"),
    (8, "Italia",          "Europa"),
    (9, "Francia",         "Europa"),
    (10, "Portugal",       "Europa"),
    (11, "Estados Unidos", "Norteamérica"),
    (12, "Australia",      "Oceanía"),
]
PLANES = [
    (1, "Trial",        0.00),
    (2, "Básico",       99.00),
    (3, "Profesional",  499.00),
    (4, "Enterprise",   1990.00),
]
CANALES = [
    (1, "Orgánico"), (2, "Pago"), (3, "Referido"), (4, "Marketplace"), (5, "Partner"),
]
PARTNERS = [
    (1, "Mercado Vino LATAM",  "Marketplace"),
    (2, "WineHub API",         "Integrador"),
    (3, "VinoConnect",         "Integrador"),
    (4, "Distribuidora Global","Distribuidor"),
    (5, "BodegaLink",          "Marketplace"),
    (6, "SommelierMarket",     "Marketplace"),
]
ESTADOS = [
    (1, "Prueba"), (2, "Activa"), (3, "En pausa"), (4, "Cancelada"),
]
TIPOS    = ["Distribuidora", "Importadora", "Retail especializado",
            "Bodega exportadora", "Consultora"]
TAMANOS  = ["Pequeña", "Mediana", "Grande"]
SEG_MAP  = {"Pequeña": "SMB", "Mediana": "Mid-Market", "Grande": "Enterprise"}

# Prefijos para nombres de cuentas B2B
ACCT_PRE = ["Vinos", "Distribuidora", "Importadora", "Grupo", "Comercial",
            "Bodegas", "Cava", "Selección", "Enoteca", "Casa"]
ACCT_SUF = ["del Valle", "Andina", "Premium", "Global", "Ibérica", "Austral",
            "Reserva", "Continental", "Boutique", "Internacional", "Sur",
            "Pacífico", "Mediterránea", "Real", "Noble"]


def _conn():
    return mysql.connector.connect(
        host=STARROCKS_HOST, port=STARROCKS_PORT, database=STARROCKS_DB,
        user=STARROCKS_USER, password=STARROCKS_PASS, connection_timeout=20,
    )


def _months():
    """Lista cronológica de (anio, mes) de los últimos N_MESES."""
    out, y, m = [], END_YEAR, END_MONTH
    for _ in range(N_MESES):
        out.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(out))


def _truncate_insert(cur, conn, table, cols, rows, batch=2000):
    cur.execute(f"TRUNCATE TABLE `{table}`")
    conn.commit()
    if not rows:
        return 0
    ph   = ", ".join(["%s"] * len(cols))
    cl   = ", ".join(f"`{c}`" for c in cols)
    sql  = f"INSERT INTO `{table}` ({cl}) VALUES ({ph})"
    for i in range(0, len(rows), batch):
        cur.executemany(sql, rows[i:i + batch])
        conn.commit()
    return len(rows)


def generate_bsc() -> dict:
    random.seed(SEED)
    print("Conectando a StarRocks (BSC) ...")
    conn = _conn()
    cur  = conn.cursor()
    print("  [OK] Conexión establecida\n")

    months   = _months()
    tiempo_ids = [y * 100 + m for (y, m) in months]

    # ── DIMENSIONES base ─────────────────────────────────────────────────────
    dim_tiempo = [
        (y * 100 + m, date(y, m, 1).isoformat(), y, (m - 1) // 3 + 1, m,
         MESES_ES[m], f"{y}-{m:02d}")
        for (y, m) in months
    ]
    _truncate_insert(cur, conn, "dim_tiempo",
                     ["id_tiempo", "fecha", "anio", "trimestre", "mes",
                      "mes_nombre", "periodo"], dim_tiempo)
    _truncate_insert(cur, conn, "dim_mercado",
                     ["id_mercado", "pais", "region_geo"], MERCADOS)
    _truncate_insert(cur, conn, "dim_plan",
                     ["id_plan", "nombre", "precio_mensual"], PLANES)
    _truncate_insert(cur, conn, "dim_canal_adquisicion",
                     ["id_canal", "nombre"], CANALES)
    _truncate_insert(cur, conn, "dim_partner_api",
                     ["id_partner", "nombre", "tipo"], PARTNERS)
    _truncate_insert(cur, conn, "dim_estado_suscripcion",
                     ["id_estado", "nombre"], ESTADOS)
    print("  [OK] Dimensiones base cargadas")

    plan_price = {p[0]: p[2] for p in PLANES}

    # ── SIMULACIÓN de clientes / suscripciones mes a mes ─────────────────────
    clientes: dict[int, dict] = {}      # id -> atributos + estado vivo
    next_cid = 1

    def nuevo_cliente(alta_iso, idx):
        nonlocal next_cid
        cid = next_cid
        next_cid += 1
        tam = random.choices(TAMANOS, weights=[5, 3, 2])[0]
        # planes de entrada según tamaño
        if tam == "Grande":
            plan = random.choices([3, 4], weights=[4, 6])[0]
        elif tam == "Mediana":
            plan = random.choices([2, 3, 4], weights=[3, 6, 1])[0]
        else:
            plan = random.choices([1, 2, 3], weights=[3, 6, 1])[0]
        clientes[cid] = {
            "nombre":   f"{random.choice(ACCT_PRE)} {random.choice(ACCT_SUF)}",
            "tipo":     random.choice(TIPOS),
            "tamano":   tam,
            "segmento": SEG_MAP[tam],
            "mercado":  random.choices([m[0] for m in MERCADOS],
                                       weights=[12, 9, 11, 8, 6, 6, 9, 8, 7, 5, 7, 4])[0],
            "canal":    random.choices([c[0] for c in CANALES],
                                       weights=[3, 4, 2, 4, 3])[0],
            "plan":     plan,
            "alta":     alta_iso,
            "ltv":      0.0,
            "vivo":     True,
            "meses_activo": 0,
        }
        return cid

    # Cartera inicial: clientes dados de alta en los 12 meses previos a la ventana
    y0, m0 = months[0]
    for _ in range(95):
        back = random.randint(1, 12)
        ay, am = y0, m0
        for _ in range(back):
            am -= 1
            if am == 0:
                am, ay = 12, ay - 1
        nuevo_cliente(date(ay, am, 1).isoformat(), 0)

    fact_susc, fact_ret, fact_uso = [], [], []
    sid = uid = rid = 0
    mrr_by_month: dict[int, float] = {}
    nuevos_por_mt: dict[tuple[int, int], dict[int, int]] = {}  # (tid,mercado)->{canal:n}

    for idx, (y, m) in enumerate(months):
        tid = y * 100 + m
        progreso = idx / (N_MESES - 1)          # 0..1

        # 1) Tamaño de cartera al inicio del mes
        N = sum(1 for c in clientes.values() if c["vivo"])
        churn_rate = 0.042 - 0.0005 * idx            # 4.2 % → 3.05 %

        # Altas del mes: reponen el churn + ~2 % de crecimiento neto
        # (mantiene el MRR creciendo ~30 % anual, no de forma explosiva)
        n_altas = max(1, round(N * (churn_rate + 0.013) + random.uniform(-1, 1)))
        for _ in range(n_altas):
            cid = nuevo_cliente(date(y, m, 1).isoformat(), idx)
            mk = clientes[cid]["mercado"]; cn = clientes[cid]["canal"]
            nuevos_por_mt.setdefault((tid, mk), {}).setdefault(cn, 0)
            nuevos_por_mt[(tid, mk)][cn] += 1
        nuevos_este_mes = {cid for cid, c in clientes.items()
                           if c["vivo"] and c["alta"] == date(y, m, 1).isoformat()}

        # 2) Churn del mes (tasa decreciente: retención mejora)
        activos = [cid for cid, c in clientes.items() if c["vivo"]]
        churned = set()
        for cid in activos:
            if cid in nuevos_este_mes:
                continue
            if random.random() < churn_rate:
                churned.add(cid)

        # 3) Upgrades del mes (~4 % suben de plan → empuja MRR)
        for cid in activos:
            if cid in churned:
                continue
            if clientes[cid]["plan"] < 4 and random.random() < 0.02:
                clientes[cid]["plan"] += 1

        # 4) Emitir hechos por cliente
        mrr_total = 0.0
        for cid in activos:
            c = clientes[cid]
            if cid in churned:
                sid += 1; rid += 1
                fact_susc.append((sid, tid, cid, c["plan"], 4, 0.0,
                                  0, 0, 0, 1))
                fact_ret.append((rid, tid, cid, 0, 1, round(c["ltv"], 2),
                                 round(random.uniform(0.55, 0.95), 2)))
                c["vivo"] = False
                continue

            precio = plan_price[c["plan"]]
            # pequeño descuento comercial aleatorio
            mrr = round(precio * random.uniform(0.92, 1.0), 2)
            mrr_total += mrr
            es_nuevo = 1 if cid in nuevos_este_mes else 0
            estado   = 1 if c["plan"] == 1 else 2   # Trial=Prueba, resto Activa
            c["meses_activo"] += 1
            c["ltv"] += mrr * 0.78                   # margen bruto acumulado
            riesgo = max(0.02, round(random.uniform(0.03, 0.35) * (1 - progreso * 0.4), 2))

            sid += 1; rid += 1; uid += 1
            fact_susc.append((sid, tid, cid, c["plan"], estado, mrr,
                              es_nuevo, 0, 0, 0))
            fact_ret.append((rid, tid, cid, 1, 0, round(c["ltv"], 2), riesgo))

            # Uso de plataforma
            u_tot = random.randint(3, 45)
            adopt = min(0.95, random.uniform(0.55, 0.70) + progreso * 0.10)
            u_act = max(1, round(u_tot * adopt))
            sesiones = u_act * random.randint(4, 18)
            dash     = sesiones * random.randint(1, 4)
            funcs    = random.randint(3, 14)
            # NPS: responde ~35 % de cuentas; distribución mejora con el tiempo
            if random.random() < 0.60:
                prom_w = 30 + progreso * 30     # promotores ↑ con el tiempo
                det_w  = 24 - progreso * 14     # detractores ↓
                nps = random.choices(
                    [10, 9, 8, 7, 6, 5, 4, 3],
                    weights=[prom_w * .6, prom_w * .4, 14, 12,
                             det_w * .4, det_w * .3, det_w * .2, det_w * .1])[0]
            else:
                nps = -1
            fact_uso.append((uid, tid, cid, sesiones, dash, funcs,
                             u_act, u_tot, nps))

        mrr_by_month[tid] = round(mrr_total, 2)

    # dim_cliente (cartera final completa)
    dim_cli = [
        (cid, c["nombre"], c["tipo"], c["tamano"], c["segmento"],
         c["mercado"], c["plan"], c["canal"], c["alta"])
        for cid, c in clientes.items()
    ]
    _truncate_insert(cur, conn, "dim_cliente",
                     ["id_cliente", "nombre", "tipo", "tamano", "segmento",
                      "id_mercado", "id_plan", "id_canal", "fecha_alta"], dim_cli)

    n_sus = _truncate_insert(cur, conn, "fact_suscripcion",
        ["id_suscripcion", "id_tiempo", "id_cliente", "id_plan", "id_estado",
         "mrr", "es_nuevo", "es_upgrade", "es_downgrade", "es_churn"], fact_susc)
    n_ret = _truncate_insert(cur, conn, "fact_retencion",
        ["id_retencion", "id_tiempo", "id_cliente", "activo", "cancelacion",
         "ltv", "riesgo_churn"], fact_ret)
    n_uso = _truncate_insert(cur, conn, "fact_uso_plataforma",
        ["id_uso", "id_tiempo", "id_cliente", "sesiones", "dashboards_vistos",
         "funciones_usadas", "usuarios_activos", "usuarios_totales", "nps_score"],
        fact_uso)
    print(f"  [OK] Suscripción/Retención/Uso: {n_sus}/{n_ret}/{n_uso} filas")

    # ── DIM + FACT de campañas y conversión ──────────────────────────────────
    dim_camp, fact_camp = [], []
    cid_camp = 0
    camp_keys = []   # (id_campana, mercado, canal)
    for (mk, pais, _reg) in MERCADOS:
        for cn in (2, 4, 3):   # Pago, Marketplace, Referido
            cid_camp += 1
            cname = f"{dict((c[0], c[1]) for c in CANALES)[cn]} · {pais}"
            dim_camp.append((cid_camp, cname, mk, cn,
                             random.choice(list(SEG_MAP.values()))))
            camp_keys.append((cid_camp, mk, cn))
    _truncate_insert(cur, conn, "dim_campana",
                     ["id_campana", "nombre", "id_mercado", "id_canal", "segmento"],
                     dim_camp)

    fc_id = 0
    for idx, (y, m) in enumerate(months):
        tid = y * 100 + m
        progreso = idx / (N_MESES - 1)
        for (camp, mk, cn) in camp_keys:
            base = random.randint(40_000, 160_000)
            impres = int(base * (1 + progreso * 0.8))
            ctr    = random.uniform(0.012, 0.03)
            clics  = int(impres * ctr)
            leads  = int(clics * random.uniform(0.08, 0.16))
            gasto  = round(impres / 1000 * random.uniform(7, 16), 2)
            fc_id += 1
            fact_camp.append((fc_id, tid, camp, impres, clics, gasto, leads))
    _truncate_insert(cur, conn, "fact_campana",
        ["id_fact_campana", "id_tiempo", "id_campana", "impresiones",
         "clics", "gasto", "leads"], fact_camp)

    # Conversión por mercado × canal (CAC a la baja, conversión al alza)
    fact_conv = []
    cv_id = 0
    for idx, (y, m) in enumerate(months):
        tid = y * 100 + m
        progreso = idx / (N_MESES - 1)
        conv_rate = 0.062 + progreso * 0.033        # 6.2 % → 9.5 %
        cac_base  = 1500 - progreso * 320           # 1500 → 1180
        for (mk, pais, reg) in MERCADOS:
            for (cn, _cn_name) in CANALES:
                nuevos = nuevos_por_mt.get((tid, mk), {}).get(cn, 0)
                # leads coherentes con las conversiones objetivo del mes
                base_leads = random.randint(20, 70)
                leads = base_leads + nuevos * random.randint(8, 14)
                conv  = max(nuevos, int(leads * conv_rate))
                oport = int(leads * random.uniform(0.30, 0.45))
                cac   = round(cac_base * random.uniform(0.8, 1.2), 2)
                cv_id += 1
                fact_conv.append((cv_id, tid, mk, cn, leads, oport, conv, cac))
    _truncate_insert(cur, conn, "fact_conversion",
        ["id_conversion", "id_tiempo", "id_mercado", "id_canal",
         "leads", "oportunidades", "conversiones", "cac"], fact_conv)
    print(f"  [OK] Campañas/Conversión: {len(fact_camp)}/{len(fact_conv)} filas")

    # ── API: consumo + integraciones (ingresos vía API → ~33 % del total) ────
    fact_api, fact_int = [], []
    api_id = int_id = 0
    for idx, (y, m) in enumerate(months):
        tid = y * 100 + m
        progreso = idx / (N_MESES - 1)
        mrr_total = mrr_by_month.get(tid, 0.0)
        # share objetivo de ingresos API: 13 % → 35 %
        api_share = 0.13 + progreso * 0.22
        api_rev_total = mrr_total * api_share / max(1e-6, (1 - api_share))
        pesos = [random.uniform(0.6, 1.6) for _ in PARTNERS]
        sp = sum(pesos)
        for k, (pid, _nm, _tp) in enumerate(PARTNERS):
            ingreso = round(api_rev_total * pesos[k] / sp, 2)
            llamadas = int((50_000 + progreso * 400_000) * pesos[k] / sp
                           * random.uniform(0.8, 1.2))
            lat = round(random.uniform(60, 140) - progreso * 20, 2)
            err = int(llamadas * random.uniform(0.001, 0.015))
            api_id += 1
            fact_api.append((api_id, tid, pid, llamadas, lat, err, ingreso))
            conexiones = int((8 + progreso * 60) * pesos[k] / sp * 6)
            int_id += 1
            fact_int.append((int_id, tid, pid, max(1, conexiones), ingreso))
    _truncate_insert(cur, conn, "fact_consumo_api",
        ["id_consumo", "id_tiempo", "id_partner", "llamadas",
         "latencia_ms", "errores", "ingreso_api"], fact_api)
    _truncate_insert(cur, conn, "fact_integracion_partner",
        ["id_integracion", "id_tiempo", "id_partner",
         "conexiones_activas", "ingreso_api"], fact_int)
    print(f"  [OK] API consumo/integraciones: {len(fact_api)}/{len(fact_int)} filas")

    # ── Disponibilidad e infraestructura (uptime > 99.9 %, TTM < 1 día) ──────
    fact_disp = []
    d_id = 0
    for idx, (y, m) in enumerate(months):
        tid = y * 100 + m
        progreso = idx / (N_MESES - 1)
        for (mk, pais, reg) in MERCADOS:
            up = round(min(99.99, 99.86 + progreso * 0.08 + random.uniform(-0.03, 0.03)), 3)
            lat_base = 230 if reg == "América Latina" else (150 if reg == "Europa" else 180)
            lat = round(lat_base - progreso * 45 + random.uniform(-15, 15), 2)
            inc = random.choices([0, 1, 2, 3], weights=[60, 25, 10, 5])[0]
            desp = random.randint(2, 9)
            ttm  = round(1.45 - progreso * 0.75 + random.uniform(-0.1, 0.1), 2)
            costo = round(random.uniform(180, 520) * (1 + progreso * 0.3), 2)
            d_id += 1
            fact_disp.append((d_id, tid, mk, up, max(40, lat), inc, desp,
                              max(0.4, ttm), costo))
    _truncate_insert(cur, conn, "fact_disponibilidad",
        ["id_disponibilidad", "id_tiempo", "id_mercado", "uptime",
         "latencia_ms", "incidentes", "despliegues", "time_to_market_dias",
         "costo_cloud"], fact_disp)
    print(f"  [OK] Disponibilidad: {len(fact_disp)} filas")

    # ── Aprendizaje y crecimiento (perspectiva 4 del BSC) ────────────────────
    fact_apr = []
    a_id = 0
    for idx, (y, m) in enumerate(months):
        tid = y * 100 + m
        progreso = idx / (N_MESES - 1)
        # horas de capacitación (run-rate anual por persona; meta 32/año)
        horas = round(30 + progreso * 8 + random.uniform(-1, 1), 2)
        ddd   = round(min(88, 68 + progreso * 18 + random.uniform(-2, 2)), 2)
        tecno = min(6, 1 + int(progreso * 5))
        rota  = round(max(6.0, 12 - progreso * 4 + random.uniform(-1, 1)), 2)
        ml    = min(7, 2 + int(progreso * 5))
        a_id += 1
        fact_apr.append((a_id, tid, horas, ddd, tecno, rota, ml))
    _truncate_insert(cur, conn, "fact_aprendizaje",
        ["id_aprendizaje", "id_tiempo", "horas_capacitacion",
         "decisiones_data_driven", "tecnologias_adoptadas",
         "rotacion_personal", "modelos_ml_produccion"], fact_apr)
    print(f"  [OK] Aprendizaje: {len(fact_apr)} filas")

    cur.close()
    conn.close()

    resumen = {
        "dim_cliente": len(dim_cli), "fact_suscripcion": n_sus,
        "fact_retencion": n_ret, "fact_uso_plataforma": n_uso,
        "fact_campana": len(fact_camp), "fact_conversion": len(fact_conv),
        "fact_consumo_api": len(fact_api), "fact_integracion_partner": len(fact_int),
        "fact_disponibilidad": len(fact_disp), "fact_aprendizaje": len(fact_apr),
    }
    print("\n" + "=" * 50)
    print("GENERACIÓN BSC COMPLETADA")
    print("=" * 50)
    for k, v in resumen.items():
        print(f"  {k:28s} {v:>7,} filas")
    print("=" * 50)
    return resumen


if __name__ == "__main__":
    generate_bsc()
