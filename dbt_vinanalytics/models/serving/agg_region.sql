-- agg_region — agregación por región. Princ. VI: reemplaza el GROUP BY
-- imperativo de populate.py::_pop_vino. Expresiones idénticas → sin cambios.
{{ config(materialized='view') }}

select
    dr.nombre  as region,
    count(*)   as total
from {{ source('dw_vitivinicola', 'fact_resenas') }} fr
join {{ source('dw_vitivinicola', 'dim_region') }} dr on fr.id_region = dr.id_region
where dr.nombre != 'Desconocido'
group by dr.nombre
