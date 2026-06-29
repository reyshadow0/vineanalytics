"""
tests/test_ingesta.py — Pruebas offline de CU-O01 y CU-O02 (paquete ingesta-datos).

No requieren PocketBase ni Docker: el núcleo de ingesta es puro y el catálogo se
prueba con un cliente PocketBase en memoria (FakePB). Cubren:

  CU-O01: validación de metadatos, dedup de fuentes, ciclo de vida.
  CU-O02: validación de esquema + rechazos con causa, umbral 5 % (FALLIDA),
          deduplicación por clave natural, reporte, escritura Parquet snappy,
          idempotencia (reejecutar no duplica) y compatibilidad con el
          transformer posterior (el staging generado sigue siendo consumible).

Ejecutar:  python -m tests.test_ingesta
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# La consola de Windows suele ser cp1252; forzamos UTF-8 para los símbolos (→, ñ).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from etl import ingesta, source_catalog as cat

_fallos: list[str] = []


def check(cond: bool, msg: str) -> None:
    estado = "OK  " if cond else "FALL"
    print(f"  [{estado}] {msg}")
    if not cond:
        _fallos.append(msg)


# ── Cliente PocketBase en memoria (para CU-O01 sin red) ───────────────────────
class FakePB:
    """Imita la superficie de PBClient usada por source_catalog."""

    def __init__(self):
        self.data: dict[str, list[dict]] = {}
        self._seq = 0

    def collection_exists(self, name): return name in self.data

    def ensure_collection(self, name, schema, type_="base"):
        if name in self.data:
            return False
        self.data[name] = []
        return True

    def find(self, collection, per_page=200, **filters):
        rows = self.data.get(collection, [])
        return [r for r in rows
                if all(str(r.get(k)) == str(v) for k, v in filters.items())][:per_page]

    def find_one(self, collection, **filters):
        items = self.find(collection, per_page=1, **filters)
        return items[0] if items else None

    def create(self, collection, data):
        self._seq += 1
        rec = {"id": f"rec{self._seq:04d}", **data}
        self.data.setdefault(collection, []).append(rec)
        return rec

    def update(self, collection, record_id, data):
        for r in self.data.get(collection, []):
            if r["id"] == record_id:
                r.update(data)
                return r
        raise KeyError(record_id)


# ── Datos sintéticos de reseñas ───────────────────────────────────────────────
def _resena(taster, title, winery, points=90, price=20.0):
    return {"country": "Italy", "description": "x", "designation": "",
            "points": points, "price": price, "province": "p", "region_1": "r",
            "region_2": "", "taster_name": taster, "taster_twitter_handle": "@x",
            "title": title, "variety": "Red Blend", "winery": winery}


# ── CU-O01 ────────────────────────────────────────────────────────────────────
def test_cu_o01_catalogo():
    print("\nCU-O01 — Catálogo de fuentes")
    pb = FakePB()

    # Metadatos inválidos → no se registra.
    errs = cat.validar_metadatos({"nombre": "", "tipo": "x", "formato": "z",
                                  "endpoint": "", "frecuencia": "diaria"})
    check(len(errs) >= 4, f"validar_metadatos detecta metadatos inválidos ({len(errs)} errores)")

    try:
        cat.registrar_fuente({"nombre": "mala", "tipo": "x", "formato": "json",
                              "endpoint": "e", "frecuencia": "0 6 * * *"}, pb)
        check(False, "registrar_fuente rechaza tipo inválido")
    except cat.FuenteInvalida:
        check(True, "registrar_fuente rechaza tipo inválido (FuenteInvalida)")

    # Alta nominal → REGISTRADA.
    datos = {"nombre": "Precios EU", "tipo": "precios", "formato": "api",
             "endpoint": "https://api.precios/eu", "frecuencia": "0 6 * * *",
             "mercado": "Europa"}
    f1 = cat.registrar_fuente(datos, pb)
    check(f1["estado"] == cat.REGISTRADA, "alta nominal deja la fuente REGISTRADA")

    # Alta duplicada (tipo+endpoint+formato) → rechazo con id existente (RN-202).
    try:
        cat.registrar_fuente(datos, pb)
        check(False, "alta duplicada rechazada")
    except cat.FuenteDuplicada as exc:
        check(exc.detalle.get("id_existente") == f1["id"],
              "alta duplicada rechazada devolviendo el id existente (RF-104/RN-202)")

    # Habilitar (no hay 'coleccion' → conectividad asumida OK) → HABILITADA.
    f1h = cat.habilitar_fuente(f1["id"], pb)
    check(f1h["estado"] == cat.HABILITADA, "habilitar_fuente → HABILITADA")
    check(len(cat.fuentes_habilitadas(pb)) == 1, "fuentes_habilitadas lista 1 fuente")

    # Deshabilitar → DESHABILITADA y fuera de la lista de habilitadas.
    cat.deshabilitar_fuente(f1["id"], pb)
    check(len(cat.fuentes_habilitadas(pb)) == 0, "deshabilitar_fuente saca la fuente de habilitadas")

    # Conectividad: colección PB inexistente → RECHAZADA al habilitar (RF-102).
    f2 = cat.registrar_fuente({"nombre": "Reseñas X", "tipo": "reseñas",
                               "formato": "json", "endpoint": "no_existe",
                               "coleccion": "no_existe", "frecuencia": "0 6 * * *"}, pb)
    try:
        cat.habilitar_fuente(f2["id"], pb)
        check(False, "habilitar con colección inexistente falla")
    except cat.ConectividadInvalida:
        rec = cat.obtener_fuente(f2["id"], pb)
        check(rec["estado"] == cat.RECHAZADA,
              "conectividad inválida → fuente RECHAZADA (RF-102)")


# ── CU-O02 ────────────────────────────────────────────────────────────────────
def test_cu_o02_dedup_rechazos_reporte():
    print("\nCU-O02 — Validación, rechazos, dedup y reporte")
    clave = cat.CLAVE_NATURAL_DEFAULT["reseñas"]

    registros = [
        _resena("Ana", "Vino A 2018", "Bodega 1"),                 # válido
        _resena("Ana", "Vino A 2018", "Bodega 1"),                 # DUPLICADO
        _resena("Beto", "Vino B 2019", "Bodega 2"),                # válido
        _resena("Ana", "", "Bodega 3"),                            # RECHAZO: title vacío
        _resena("Cira", "Vino C 2020", "Bodega 4", points=55),     # RECHAZO: puntaje fuera de rango
    ]
    val, rej, rep = ingesta.procesar_lote(
        registros, tipo="reseñas", fuente_id="rec0001", clave_natural=list(clave))

    check(rep["filas_leidas"] == 5, "reporte: 5 filas leídas")
    check(rep["filas_rechazadas"] == 2, "reporte: 2 rechazadas (title vacío + puntaje)")
    check(rep["filas_duplicadas"] == 1, "reporte: 1 duplicada por clave natural")
    check(rep["filas_cargadas"] == 0, "reporte: 0 cargadas (lote FALLIDA no aterriza)")
    # 2/5 = 40% de rechazo > 5% → FALLIDA (RN-204). El dedup igual se contabiliza.
    check(rep["estado"] == "FALLIDA", "RN-204: 40% de rechazo > 5% → FALLIDA (no aterriza)")
    check(len(rej) == 2 and "motivo_rechazo" in rej.columns,
          "área de rechazos tiene 2 filas con su causa (motivo_rechazo)")
    motivos = set(rej["motivo_rechazo"])
    check(any(m.startswith("campo_faltante:title") for m in motivos),
          "rechazo etiquetado 'campo_faltante:title'")
    check(any(m.startswith("dominio:puntaje") for m in motivos),
          "rechazo etiquetado 'dominio:puntaje_fuera_de_rango'")


def test_cu_o02_umbral_y_parcial():
    print("\nCU-O02 — Umbral 5%: PARCIAL vs FALLIDA")
    clave = list(cat.CLAVE_NATURAL_DEFAULT["reseñas"])

    # Lote de 100 con 2% inválido → PARCIAL, aterriza.
    base = [_resena(f"T{i}", f"Vino {i}", f"B{i}") for i in range(98)]
    malos = [_resena(f"T{i}", f"Vino {i}", f"B{i}", points=10) for i in range(98, 100)]
    _, _, rep = ingesta.procesar_lote(base + malos, tipo="reseñas",
                                      fuente_id="f", clave_natural=clave)
    check(rep["pct_rechazo"] == 2.0 and rep["estado"] == "PARCIAL",
          "2% inválido → PARCIAL (aterriza con rechazos)")

    # Lote de 100 con 12% inválido → FALLIDA, no aterriza.
    base = [_resena(f"T{i}", f"Vino {i}", f"B{i}") for i in range(88)]
    malos = [_resena(f"T{i}", f"Vino {i}", f"B{i}", points=1) for i in range(88, 100)]
    _, _, rep = ingesta.procesar_lote(base + malos, tipo="reseñas",
                                      fuente_id="f", clave_natural=clave)
    check(rep["pct_rechazo"] == 12.0 and rep["estado"] == "FALLIDA",
          "12% inválido → FALLIDA (no aterriza)")
    check(rep["filas_cargadas"] == 0, "FALLIDA reporta 0 filas cargadas")


def test_cu_o02_escritura_e_idempotencia(tmp: Path):
    print("\nCU-O02 — Parquet snappy + idempotencia")
    # Redirige las rutas de staging al directorio temporal.
    ingesta.STAGE = tmp
    ingesta.INGESTA_DIR = tmp / "ingesta"
    ingesta.REJECTS_DIR = tmp / "rejects"
    ingesta.REPORTES_DIR = ingesta.INGESTA_DIR / "_reportes"
    ingesta.WINE_RAW = tmp / "wine_raw.parquet"

    fuente = {"id": "rec0001", "tipo": "reseñas", "estado": cat.HABILITADA,
              "endpoint": "wine_reviews", "coleccion": "wine_reviews"}
    # 4 válidos + 1 duplicado (mismo taster/title/winery).
    registros = [
        _resena("Ana", "Vino A", "B1"), _resena("Ana", "Vino A", "B1"),  # dup
        _resena("Beto", "Vino B", "B2"), _resena("Cira", "Vino C", "B3"),
    ]

    rep1 = ingesta.ingestar_fuente(fuente, client=None, records=registros,
                                   fecha_ingesta="2026-06-29", escribir_plano=True)
    check(rep1["estado"] == "COMPLETADA" or rep1["estado"] == "PARCIAL",
          "primer run aterriza (estado no FALLIDA)")
    check(rep1["filas_cargadas"] == 3, "primer run carga 3 filas (1 duplicada eliminada)")

    raw = pd.read_parquet(ingesta.WINE_RAW)
    n1 = len(raw)
    check(n1 == 3, f"wine_raw.parquet tiene 3 filas tras el 1er run (real={n1})")
    codec = pq.ParquetFile(ingesta.WINE_RAW).metadata.row_group(0).column(0).compression
    check(codec == "SNAPPY", f"wine_raw.parquet comprimido en SNAPPY (real={codec})")

    parts = list((ingesta.INGESTA_DIR / "reseñas" / "fuente=rec0001"
                  / "fecha_ingesta=2026-06-29").glob("*.parquet"))
    check(len(parts) == 1, "staging particionado por fuente/fecha_ingesta")

    # Reejecutar la MISMA ventana → no debe duplicar (RNF-102, CA-104).
    rep2 = ingesta.ingestar_fuente(fuente, client=None, records=registros,
                                   fecha_ingesta="2026-06-29", escribir_plano=True)
    n2 = len(pd.read_parquet(ingesta.WINE_RAW))
    check(n2 == n1, f"IDEMPOTENCIA: reejecutar no incrementa filas ({n1} → {n2})")
    check(rep2["filas_cargadas"] == rep1["filas_cargadas"],
          "IDEMPOTENCIA: filas_cargadas estable entre reruns")


def test_downstream_transformer(tmp: Path):
    print("\nCU-O02 — El staging generado sigue siendo consumible por el ETL (CU-O03)")
    from etl import transformer

    # Genera un wine_raw plano con la ingesta y verifica que el transformer lo
    # consuma (construye dims + fact_resenas) sin romperse.
    registros = [_resena(f"T{i%7}", f"Vino {i}", f"B{i%5}", points=85 + i % 10,
                         price=10 + i) for i in range(60)]
    val, _, _ = ingesta.procesar_lote(registros, tipo="reseñas", fuente_id="f",
                                      clave_natural=list(cat.CLAVE_NATURAL_DEFAULT["reseñas"]))
    raw_path = tmp / "wine_raw.parquet"
    val.to_parquet(raw_path, index=False, compression="snappy")

    # Aísla las salidas del transformer al directorio temporal.
    transformer.STAGE_DIR = str(tmp)
    result = transformer.transform(raw_path=raw_path, out_path=tmp / "wine_clean.parquet")

    fact = result["fact_resenas"]
    check(not fact.empty, "transformer construye fact_resenas desde el staging ingerido")
    check(fact["id_resena"].is_unique, "fact_resenas.id_resena es único (consumible por stg_resena/DBT)")
    check("dim_catador" in result, "transformer construye las dimensiones esperadas")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="ingesta_test_"))
    try:
        test_cu_o01_catalogo()
        test_cu_o02_dedup_rechazos_reporte()
        test_cu_o02_umbral_y_parcial()
        test_cu_o02_escritura_e_idempotencia(tmp)
        test_downstream_transformer(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 56)
    if _fallos:
        print(f"RESULTADO: {len(_fallos)} comprobación(es) FALLIDA(s):")
        for f in _fallos:
            print(f"  - {f}")
        return 1
    print("RESULTADO: todas las comprobaciones OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
