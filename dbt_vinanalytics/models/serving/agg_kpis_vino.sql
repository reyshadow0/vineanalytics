-- agg_kpis_vino — KPIs globales del catálogo de vino (una fila).
-- Princ. VI: agregación declarativa única. Reemplaza el SQL imperativo de
-- clickhouse/populate.py::_pop_vino (KPIs) y el fallback de app.py::api_kpis.
-- Expresiones idénticas a las originales → resultados sin cambios.
{{ config(materialized='view') }}

with k as (
    select
        count(*)                                                           as total_resenas,
        round(avg(cast(points as double)), 1)                             as puntuacion_promedio,
        round(avg(case when price > 0 then cast(price as double) end), 2) as precio_promedio,
        max(case when price > 0 then price end)                           as precio_maximo,
        min(case when price > 0 then price end)                           as precio_minimo
    from {{ source('dw_vitivinicola', 'fact_resenas') }}
),
dims as (
    select
        (select count(*) from {{ source('dw_vitivinicola', 'dim_pais') }})     as total_paises,
        (select count(*) from {{ source('dw_vitivinicola', 'dim_variedad') }}) as total_variedades,
        (select count(*) from {{ source('dw_vitivinicola', 'dim_bodega') }})   as total_bodegas
)

select
    k.total_resenas,
    k.puntuacion_promedio,
    k.precio_promedio,
    k.precio_maximo,
    k.precio_minimo,
    dims.total_paises,
    dims.total_variedades,
    dims.total_bodegas
from k
cross join dims
