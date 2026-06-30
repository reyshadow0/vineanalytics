-- agg_variedad — agregación por variedad. total = todas las reseñas;
-- total_con_precio = reseñas con price>0 (sirve la gráfica de precios).
-- Princ. VI: reemplaza el GROUP BY imperativo de populate.py::_pop_vino.
{{ config(materialized='view') }}

select
    dv.nombre                                                              as variedad,
    count(*)                                                               as total,
    round(avg(case when fr.price > 0 then cast(fr.price as double) end), 2) as precio_promedio,
    sum(case when fr.price > 0 then 1 else 0 end)                          as total_con_precio
from {{ source('dw_vitivinicola', 'fact_resenas') }} fr
join {{ source('dw_vitivinicola', 'dim_variedad') }} dv on fr.id_variedad = dv.id_variedad
where dv.nombre != 'Desconocido'
group by dv.nombre
