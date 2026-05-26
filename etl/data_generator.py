"""
Genera N reseñas de vino con datos aleatorios e inserta directo en StarRocks.
Lee las dimensiones existentes para usar FKs válidas.
Algunos campos se dejan vacíos intencionalmente.
"""

import random
import sys
from pathlib import Path

import mysql.connector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import (
    STARROCKS_HOST, STARROCKS_PORT, STARROCKS_DB,
    STARROCKS_USER, STARROCKS_PASS, ETL_BATCH_SIZE,
)

VARIETIES_EXTRA = [
    "Cabernet Sauvignon", "Merlot", "Pinot Noir", "Chardonnay", "Sauvignon Blanc",
    "Riesling", "Syrah", "Zinfandel", "Grenache", "Tempranillo", "Sangiovese",
    "Nebbiolo", "Malbec", "Carmenère", "Pinot Grigio", "Viognier", "Gewürztraminer",
    "Chenin Blanc", "Barbera", "Albariño", "Verdejo", "Monastrell", "Touriga Nacional",
    "Grüner Veltliner", "Zweigelt", "Cabernet Franc", "Petit Verdot", "Red Blend",
    "White Blend", "Rosé", "Champagne Blend", "Pinot Meunier", "Shiraz",
]

WINERY_PRE  = ["Château","Domaine","Bodega","Cantina","Tenuta","Quinta",
                "Weingut","Villa","Casa","Viña","Bodegas","Cave","Clos"]
WINERY_SUF  = ["Alto","Bella","Crest","Del Sol","Esperanza","Fuente","Grande",
                "Hermosa","Klein","Luna","Monte","Norte","Pico","Roca","Sierra",
                "Torre","Valle","Vista","Bravo","Cruz","Dorado","Flores","Gracia",
                "Nuevo","Reyes","Santos","Vidal","Campos","Lagos","Brioso"]

DESIGNATIONS = [
    "Reserve","Grand Reserve","Estate","Old Vine","Single Vineyard",
    "Barrel Select","Signature","Collector's Edition","Special Release",
    "Limited Edition","Cellar Select","Heritage","Classico","Superior",
    None, None, None,   # ~18 % sin designación
]

ADJECTIVES = ["bold","elegant","smooth","crisp","rich","vibrant","complex",
              "fresh","structured","silky","velvety","bright","concentrated","aromatic"]
FRUITS     = ["blackberry","cherry","plum","raspberry","strawberry","blueberry",
              "peach","apricot","lemon","grapefruit","apple","pear","fig","cassis"]
SPICES     = ["oak","vanilla","chocolate","coffee","cedar","tobacco","pepper",
              "clove","licorice","herbs","mint","eucalyptus","leather","earth"]


def _desc() -> str:
    t = random.choice([
        "A {a1} wine with notes of {f1} and {f2}. The palate shows {a2} tannins and a {a3} finish.",
        "Rich and {a1} on the nose, with aromas of {f1}, {f2}, and {s}. Medium-bodied with {a2} acidity.",
        "An elegant expression featuring {f1} and {s} on the nose. The palate delivers {a2} flavors.",
        "This {a1} wine opens with {f1} and hints of {s}. Firm tannins and bright acidity.",
        "Concentrated {f1} and {f2} dominate the nose. On the palate it is {a1} with a {a2} finish.",
    ])
    return t.format(
        a1=random.choice(ADJECTIVES), a2=random.choice(ADJECTIVES), a3=random.choice(ADJECTIVES),
        f1=random.choice(FRUITS),     f2=random.choice(FRUITS),
        s=random.choice(SPICES),
    )


def _conn():
    return mysql.connector.connect(
        host=STARROCKS_HOST, port=STARROCKS_PORT, database=STARROCKS_DB,
        user=STARROCKS_USER, password=STARROCKS_PASS, connection_timeout=15,
    )


def _load_dim_ids(cur, table: str, id_col: str) -> list[int]:
    cur.execute(f"SELECT {id_col} FROM `{table}`")
    rows = cur.fetchall()
    return [r[0] for r in rows] if rows else []


