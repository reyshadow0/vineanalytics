-- Dim_Bodega ← dim_bodega existente (renombrado para no colisionar).
{{ config(
    materialized='table',
    table_type='PRIMARY',
    keys=['id_bodega'],
    distributed_by=['id_bodega'],
    buckets=3,
    properties={"replication_num": "1"}
) }}

select
    id_bodega,
    nombre as bodega
from {{ source('dw_vitivinicola', 'dim_bodega') }}
