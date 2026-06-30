-- agg_bodega — agregación por bodega. Princ. VI: reemplaza el GROUP BY
-- imperativo de populate.py::_pop_vino. Expresiones idénticas → sin cambios.
{{ config(materialized='view') }}

select
    db.nombre                                  as bodega,
    count(*)                                   as total,
    round(avg(cast(fr.points as double)), 1)   as puntuacion_promedio
from {{ source('dw_vitivinicola', 'fact_resenas') }} fr
join {{ source('dw_vitivinicola', 'dim_bodega') }} db on fr.id_bodega = db.id_bodega
where db.nombre != 'Desconocido'
group by db.nombre
