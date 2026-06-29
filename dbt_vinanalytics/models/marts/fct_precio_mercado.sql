-- Fact_Precio_Mercado (matriz §9.8 · CU-O02): precio observado por vino/mercado.
-- Solo precios válidos (> 0); moneda canónica USD (origen winemag en USD).
{{ config(
    materialized='table',
    table_type='DUPLICATE',
    keys=['id_precio'],
    distributed_by=['id_precio'],
    buckets=10,
    properties={"replication_num": "1"}
) }}

select
    r.id_resena      as id_precio,
    r.id_resena,
    r.id_vino,
    r.id_mercado,
    r.precio,
    'USD'            as moneda
from {{ ref('fct_resena') }} r
where r.precio > 0
