-- Fact_Resena (matriz §9.8 · CU-O02): la reseña como hecho, con FKs resueltas.
{{ config(
    materialized='table',
    table_type='DUPLICATE',
    keys=['id_resena'],
    distributed_by=['id_resena'],
    buckets=10,
    properties={"replication_num": "1"}
) }}

select
    r.id_resena,
    r.id_variedad           as id_vino,
    r.id_bodega,
    r.id_region,
    r.id_catador,
    r.id_pais               as id_mercado,
    r.puntos,
    r.precio,
    char_length(coalesce(r.descripcion, '')) as longitud_descripcion
from {{ ref('stg_resena') }} r