def generate(n: int = 100_000) -> int:
    print(f"Conectando a StarRocks ...")
    conn = _conn()
    cur  = conn.cursor()
    print(f"  [OK] Conexión establecida\n")

    # ── Cargar IDs de dimensiones existentes ──────────────────────────────
    print("Leyendo dimensiones existentes ...")
    pais_ids      = _load_dim_ids(cur, "dim_pais",      "id_pais")
    variedad_ids  = _load_dim_ids(cur, "dim_variedad",  "id_variedad")
    bodega_ids    = _load_dim_ids(cur, "dim_bodega",    "id_bodega")
    provincia_ids = _load_dim_ids(cur, "dim_provincia", "id_provincia")
    region_ids    = _load_dim_ids(cur, "dim_region",    "id_region")
    catador_ids   = _load_dim_ids(cur, "dim_catador",   "id_catador")

    if not all([pais_ids, variedad_ids, bodega_ids, provincia_ids, region_ids, catador_ids]):
        cur.close(); conn.close()
        raise RuntimeError(
            "Las tablas de dimensiones están vacías. "
            "Ejecute primero el pipeline E→T→L con el CSV real."
        )

    print(f"  Países:    {len(pais_ids)}")
    print(f"  Variedades:{len(variedad_ids)}")
    print(f"  Bodegas:   {len(bodega_ids)}")
    print(f"  Provincias:{len(provincia_ids)}")
    print(f"  Regiones:  {len(region_ids)}")
    print(f"  Catadores: {len(catador_ids)}")

    # ── Obtener el próximo id_resena ──────────────────────────────────────
    cur.execute("SELECT COALESCE(MAX(id_resena), 0) FROM fact_resenas")
    max_id = int(cur.fetchone()[0])
    print(f"\nPróximo id_resena: {max_id + 1:,}")
    print(f"Generando {n:,} reseñas aleatorias ...\n")

    sql = """
        INSERT INTO fact_resenas
          (id_resena, points, price, title, designation, description,
           region_2, id_pais, id_variedad, id_bodega, id_provincia, id_region, id_catador)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """

    total_ok = 0
    batch_size = ETL_BATCH_SIZE

    for start in range(0, n, batch_size):
        chunk_size = min(batch_size, n - start)
        rows = []
        for j in range(chunk_size):
            rid    = max_id + start + j + 1
            points = random.randint(80, 100)
            # ~20 % sin precio
            price  = round(random.uniform(8.0, 350.0), 2) if random.random() > 0.20 else 0.0
            variety = random.choice(VARIETIES_EXTRA)
            winery  = f"{random.choice(WINERY_PRE)} {random.choice(WINERY_SUF)}"
            year    = random.randint(2010, 2022)
            title   = f"{winery} {variety} {year}"
            # ~18 % sin designación
            desig   = random.choice(DESIGNATIONS) or ""
            # ~12 % sin descripción
            desc    = _desc() if random.random() > 0.12 else ""
            # ~25 % sin region_2
            reg2    = random.choice(["","","North","South","East","West","Central"]) if random.random() > 0.25 else ""

            rows.append((
                rid, points, price, title[:500], desig[:300], desc[:1000], reg2[:150],
                random.choice(pais_ids),
                random.choice(variedad_ids),
                random.choice(bodega_ids),
                random.choice(provincia_ids),
                random.choice(region_ids),
                random.choice(catador_ids),
            ))

        cur.executemany(sql, rows)
        conn.commit()
        total_ok += chunk_size
        pct = total_ok / n * 100
        print(f"  {total_ok:>7,}/{n:,}  ({pct:5.1f}%)")

    cur.close()
    conn.close()

    print(f"\n{'='*50}")
    print(f"GENERACIÓN COMPLETADA")
    print(f"  Insertados en fact_resenas: {total_ok:,}")
    print(f"{'='*50}")
    return total_ok


if __name__ == "__main__":
    generate()
