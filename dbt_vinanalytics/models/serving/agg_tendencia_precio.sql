-- agg_tendencia_precio — precio promedio por año (extraído del título) y variedad.
-- Princ. VI: mueve a DBT el GROUP BY + REGEXP_EXTRACT que estaba suelto en
-- app.py::api_graficas_tendencias_precio. El endpoint ahora SOLO lee esta vista y
-- calcula la regresión/proyección (presentación), sin agregar en Python.
--   variedad = nombre de la variedad, o '__ALL__' para el agregado global.
{{ config(materialized='view') }}

-- Por variedad
select
    dv.nombre                                          as variedad,
    regexp_extract(fr.title, '(2[0-9]{3})', 1)         as anio,
    round(avg(cast(fr.price as double)), 2)            as precio_promedio,
    count(*)                                           as total
from {{ source('dw_vitivinicola', 'fact_resenas') }} fr
join {{ source('dw_vitivinicola', 'dim_variedad') }} dv on fr.id_variedad = dv.id_variedad
where fr.price > 0
  and regexp_extract(fr.title, '(2[0-9]{3})', 1) != ''
group by dv.nombre, regexp_extract(fr.title, '(2[0-9]{3})', 1)

union all

-- Agregado global (todas las variedades)
select
    '__ALL__'                                          as variedad,
    regexp_extract(title, '(2[0-9]{3})', 1)            as anio,
    round(avg(cast(price as double)), 2)               as precio_promedio,
    count(*)                                           as total
from {{ source('dw_vitivinicola', 'fact_resenas') }}
where price > 0
  and regexp_extract(title, '(2[0-9]{3})', 1) != ''
group by regexp_extract(title, '(2[0-9]{3})', 1)
