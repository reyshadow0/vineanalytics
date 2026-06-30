-- agg_puntuacion_hist — histograma de puntuación. Princ. VI: reemplaza el
-- GROUP BY imperativo de populate.py::_pop_vino. Expresiones idénticas.
{{ config(materialized='view') }}

select
    points     as puntuacion,
    count(*)   as total
from {{ source('dw_vitivinicola', 'fact_resenas') }}
group by points
