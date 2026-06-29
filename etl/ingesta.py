"""
etl/ingesta.py — Ingesta de datos externos · CU-O02 (OP1).

Aterriza los datos crudos de una fuente HABILITADA del catálogo (CU-O01,
`etl/source_catalog.py`) en la capa de staging Parquet (snappy), de forma
idempotente, deduplicada y auditada. La ingesta NO transforma a Fact-Dim ni
carga StarRocks (RN-206, RT-01): solo deja un aterrizaje limpio y trazable que
luego CU-O04 (GE) valida y CU-O03 (DBT) promueve.

Flujo del lote (§9 del spec):
  PENDIENTE → LEYENDO → VALIDANDO_ESQUEMA → DEDUPLICANDO → ESCRIBIENDO_PARQUET
            → COMPLETADA | PARCIAL | FALLIDA

Reglas implementadas:
  - RN-201  Solo se ingiere de una fuente registrada y HABILITADA.
  - RF-107  Validación de esquema por registro; los inválidos van a `rejects/`
            con su causa, sin frenar el lote válido.
  - RN-204  Si el % de rechazo supera el 5 %, el lote es FALLIDA y NO aterriza
            (emite alerta).
  - RN-205  Dominios mínimos por tipo (puntaje∈[80,100], precio>0 en `precios`,
            fecha no futura, moneda ISO-4217).
  - RF-108 / RN-203  Deduplicación por clave natural antes de escribir.
  - RF-109 / RNF-101 Escritura en Parquet snappy particionado por fuente/fecha.
  - RF-110  Reporte de ingesta (leídas/cargadas/rechazadas/duplicadas/estado).
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import STAGE_DIR
from etl import source_catalog as cat

# ── Rutas de staging (capa Parquet) ───────────────────────────────────────────
STAGE = Path(STAGE_DIR)
INGESTA_DIR = STAGE / "ingesta"          # datos válidos particionados
REJECTS_DIR = STAGE / "rejects"          # área de rechazos auditada (RF-107)
REPORTES_DIR = INGESTA_DIR / "_reportes"  # reportes de ingesta por lote (RF-110)
WINE_RAW = STAGE / "wine_raw.parquet"    # vista plana para el ETL/GE existente

UMBRAL_RECHAZO = 0.05                     # RN-204 (5 %)

# Monedas ISO-4217 frecuentes en el dominio (RN-205). Lista acotada; GE (CU-O04)
# hace la validación exhaustiva aguas abajo.
_MONEDAS_ISO = {"USD", "EUR", "GBP", "CLP", "ARS", "MXN", "ZAR", "AUD", "BRL"}


# ── Validación de esquema y dominios (RF-107, RN-205) ─────────────────────────
def _motivo_rechazo(reg: dict, tipo: str, requeridos: tuple[str, ...]) -> str:
    """Devuelve la causa de rechazo de un registro, o "" si es válido."""
    # 1) Campos obligatorios presentes y no vacíos (RF-107).
    for col in requeridos:
        val = reg.get(col, None)
        if val is None or (isinstance(val, str) and not val.strip()):
            return f"campo_faltante:{col}"
        if isinstance(val, float) and pd.isna(val):
            return f"campo_faltante:{col}"

    # 2) Dominios mínimos por tipo (RN-205).
    if tipo in ("reseñas", "puntuaciones"):
        pts = pd.to_numeric(reg.get("points"), errors="coerce")
        if pd.isna(pts) or not (80 <= pts <= 100):
            return f"dominio:puntaje_fuera_de_rango:{reg.get('points')}"

    if tipo == "precios":
        prc = pd.to_numeric(reg.get("price"), errors="coerce")
        if pd.isna(prc) or prc <= 0:                       # RN-205 precio > 0
            return f"dominio:precio_no_positivo:{reg.get('price')}"
        moneda = str(reg.get("moneda", "")).strip().upper()
        if moneda not in _MONEDAS_ISO:
            return f"dominio:moneda_no_iso4217:{reg.get('moneda')}"

    # 3) Fecha no futura cuando el tipo la incluye (RN-205).
    for fcol in ("fecha_precio", "fecha_cata", "fecha_resena"):
        if fcol in reg and str(reg.get(fcol, "")).strip():
            f = pd.to_datetime(reg.get(fcol), errors="coerce")
            if pd.notna(f) and f.date() > date.today():
                return f"dominio:fecha_futura:{reg.get(fcol)}"

    return ""


def procesar_lote(records: list[dict], *, tipo: str, fuente_id: str,
                  clave_natural: list[str], umbral_rechazo: float = UMBRAL_RECHAZO,
                  fecha_ingesta: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Núcleo puro de la ingesta: valida esquema → rechaza → dedup → reporta.

    No realiza E/S: separa los DataFrames válido/rechazado y devuelve el reporte
    para que el orquestador decida el aterrizaje. Reusable y testeable sin red.
    """
    fecha_ingesta = fecha_ingesta or date.today().isoformat()
    requeridos = cat.esquema_minimo_de(tipo)

    df = pd.DataFrame(records)
    filas_leidas = len(df)

    # ── VALIDANDO_ESQUEMA (RF-107, RN-205) ────────────────────────────────────
    if filas_leidas:
        motivos = df.to_dict(orient="records")
        motivos = [_motivo_rechazo(r, tipo, requeridos) for r in motivos]
        mask_valida = [m == "" for m in motivos]
        df_validos = df[mask_valida].reset_index(drop=True)
        df_rechazados = df[[not v for v in mask_valida]].reset_index(drop=True)
        df_rechazados = df_rechazados.assign(
            motivo_rechazo=[m for m in motivos if m != ""],
            fuente=fuente_id,
            fecha_ingesta=fecha_ingesta,
        )
    else:
        df_validos = df.copy()
        df_rechazados = pd.DataFrame(columns=list(df.columns) + ["motivo_rechazo"])

    filas_rechazadas = len(df_rechazados)
    filas_validas = len(df_validos)
    pct_rechazo = (filas_rechazadas / filas_leidas) if filas_leidas else 0.0

    # ── DEDUPLICANDO (RF-108, RN-203) ─────────────────────────────────────────
    claves_presentes = [c for c in clave_natural if c in df_validos.columns]
    if claves_presentes and filas_validas:
        antes = len(df_validos)
        df_validos = df_validos.drop_duplicates(subset=claves_presentes, keep="first") \
                               .reset_index(drop=True)
        filas_duplicadas = antes - len(df_validos)
    else:
        filas_duplicadas = 0
    filas_cargadas = len(df_validos)

    # ── Estado del lote (§9, RN-204) ──────────────────────────────────────────
    if filas_leidas == 0:
        estado = "FALLIDA"
    elif pct_rechazo > umbral_rechazo:
        estado = "FALLIDA"            # RN-204: no aterriza
    elif filas_rechazadas > 0:
        estado = "PARCIAL"
    else:
        estado = "COMPLETADA"

    reporte = {
        "fuente": fuente_id,
        "tipo": tipo,
        "fecha_ingesta": fecha_ingesta,
        "clave_natural": claves_presentes,
        "filas_leidas": filas_leidas,
        "filas_validas": filas_validas,
        "filas_duplicadas": filas_duplicadas,
        "filas_rechazadas": filas_rechazadas,
        "filas_cargadas": filas_cargadas if estado != "FALLIDA" else 0,
        "pct_rechazo": round(pct_rechazo * 100, 2),
        "umbral_pct": round(umbral_rechazo * 100, 2),
        "estado": estado,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    return df_validos, df_rechazados, reporte


# ── Escritores Parquet snappy particionados (RF-109, RNF-101) ─────────────────
def _ruta_particion(base: Path, tipo: str, fuente_id: str, fecha_ingesta: str) -> Path:
    return base / tipo / f"fuente={fuente_id}" / f"fecha_ingesta={fecha_ingesta}"


def escribir_staging_particionado(df: pd.DataFrame, *, tipo: str, fuente_id: str,
                                  fecha_ingesta: str) -> Path:
    """Escribe los datos válidos en Parquet snappy, particionado por
    fuente/fecha_ingesta. Sobrescribe la partición → idempotente (RNF-102)."""
    destino = _ruta_particion(INGESTA_DIR, tipo, fuente_id, fecha_ingesta)
    destino.mkdir(parents=True, exist_ok=True)
    out = destino / "data.parquet"
    df.to_parquet(out, index=False, compression="snappy")
    return out


def escribir_rechazos(df_rej: pd.DataFrame, *, tipo: str, fuente_id: str,
                      fecha_ingesta: str) -> Path | None:
    """Persiste el área de rechazos auditada (con causa). Idempotente (RF-107)."""
    if df_rej.empty:
        return None
    destino = _ruta_particion(REJECTS_DIR, tipo, fuente_id, fecha_ingesta)
    destino.mkdir(parents=True, exist_ok=True)
    out = destino / "data.parquet"
    df_rej.to_parquet(out, index=False, compression="snappy")
    return out


def guardar_reporte(reporte: dict) -> Path:
    """Persiste el reporte de ingesta del lote (RF-110)."""
    REPORTES_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTES_DIR / f"{reporte['fuente']}_{reporte['fecha_ingesta']}.json"
    out.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


# ── Lector de fuente PocketBase (RF-106) ──────────────────────────────────────
def leer_coleccion_pocketbase(client, coleccion: str, page_size: int = 500) -> list[dict]:
    """Pagina una colección PocketBase y devuelve los registros sin campos meta."""
    meta = {"id", "collectionId", "collectionName", "created", "updated", "expand"}
    registros: list[dict] = []
    page, total_pages = 1, None
    base = client.base_url
    while True:
        resp = client.session.get(
            f"{base}/api/collections/{coleccion}/records",
            params={"page": page, "perPage": page_size}, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if total_pages is None:
            total_pages = data.get("totalPages", 1)
        items = data.get("items", [])
        if not items:
            break
        registros.extend({k: v for k, v in it.items() if k not in meta} for it in items)
        if page >= total_pages:
            break
        page += 1
    return registros


# ── Emisión de eventos para observabilidad / alertas (RNF-105, RN-204) ────────
def _emitir_evento(reporte: dict) -> None:
    """Log estructurado consumible por OP7/OP9. En FALLIDA emite una ALERTA."""
    nivel = "ALERTA" if reporte["estado"] == "FALLIDA" else "INFO"
    print(f"[{nivel}] ingesta {json.dumps(reporte, ensure_ascii=False)}")


# ── Orquestación de una fuente (RN-201, RF-106..RF-110) ───────────────────────
def ingestar_fuente(fuente: dict, *, client=None, records: list[dict] | None = None,
                    fecha_ingesta: str | None = None, escribir_plano: bool = True) -> dict:
    """Ingiere una fuente del catálogo y aterriza el staging.

    - `records` permite inyectar el lote (tests); si es None se lee de PocketBase.
    - RN-201: la fuente debe estar HABILITADA, si no, el lote es FALLIDA y no lee.
    """
    fecha_ingesta = fecha_ingesta or date.today().isoformat()
    tipo = fuente.get("tipo", "")
    fuente_id = fuente.get("id", fuente.get("endpoint", "desconocida"))
    clave_natural = cat.clave_natural_de(fuente)

    # RN-201: sin fuente habilitada no hay ingesta.
    if fuente.get("estado") != cat.HABILITADA:
        reporte = {
            "fuente": fuente_id, "tipo": tipo, "fecha_ingesta": fecha_ingesta,
            "filas_leidas": 0, "filas_cargadas": 0, "estado": "FALLIDA",
            "motivo": f"fuente no HABILITADA (estado={fuente.get('estado')})",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        _emitir_evento(reporte)
        guardar_reporte(reporte)
        return reporte

    # ── LEYENDO (RF-106) ──────────────────────────────────────────────────────
    if records is None:
        coleccion = str(fuente.get("coleccion") or fuente.get("endpoint"))
        records = leer_coleccion_pocketbase(client, coleccion)

    # ── VALIDANDO_ESQUEMA → DEDUPLICANDO (núcleo puro) ────────────────────────
    df_validos, df_rechazados, reporte = procesar_lote(
        records, tipo=tipo, fuente_id=fuente_id,
        clave_natural=clave_natural, fecha_ingesta=fecha_ingesta)

    # El área de rechazos se persiste siempre (auditoría), incluso en FALLIDA.
    ruta_rej = escribir_rechazos(df_rechazados, tipo=tipo, fuente_id=fuente_id,
                                 fecha_ingesta=fecha_ingesta)
    reporte["ruta_rechazos"] = str(ruta_rej) if ruta_rej else None

    # ── ESCRIBIENDO_PARQUET (solo si no es FALLIDA, RN-204) ───────────────────
    if reporte["estado"] != "FALLIDA":
        ruta = escribir_staging_particionado(
            df_validos, tipo=tipo, fuente_id=fuente_id, fecha_ingesta=fecha_ingesta)
        reporte["ruta_staging"] = str(ruta)
        # Compatibilidad: el ETL/GE existente leen stage/wine_raw.parquet.
        if escribir_plano and tipo == "reseñas":
            df_validos.to_parquet(WINE_RAW, index=False, compression="snappy")
            reporte["ruta_wine_raw"] = str(WINE_RAW)
        if client is not None and fuente.get("id"):
            cat.marcar_ingesta(fuente["id"], reporte["estado"],
                               reporte["timestamp"], client)
    else:
        reporte["ruta_staging"] = None
        if client is not None and fuente.get("id"):
            cat.marcar_ingesta(fuente["id"], "FALLIDA", client=client)

    guardar_reporte(reporte)
    _emitir_evento(reporte)
    return reporte


def ingestar_todas(client=None) -> list[dict]:
    """Ingiere todas las fuentes HABILITADAS del catálogo (RF-106)."""
    from pb_client import get_client
    client = client or get_client()
    reportes = []
    for fuente in cat.fuentes_habilitadas(client):
        reportes.append(ingestar_fuente(fuente, client=client))
    return reportes


if __name__ == "__main__":
    from pb_client import get_client
    print(json.dumps(ingestar_todas(get_client()), ensure_ascii=False, indent=2))
