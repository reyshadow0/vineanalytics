"""
Motor de Inteligencia / Machine Learning de VinAnalytics Group.

Implementa las técnicas de IA descritas en el documento de Desarrollo Empresarial
(secciones 9.10–9.11), operando sobre el modelo Fact-Dim ya cargado en StarRocks:

  · Predicción de churn (CU-E05, CU-T09, CU-O12)      → scoring ponderado de riesgo
  · Segmentación de clientes RFM (CU-T02)             → Recencia / Frecuencia / Monto
  · Precios dinámicos y demanda (CU-T08, CU-E02)      → regresión + señal de demanda
  · Detección de anomalías (CU-E04, CU-O13)           → z-score sobre series mensuales

Algoritmos transparentes con numpy/pandas (sin dependencias pesadas), lo que los
hace explicables: cada predicción muestra los factores que la originan.
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS,
)


def _conn():
    return mysql.connector.connect(
        host=STARROCKS_HOST, port=STARROCKS_PORT, database=STARROCKS_DB,
        user=STARROCKS_USER, password=STARROCKS_PASS, connection_timeout=20,
    )


def _df(sql: str, params: tuple = ()) -> pd.DataFrame:
    import warnings
    conn = _conn()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # silencia aviso SQLAlchemy de pandas
            return pd.read_sql(sql, conn, params=params or None)
    finally:
        conn.close()


def _latest() -> int | None:
    df = _df("SELECT MAX(id_tiempo) AS m FROM dim_tiempo")
    if df.empty or pd.isna(df.iloc[0]["m"]):
        return None
    return int(df.iloc[0]["m"])


def _meses_entre(alta, ref: date) -> int:
    """Meses transcurridos entre una fecha de alta y la fecha de referencia."""
    if alta is None:
        return 0
    if isinstance(alta, str):
        try:
            alta = date.fromisoformat(alta[:10])
        except ValueError:
            return 0
    return max(0, (ref.year - alta.year) * 12 + (ref.month - alta.month))


# ═════════════════════════════════════════════════════════════════════════════
# 1) PREDICCIÓN DE CHURN  (CU-E05 / CU-T09 / CU-O12)
# ═════════════════════════════════════════════════════════════════════════════

_PLAN_RISK = {"Trial": 0.85, "Básico": 0.45, "Profesional": 0.22, "Enterprise": 0.10}
_PESOS = {  # ponderaciones del modelo (suman 1.0)
    "adopcion": 0.22, "sesiones": 0.15, "nps": 0.13,
    "plan": 0.15, "antiguedad": 0.10, "riesgo_base": 0.25,
}


def predecir_churn() -> dict:
    latest = _latest()
    if latest is None:
        return {"disponible": False}
    ref = date(latest // 100, latest % 100, 1)

    df = _df("""
        SELECT c.id_cliente, c.nombre, c.tipo, c.fecha_alta,
               m.pais, p.nombre AS plan,
               r.riesgo_churn, r.ltv,
               u.usuarios_activos, u.usuarios_totales, u.sesiones, u.nps_score
        FROM fact_retencion r
        JOIN dim_cliente c ON r.id_cliente = c.id_cliente
        JOIN dim_mercado m ON c.id_mercado = m.id_mercado
        JOIN dim_plan    p ON c.id_plan    = p.id_plan
        LEFT JOIN fact_uso_plataforma u
               ON u.id_cliente = r.id_cliente AND u.id_tiempo = r.id_tiempo
        WHERE r.id_tiempo = %s AND r.activo = 1
    """, (latest,))
    if df.empty:
        return {"disponible": False}

    def fila_score(row):
        adopcion = (row["usuarios_activos"] / row["usuarios_totales"]
                    if row.get("usuarios_totales") else 0.6)
        adopcion = float(adopcion) if pd.notna(adopcion) else 0.6
        r_adop = 1 - min(1.0, max(0.0, adopcion))
        ses = float(row["sesiones"]) if pd.notna(row.get("sesiones")) else 40
        r_ses = 1 - min(1.0, ses / 150.0)
        nps = row.get("nps_score")
        if pd.isna(nps) or nps is None or nps < 0:
            r_nps = 0.5
        elif nps <= 6:
            r_nps = 1.0
        elif nps <= 8:
            r_nps = 0.45
        else:
            r_nps = 0.0
        r_plan = _PLAN_RISK.get(row["plan"], 0.3)
        meses = _meses_entre(row["fecha_alta"], ref)
        r_antig = max(0.0, 1 - meses / 12.0)
        r_base = float(row["riesgo_churn"]) if pd.notna(row["riesgo_churn"]) else 0.2

        score = (_PESOS["adopcion"] * r_adop + _PESOS["sesiones"] * r_ses
                 + _PESOS["nps"] * r_nps + _PESOS["plan"] * r_plan
                 + _PESOS["antiguedad"] * r_antig + _PESOS["riesgo_base"] * r_base)
        # factor principal de riesgo
        factores = {"baja adopción": r_adop * _PESOS["adopcion"],
                    "poco uso": r_ses * _PESOS["sesiones"],
                    "NPS bajo": r_nps * _PESOS["nps"],
                    "plan inicial": r_plan * _PESOS["plan"],
                    "cuenta nueva": r_antig * _PESOS["antiguedad"],
                    "señal histórica": r_base * _PESOS["riesgo_base"]}
        principal = max(factores, key=factores.get)
        return round(min(1.0, score), 3), round(adopcion * 100, 1), principal

    res = df.apply(fila_score, axis=1, result_type="expand")
    df["score"], df["adopcion"], df["factor"] = res[0], res[1], res[2]

    def nivel(s):
        return "Alto" if s >= 0.42 else ("Medio" if s >= 0.28 else "Bajo")
    df["nivel"] = df["score"].apply(nivel)

    acciones = {
        "Alto":  "Contacto proactivo de Customer Success + oferta de retención",
        "Medio": "Onboarding guiado y revisión de adopción",
        "Bajo":  "Seguimiento estándar · oportunidad de upsell",
    }

    top = df.sort_values("score", ascending=False).head(25)
    top_list = [{
        "cliente": r["nombre"], "tipo": r["tipo"], "pais": r["pais"], "plan": r["plan"],
        "score": float(r["score"]), "probabilidad": round(float(r["score"]) * 100, 1),
        "nivel": r["nivel"], "adopcion": float(r["adopcion"]),
        "factor": r["factor"], "ltv": round(float(r["ltv"] or 0), 2),
        "accion": acciones[r["nivel"]],
    } for _, r in top.iterrows()]

    dist = df["nivel"].value_counts().to_dict()
    total = len(df)
    return {
        "disponible": True,
        "modelo": "Scoring ponderado de churn (6 factores)",
        "pesos": _PESOS,
        "total_clientes": total,
        "distribucion": {
            "Alto": int(dist.get("Alto", 0)),
            "Medio": int(dist.get("Medio", 0)),
            "Bajo": int(dist.get("Bajo", 0)),
        },
        "riesgo_promedio": round(float(df["score"].mean()) * 100, 1),
        "ingresos_en_riesgo": round(float(df[df["nivel"] == "Alto"]["ltv"].sum()), 2),
        "cuentas_riesgo": top_list,
    }


# ═════════════════════════════════════════════════════════════════════════════
# 2) SEGMENTACIÓN DE CLIENTES — RFM  (CU-T02)
# ═════════════════════════════════════════════════════════════════════════════

def segmentar_clientes() -> dict:
    latest = _latest()
    if latest is None:
        return {"disponible": False}

    base = _df("""
        SELECT c.id_cliente, c.nombre, c.tipo, m.pais, p.nombre AS plan
        FROM fact_retencion r
        JOIN dim_cliente c ON r.id_cliente = c.id_cliente
        JOIN dim_mercado m ON c.id_mercado = m.id_mercado
        JOIN dim_plan    p ON c.id_plan    = p.id_plan
        WHERE r.id_tiempo = %s AND r.activo = 1
    """, (latest,))
    if base.empty or len(base) < 5:
        return {"disponible": False}

    ltv = _df("SELECT id_cliente, MAX(ltv) AS ltv FROM fact_retencion GROUP BY id_cliente")
    freq = _df("SELECT id_cliente, SUM(sesiones) AS freq FROM fact_uso_plataforma GROUP BY id_cliente")
    rec = _df("""SELECT id_cliente,
                        AVG(usuarios_activos*1.0/usuarios_totales) AS rec
                 FROM fact_uso_plataforma WHERE id_tiempo=%s GROUP BY id_cliente""",
              (latest,))

    df = base.merge(ltv, on="id_cliente", how="left") \
             .merge(freq, on="id_cliente", how="left") \
             .merge(rec, on="id_cliente", how="left")
    df[["ltv", "freq", "rec"]] = df[["ltv", "freq", "rec"]].fillna(0).astype(float)

    def quintil(s):
        # 1..5 robusto ante empates
        return pd.qcut(s.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)

    df["R"] = quintil(df["rec"])
    df["F"] = quintil(df["freq"])
    df["M"] = quintil(df["ltv"])

    def seg(row):
        R, F, M = row["R"], row["F"], row["M"]
        if R >= 4 and F >= 4 and M >= 4:
            return "Campeones"
        if M >= 4 and F >= 3:
            return "Clientes leales"
        if R >= 4 and M <= 3:
            return "Potencial de crecimiento"
        if R <= 2 and M >= 3:
            return "En riesgo (alto valor)"
        if R <= 2 and F <= 2:
            return "Hibernando"
        return "Promedio"
    df["segmento"] = df.apply(seg, axis=1)

    orden = ["Campeones", "Clientes leales", "Potencial de crecimiento",
             "En riesgo (alto valor)", "Promedio", "Hibernando"]
    estrategia = {
        "Campeones": "Programa de embajadores y upsell premium",
        "Clientes leales": "Retención y venta cruzada de módulos",
        "Potencial de crecimiento": "Onboarding y expansión de uso",
        "En riesgo (alto valor)": "Plan de recuperación de Customer Success",
        "Promedio": "Automatización de nurturing",
        "Hibernando": "Campaña de reactivación o cierre",
    }

    segmentos = []
    for s in orden:
        g = df[df["segmento"] == s]
        if g.empty:
            continue
        segmentos.append({
            "segmento": s,
            "clientes": int(len(g)),
            "ltv_promedio": round(float(g["ltv"].mean()), 2),
            "ltv_total": round(float(g["ltv"].sum()), 2),
            "estrategia": estrategia[s],
            "ejemplos": [{"cliente": r["nombre"], "pais": r["pais"], "plan": r["plan"]}
                         for _, r in g.sort_values("ltv", ascending=False).head(4).iterrows()],
        })

    return {
        "disponible": True,
        "modelo": "Segmentación RFM (Recencia · Frecuencia · Monto)",
        "total_clientes": int(len(df)),
        "segmentos": segmentos,
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3) PRECIOS DINÁMICOS Y DEMANDA  (CU-T08 / CU-E02)
# ═════════════════════════════════════════════════════════════════════════════

def _tendencia(xs, ys):
    """Pendiente de regresión lineal simple (numpy.polyfit)."""
    if len(xs) < 2:
        return 0.0
    m, _b = np.polyfit(xs, ys, 1)
    return float(m)


def precios_dinamicos(top: int = 12) -> dict:
    df = _df("""
        SELECT dv.nombre AS variedad,
               COUNT(*) AS demanda,
               AVG(CAST(fr.price AS DOUBLE)) AS precio_prom,
               AVG(CAST(fr.points AS DOUBLE)) AS puntos_prom
        FROM fact_resenas fr
        JOIN dim_variedad dv ON fr.id_variedad = dv.id_variedad
        WHERE fr.price > 0 AND dv.nombre != 'Desconocido'
        GROUP BY dv.nombre
        HAVING COUNT(*) >= 200
        ORDER BY demanda DESC
        LIMIT %s
    """, (top,))
    if df.empty:
        return {"disponible": False}

    demanda_media = float(df["demanda"].mean())
    puntos_media = float(df["puntos_prom"].mean())

    recs = []
    for _, r in df.iterrows():
        precio = float(r["precio_prom"])
        # factor demanda: variedades muy demandadas toleran precio mayor
        f_dem = (float(r["demanda"]) / demanda_media - 1) * 0.06
        # factor calidad: mejor puntuación → premium
        f_cal = (float(r["puntos_prom"]) - puntos_media) * 0.015
        ajuste = max(-0.18, min(0.22, f_dem + f_cal))
        precio_rec = round(precio * (1 + ajuste), 2)
        recs.append({
            "variedad": r["variedad"],
            "demanda": int(r["demanda"]),
            "precio_actual": round(precio, 2),
            "puntos": round(float(r["puntos_prom"]), 1),
            "precio_recomendado": precio_rec,
            "ajuste_pct": round(ajuste * 100, 1),
            "accion": ("Subir precio" if ajuste > 0.03 else
                       "Bajar precio" if ajuste < -0.03 else "Mantener"),
        })

    return {
        "disponible": True,
        "modelo": "Precio dinámico = precio × (1 + f(demanda) + f(calidad))",
        "recomendaciones": recs,
    }


def tendencia_demanda_mercado(top: int = 8) -> dict:
    """Demanda (nº de reseñas) por país como proxy de mercado vitivinícola."""
    df = _df("""
        SELECT dp.nombre AS pais, COUNT(*) AS demanda,
               AVG(CAST(fr.points AS DOUBLE)) AS puntos
        FROM fact_resenas fr JOIN dim_pais dp ON fr.id_pais = dp.id_pais
        WHERE dp.nombre != 'Desconocido'
        GROUP BY dp.nombre ORDER BY demanda DESC LIMIT %s
    """, (top,))
    return {"disponible": not df.empty,
            "mercados": [{"pais": r["pais"], "demanda": int(r["demanda"]),
                          "puntos": round(float(r["puntos"]), 1)} for _, r in df.iterrows()]}


# ═════════════════════════════════════════════════════════════════════════════
# 4) DETECCIÓN DE ANOMALÍAS  (CU-E04 / CU-O13)
# ═════════════════════════════════════════════════════════════════════════════

def _serie_anomalias(df, valor_col, etiqueta, unidad, mejor):
    vals = df[valor_col].astype(float).to_numpy()
    if len(vals) < 4:
        return None
    mu, sigma = float(np.mean(vals)), float(np.std(vals))
    puntos, detec = [], []
    for i, row in df.reset_index(drop=True).iterrows():
        v = float(row[valor_col])
        z = (v - mu) / sigma if sigma > 1e-9 else 0.0
        es_anom = abs(z) > 2.0
        puntos.append({"periodo": row["periodo"], "valor": round(v, 2),
                       "z": round(z, 2), "anomalia": es_anom})
        if es_anom:
            detec.append({"serie": etiqueta, "periodo": row["periodo"],
                          "valor": round(v, 2), "esperado": round(mu, 2),
                          "z": round(z, 2),
                          "tipo": "pico" if z > 0 else "caída"})
    return {"etiqueta": etiqueta, "unidad": unidad, "media": round(mu, 2),
            "mejor": mejor, "puntos": puntos, "anomalias": detec}


def detectar_anomalias() -> dict:
    latest = _latest()
    if latest is None:
        return {"disponible": False}

    mrr = _df("""SELECT t.id_tiempo, t.periodo, SUM(f.mrr) AS v
                 FROM fact_suscripcion f JOIN dim_tiempo t ON f.id_tiempo=t.id_tiempo
                 WHERE f.es_churn=0 GROUP BY t.id_tiempo,t.periodo ORDER BY t.id_tiempo""")
    churn = _df("""SELECT t.id_tiempo, t.periodo,
                          SUM(f.cancelacion)*100.0/(SUM(f.activo)+SUM(f.cancelacion)) AS v
                   FROM fact_retencion f JOIN dim_tiempo t ON f.id_tiempo=t.id_tiempo
                   GROUP BY t.id_tiempo,t.periodo ORDER BY t.id_tiempo""")
    err = _df("""SELECT t.id_tiempo, t.periodo, SUM(f.errores) AS v
                 FROM fact_consumo_api f JOIN dim_tiempo t ON f.id_tiempo=t.id_tiempo
                 GROUP BY t.id_tiempo,t.periodo ORDER BY t.id_tiempo""")
    lat = _df("""SELECT t.id_tiempo, t.periodo, AVG(f.latencia_ms) AS v
                 FROM fact_disponibilidad f JOIN dim_tiempo t ON f.id_tiempo=t.id_tiempo
                 GROUP BY t.id_tiempo,t.periodo ORDER BY t.id_tiempo""")

    series = []
    for df, etq, uni, mejor in [
        (mrr, "Ingresos recurrentes (MRR)", "$", "mayor"),
        (churn, "Tasa de churn", "%", "menor"),
        (err, "Errores de API", "", "menor"),
        (lat, "Latencia global", "ms", "menor"),
    ]:
        s = _serie_anomalias(df, "v", etq, uni, mejor) if not df.empty else None
        if s:
            series.append(s)

    todas = [a for s in series for a in s["anomalias"]]
    return {
        "disponible": True,
        "modelo": "Detección por z-score (|z| > 2 sobre series mensuales)",
        "series": series,
        "anomalias": todas,
        "estado": "Anomalías detectadas" if todas else "Sin anomalías significativas",
    }


if __name__ == "__main__":
    import json
    print(json.dumps(predecir_churn(), ensure_ascii=False)[:600])
    print(json.dumps(segmentar_clientes(), ensure_ascii=False)[:600])
    print(json.dumps(precios_dinamicos(), ensure_ascii=False)[:400])
    print(json.dumps(detectar_anomalias(), ensure_ascii=False)[:400])
