-- Staging de reseñas: vista ligera sobre el source fact_resenas.
-- Limpia/normaliza y deduplica por la clave natural (id_resena).
-- No persiste datos nuevos: es la base declarativa para los marts (CU-O03).

{{ config(materialized='view') }}

with fuente as (
    select
        id_resena,
        points        as puntos,
        price         as precio,
        title         as titulo,
        designation   as designacion,
        description   as descripcion,
        region_2,
        id_pais,
        id_variedad,
        id_bodega,
        id_provincia,
        id_region,
        id_catador
    from {{ source('dw_vitivinicola', 'fact_resenas') }}
),

dedup as (
    -- defensa en profundidad: una fila por id_resena (RN-305 de etl-calidad)
    select *,
           row_number() over (partition by id_resena order by id_resena) as rn
    from fuente
)

select
    id_resena,
    puntos,
    precio,
    titulo,
    designacion,
    descripcion,
    region_2,
    id_pais,
    id_variedad,
    id_bodega,
    id_provincia,
    id_region,
    id_catador
from dedup
where rn = 1
