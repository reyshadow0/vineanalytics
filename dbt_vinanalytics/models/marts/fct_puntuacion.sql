-- Fact_Puntuacion (matriz §9.8 · CU-O02): puntaje del catador, dominio 80–100.
-- Filtra puntajes fuera de rango (los 0 = faltantes del staging se descartan aquí),
-- de modo que la suite GE posterior sobre el DW pasa en estricto 80..100 (RT-06).
{{ config(
    materialized='table',
    table_type='DUPLICATE',
    keys=['id_puntuacion'],
    distributed_by=['id_puntuacion'],
    buckets=10,
    properties={"replication_num": "1"}
) }}

select
    r.id_resena   as id_puntuacion,
    r.id_resena,
    r.id_vino,
    r.id_catador,
    r.puntos      as puntaje
from {{ ref('fct_resena') }} r
where r.puntos between 80 and 100
