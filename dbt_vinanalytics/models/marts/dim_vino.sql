-- Dim_Vino (spec ingesta-datos/etl-calidad) ← dim_variedad existente.
{{ config(
    materialized='table',
    table_type='PRIMARY',
    keys=['id_vino'],
    distributed_by=['id_vino'],
    buckets=3,
    properties={"replication_num": "1"}
) }}

select
    id_variedad as id_vino,
    nombre      as variedad
from {{ source('dw_vitivinicola', 'dim_variedad') }}
