-- Test singular: el precio en Fact_Precio_Mercado debe ser > 0 (RT-06).
-- Falla si devuelve filas.
select id_precio, precio
from {{ ref('fct_precio_mercado') }}
where precio is null or precio <= 0
