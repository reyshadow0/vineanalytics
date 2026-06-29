-- Dim_Region_Vitivinicola ← dim_region existente.
{{ config(
    materialized='table',
    table_type='PRIMARY',
    keys=['id_region'],
    distributed_by=['id_region'],
    buckets=3,
    properties={"replication_num": "1"}
) }}

select
    id_region,
    nombre as region
from {{ source('dw_vitivinicola', 'dim_region') }}
