-- agg_pais — agregación por país (gráfica países, lista, browse, v1/mercados,
-- comparar-mercados). Princ. VI: reemplaza el GROUP BY imperativo de
-- clickhouse/populate.py::_pop_vino. Expresiones idénticas → sin cambios.
{{ config(materialized='view') }}

select
    dp.nombre                                                            as pais,
    count(*)                                                             as total,
    round(avg(cast(fr.points as double)), 1)                            as puntuacion_promedio,
    round(avg(case when fr.price > 0 then cast(fr.price as double) end), 2) as precio_promedio,
    count(distinct fr.id_variedad)                                      as variedades
from {{ source('dw_vitivinicola', 'fact_resenas') }} fr
join {{ source('dw_vitivinicola', 'dim_pais') }} dp on fr.id_pais = dp.id_pais
where dp.nombre != 'Desconocido'
group by dp.nombre
