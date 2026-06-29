# DBT — Transformación declarativa sobre StarRocks (Fase 1)

Implementa **CU-O03** (transformación) del paquete `etl-calidad` (OP2) como modelos
DBT versionados, cumpliendo el **Principio VI** de la constitución (transformación
declarativa en SQL/DBT, nada de SQL imperativo suelto) y el **VII** (linaje).

## Qué hace
- `models/staging/_sources.yml` — declara las tablas StarRocks ya cargadas como
  **sources** (origen del linaje).
- `models/staging/stg_resena.sql` — vista de limpieza + dedup por `id_resena`.
- `models/marts/` — modelo **Fact-Dim** curado, mapeado a la matriz §9.8:
  - `dim_vino`, `dim_bodega_vino`, `dim_region_vitivinicola`,
    `dim_catador_sumiller`, `dim_mercado_vino`.
  - `fct_resena` (Fact_Resena), `fct_puntuacion` (Fact_Puntuacion, dominio 80–100),
    `fct_precio_mercado` (Fact_Precio_Mercado, precio > 0, USD).
- `models/marts/_schema.yml` + `tests/` — tests DBT `unique`, `not_null`,
  `relationships`, `accepted_values` y dos tests singulares de dominio (RT-06/RT-13).

> No colisiona con las tablas existentes (`fact_resenas`, `dim_pais`, …): los marts
> usan nombres `fct_*` / `dim_*_vino`. El ETL actual (pandas) sigue funcionando.

## Cómo correr (requiere StarRocks arriba y las tablas base pobladas)
```bash
pip install -r dbt_vinanalytics/requirements.txt
cd dbt_vinanalytics
export STARROCKS_HOST=localhost STARROCKS_DB=retailytics STARROCKS_USER=root STARROCKS_PASS=
dbt run   --profiles-dir .      # construye staging + marts
dbt test  --profiles-dir .      # ejecuta los tests DBT (fail si alguno falla)
dbt docs generate --profiles-dir .   # genera el grafo de linaje (Princ. VII)
```

## Orden dentro del pipeline (Princ. IX, se cablea con Airflow en una fase posterior)
`GE staging (previa) → dbt run → dbt test + GE DW (posterior) → agregaciones ClickHouse`
