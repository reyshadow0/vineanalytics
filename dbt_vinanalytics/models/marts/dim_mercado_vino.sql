-- Dim_Mercado (contexto vitivinícola) ← dim_pais existente.
-- En el dominio del vino el país de origen actúa como mercado.
{{ config(
    materialized='table',
    table_type='PRIMARY',
    keys=['id_mercado'],
    distributed_by=['id_mercado'],
    buckets=3,
    properties={"replication_num": "1"}
) }}

select
    id_pais as id_mercado,
    nombre  as pais
from {{ source('dw_vitivinicola', 'dim_pais') }}
