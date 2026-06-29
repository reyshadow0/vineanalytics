# Calidad de datos — Great Expectations + fail-fast (Fase 1)

Implementa **CU-O04** del paquete `etl-calidad` (OP2) y el **Principio V** de la
constitución (calidad primero, validación fallida **detiene** el pipeline).

## Suites
- `ge_staging.py` — **gate previo**: valida los Parquet de `stage/`
  (`wine_raw.parquet`, `fact_resenas.parquet`): existencia, unicidad de clave,
  no-nulos, dominios (`points` 0–100, `price ≥ 0`). Tolera el sentinela 0 en crudo.
- `ge_dw.py` — **gate posterior**: valida los marts DBT en StarRocks
  (`fct_resena`, `fct_puntuacion`, `fct_precio_mercado`): unicidad de PK, no-nulos,
  **`puntaje` estricto 80–100**, `precio > 0`, `moneda ∈ {USD}`.
- `run_quality.py` — orquestador **fail-fast**: `exit 0` si todo pasa, `exit 1` si
  algo falla (corta el pipeline; Airflow lo usará como tarea de calidad).

## Cómo correr
```bash
pip install -r quality/requirements.txt
# gate previo (antes del ETL/DBT):
python quality/run_quality.py --stage
# gate posterior (después de dbt run, antes de ClickHouse):
python quality/run_quality.py --dw
# ambos:
python quality/run_quality.py
```

## Posición en el flujo (Princ. IX)
`ingesta → [GE --stage] → dbt run → [dbt test + GE --dw] → agregaciones`
Cada gate que falla devuelve exit≠0 y **detiene** el DAG (fail-fast, RT-07/RT-15).
