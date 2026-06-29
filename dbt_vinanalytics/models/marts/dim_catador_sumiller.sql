-- Dim_Catador_Sumiller ← dim_catador existente.
{{ config(
    materialized='table',
    table_type='PRIMARY',
    keys=['id_catador'],
    distributed_by=['id_catador'],
    buckets=3,
    properties={"replication_num": "1"}
) }}

select
    id_catador,
    nombre  as catador,
    twitter
from {{ source('dw_vitivinicola', 'dim_catador') }}
